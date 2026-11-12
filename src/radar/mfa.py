"""Supabase TOTP verification before an opaque app session can be issued."""
import base64
import json
import os
import re
import secrets
import time
from datetime import datetime,timedelta,timezone
from urllib.request import Request,build_opener
from urllib.error import HTTPError
import jwt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from radar.team_auth import digest
from radar.mail import NoRedirect,email_list
from radar.access_security import account_state,throttle

UUID=r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'


class MFARequired(ValueError):
    def __init__(self,pending_token,factors,*,enrollment_required=False,password_changed=False):
        super().__init__('Second factor required')
        self.response={'mfaRequired':True,'pendingToken':pending_token,'factors':factors,
                       'enrollmentRequired':enrollment_required,'passwordChanged':password_changed}


def _cipher():
    try:
        key=base64.urlsafe_b64decode(os.environ.get('RADAR_AUTH_ENCRYPTION_KEY','')+'='*(-len(os.environ.get('RADAR_AUTH_ENCRYPTION_KEY',''))%4))
    except (ValueError,TypeError):key=b''
    if len(key)!=32:raise ValueError('MFA encryption is not configured')
    return AESGCM(key)


def auth_user_request(path,payload=None,*,access_token,method='POST',opener=None):
    from radar.postgres_store import PROJECT_REF
    allowed=(method=='GET' and path=='user' or method=='POST' and
             (path=='factors' or re.fullmatch(r'factors/'+UUID+r'/(challenge|verify)',path)))
    if not allowed:raise ValueError('Unexpected user Auth operation')
    base=os.environ.get('SUPABASE_URL','').rstrip('/')
    if not PROJECT_REF or base!='https://'+PROJECT_REF+'.supabase.co':raise ValueError('Unexpected Auth destination')
    if not isinstance(access_token,str) or not 20<=len(access_token)<=20000:raise ValueError('Invalid Auth proof')
    key=os.environ.get('SUPABASE_SECRET_KEY') or os.environ.get('SUPABASE_SERVICE_ROLE_KEY')
    if not key:raise ValueError('Auth is not configured')
    headers={'apikey':key,'Authorization':'Bearer '+access_token,'Content-Type':'application/json'}
    request=Request(base+'/auth/v1/'+path,headers=headers,method=method,
                    data=json.dumps(payload or {}).encode() if method=='POST' else None)
    with (opener or build_opener(NoRedirect())).open(request,timeout=15) as response:body=response.read(1_000_001)
    if len(body)>1_000_000:raise ValueError('Auth response too large')
    return json.loads(body)


def finish_first_factor(db,response,email,generation):
    from radar.password_auth import AuthenticationFailed,create_session
    user=response.get('user') or {}
    if user.get('email','').lower()!=email or not user.get('id') or not user.get('email_confirmed_at'):
        raise AuthenticationFailed('Unverified identity')
    state=account_state(db,email)
    factors=[{'id':f['id'],'factor_type':f.get('factor_type'),'friendly_name':f.get('friendly_name','Autenticador')}
             for f in user.get('factors',[]) if isinstance(f,dict) and f.get('status')=='verified' and re.fullmatch(UUID,str(f.get('id','')))]
    required=state[1] or email in email_list('RADAR_MFA_REQUIRED_EMAILS')
    if not factors and not required:return create_session(db,user,email,expected_generation=generation)
    token=response.get('access_token')
    if not isinstance(token,str) or not token:raise AuthenticationFailed('Second-factor proof unavailable')
    totp=[f for f in factors if f['factor_type']=='totp']
    if factors and not totp:raise AuthenticationFailed('Supported second factor required')
    pending=secrets.token_urlsafe(32);hashed=digest(pending);nonce=secrets.token_bytes(12)
    encrypted=nonce+_cipher().encrypt(nonce,token.encode(),('nexo-mfa:'+hashed).encode())
    db.execute('''insert into radar_mfa_pending(token_digest,user_id,email,auth_generation,encrypted_access_token,factors,enrollment_required,expires_at)
        values(%s,%s,%s,%s,%s,%s::jsonb,%s,%s)''',
        (hashed,user['id'],email,generation,encrypted,json.dumps(totp),not bool(totp),datetime.now(timezone.utc)+timedelta(minutes=5)))
    raise MFARequired(pending,totp,enrollment_required=not bool(totp))


def _pending(db,token):
    from radar.password_auth import AuthenticationFailed
    if not isinstance(token,str) or not re.fullmatch(r'[A-Za-z0-9_-]{43}',token):raise AuthenticationFailed('Invalid MFA attempt')
    row=db.execute('''select user_id,email,auth_generation,encrypted_access_token,factors,enrollment_required
        from radar_mfa_pending where token_digest=%s and consumed_at is null and expires_at>now() and attempts<5 for update''',(digest(token),)).fetchone()
    if not row or row[1] not in email_list('RADAR_TEAM_EMAILS'):raise AuthenticationFailed('Expired MFA attempt')
    generation,_,disabled=account_state(db,row[1])
    if generation!=row[2] or disabled:raise AuthenticationFailed('Account changed')
    db.execute('update radar_mfa_pending set attempts=attempts+1 where token_digest=%s',(digest(token),))
    encrypted=bytes(row[3]);nonce=encrypted[:12]
    access=_cipher().decrypt(nonce,encrypted[12:],('nexo-mfa:'+digest(token)).encode()).decode()
    return row,access


def enroll(db,token,*,origin='unknown',provider=auth_user_request):
    from radar.password_auth import AuthenticationFailed
    throttle(db,'mfa:'+str(token),origin)
    with db.transaction():row,access=_pending(db,token)
    if not row[5]:raise AuthenticationFailed('Enrollment unavailable')
    result=provider('factors',{'factor_type':'totp','friendly_name':'Nexo Radar'},access_token=access)
    factor=result.get('id');qr=(result.get('totp') or {}).get('qr_code')
    if not re.fullmatch(UUID,str(factor)) or not isinstance(qr,str) or len(qr)>100000:raise ValueError('Invalid enrollment response')
    if qr.lstrip().startswith('<svg'):qr='data:image/svg+xml;base64,'+base64.b64encode(qr.encode()).decode()
    if not qr.startswith('data:image/svg+xml;base64,'):raise ValueError('Invalid enrollment image')
    factors=[{'id':factor,'factor_type':'totp','friendly_name':'Nexo Radar'}]
    db.execute('update radar_mfa_pending set factors=%s::jsonb,enrollment_required=false where token_digest=%s and consumed_at is null',
               (json.dumps(factors),digest(token)))
    return {'factors':factors,'qrCode':qr}


def verify(db,token,factor_id,code,*,origin='unknown',provider=auth_user_request):
    from radar.password_auth import AuthenticationFailed,create_session
    if not isinstance(code,str) or not re.fullmatch(r'\d{6}',code):raise AuthenticationFailed('Invalid authenticator code')
    throttle(db,'mfa:'+str(token),origin)
    with db.transaction():row,access=_pending(db,token)
    factors=row[4] if isinstance(row[4],list) else json.loads(row[4])
    if factor_id not in {f.get('id') for f in factors}:raise AuthenticationFailed('Invalid factor')
    try:
        challenge=provider('factors/'+factor_id+'/challenge',{},access_token=access)
        response=provider('factors/'+factor_id+'/verify',{'challenge_id':challenge['id'],'code':code},access_token=access)
        verified_token=response.get('access_token','')
        # The token is first validated at the fixed Supabase /user endpoint.
        # Reading its assurance claim afterwards does not authorize an unverified JWT.
        user=provider('user',access_token=verified_token,method='GET')
        user=user.get('user',user)
        claims=jwt.decode(verified_token,options={'verify_signature':False})
        if (claims.get('aal')!='aal2' or claims.get('sub')!=str(row[0]) or claims.get('exp',0)<=time.time()
            or str(user.get('id'))!=str(row[0]) or user.get('email','').lower()!=row[1]):
            raise AuthenticationFailed('Second factor not verified')
    except (HTTPError,KeyError,jwt.InvalidTokenError) as exc:
        raise AuthenticationFailed('Second factor not verified') from None
    with db.transaction():
        consumed=db.execute('''update radar_mfa_pending set consumed_at=now() where token_digest=%s
            and consumed_at is null and expires_at>now() returning email''',(digest(token),)).fetchone()
        if not consumed:raise AuthenticationFailed('MFA attempt already consumed')
        return create_session(db,user,row[1],expected_generation=row[2],assurance='aal2')
