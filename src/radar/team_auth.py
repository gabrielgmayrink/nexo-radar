"""Supabase validates one-time links; opaque HttpOnly sessions stay on the server."""
import hashlib
import html
import json
import os
import re
import secrets
from datetime import datetime,timedelta,timezone
from http.cookies import SimpleCookie
from urllib.request import Request,build_opener
from radar.mail import APP_URL,NoRedirect,email_list,reserve,send_reserved
from radar.postgres_store import PROJECT_REF

COOKIE='__Host-radar_session'


def digest(value):return hashlib.sha256(value.encode()).hexdigest()


def auth_request(path,payload,*,opener=None,method='POST'):
    if not (method=='POST' and path in ('admin/generate_link','verify','token?grant_type=password','admin/users') or method in ('DELETE','PUT') and re.fullmatch(r'admin/users/[0-9a-f-]{36}',path)):
        raise ValueError('Unexpected Auth operation')
    base=os.environ.get('SUPABASE_URL','').rstrip('/')
    if not PROJECT_REF or base!='https://'+PROJECT_REF+'.supabase.co':raise ValueError('Unexpected Auth destination')
    key=os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or os.environ.get('SUPABASE_SECRET_KEY')
    if not key:raise ValueError('Auth is not configured')
    headers={'apikey':key,'Content-Type':'application/json'}
    if key.startswith('eyJ'):headers['Authorization']='Bearer '+key
    request=Request(base+'/auth/v1/'+path,data=json.dumps(payload).encode(),headers=headers,method=method)
    with (opener or build_opener(NoRedirect())).open(request,timeout=15) as response:
        body=response.read(1_000_000)
        return {} if method=='DELETE' and not body.strip() else json.loads(body)


def request_login(db,email,*,provider=auth_request,sender=send_reserved):
    email=email.strip().lower()
    if email not in email_list('RADAR_TEAM_EMAILS'):return
    identifier=reserve(db,email,'login','login:'+secrets.token_hex(16))
    if not identifier:return
    try:
        data=provider('admin/generate_link',{'type':'magiclink','email':email})
        properties=data.get('properties',data)
        token=properties.get('hashed_token','')
        kind=properties.get('verification_type','magiclink')
        if not re.fullmatch(r'[A-Za-z0-9_-]{20,256}',token) or kind not in ('magiclink','signup','email'):
            raise ValueError('Invalid login response')
        expires=datetime.now(timezone.utc)+timedelta(minutes=15)
        db.execute('insert into radar_login_requests(token_digest,email,verification_type,expires_at) values(%s,%s,%s,%s)',
                   (digest(token),email,kind,expires))
        link=APP_URL+'/#login='+token
        body=f'<h1>Entrar no Radar de Licitações</h1><p>Você solicitou acesso à equipe Public.</p><p><a href="{html.escape(link,quote=True)}">Confirmar entrada no Radar</a></p><p>O link expira em 15 minutos e só pode ser usado uma vez. Se você não solicitou o acesso, ignore esta mensagem.</p>'
        sender(db,identifier,email,'Seu acesso ao Radar de Licitações',body,
               'Confirme sua entrada no Radar: '+link+'\nO link expira em 15 minutos. Se não solicitou, ignore.')
    except Exception:
        db.execute("update radar_mail_outbox set status='failed' where id=%s and status='reserved'",(identifier,))
        raise


def login_record(db,token):
    if not isinstance(token,str) or not re.fullmatch(r'[A-Za-z0-9_-]{20,256}',token):raise ValueError('Invalid login link')
    result=db.execute('''select email,verification_type from radar_login_requests
        where token_digest=%s and consumed_at is null and expires_at>now()''',(digest(token),)).fetchone()
    if not result or result[0] not in email_list('RADAR_TEAM_EMAILS'):raise ValueError('Expired login link')
    return result


def confirm_login(db,token,*,provider=auth_request):
    email,kind=login_record(db,token)
    # No email lookup or user identity supplied by the browser is trusted.
    result=provider('verify',{'token_hash':token,'type':kind})
    user=result.get('user') or {}
    if user.get('email','').lower()!=email or not user.get('email_confirmed_at') or not user.get('id'):
        raise ValueError('Unverified identity')
    session=secrets.token_urlsafe(32)
    with db.transaction():
        consumed=db.execute('''update radar_login_requests set consumed_at=now()
            where token_digest=%s and consumed_at is null and expires_at>now() returning email''',(digest(token),)).fetchone()
        if not consumed:raise ValueError('Login already confirmed')
        db.execute('insert into radar_team_sessions(token_digest,user_id,email,expires_at) values(%s,%s,%s,%s)',
                   (digest(session),user['id'],email,datetime.now(timezone.utc)+timedelta(days=7)))
    return email,session


def session_cookie(token,*,clear=False):
    return COOKIE+'='+('' if clear else token)+'; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age='+('0' if clear else '604800')


def session_token(header):
    if header and len(header)>8192:return None
    cookies=SimpleCookie()
    try:cookies.load(header or '')
    except Exception:return None
    token=cookies[COOKIE].value if COOKIE in cookies else ''
    return token if re.fullmatch(r'[A-Za-z0-9_-]{43}',token) else None


def session_user(db,header):
    token=session_token(header)
    if not token:return None
    row=db.execute('select email from radar_team_sessions where token_digest=%s and expires_at>now()',
                   (digest(token),)).fetchone()
    return row[0] if row and row[0] in email_list('RADAR_TEAM_EMAILS') else None


def revoke_session(db,header):
    token=session_token(header)
    if token:db.execute('delete from radar_team_sessions where token_digest=%s',(digest(token),))
