"""Password verification stays in Supabase; this app keeps opaque sessions only."""
import re
import secrets
from datetime import datetime,timedelta,timezone
from urllib.error import HTTPError
from radar.mail import EMAIL_PATTERN,email_list
from radar.team_auth import auth_request,digest
from radar.access_security import throttle,TooManyAttempts,account_state,lock_account,revoke_account


class AuthenticationFailed(ValueError): pass
def password_reset_required(db,email):
    row=db.execute('select password_reset_required from radar_account_security where email=%s',(email,)).fetchone()
    return bool(row and row[0] is True)


def create_session(db,user,email,*,expected_generation=None,assurance='aal1'):
    if user.get('email','').lower()!=email or not user.get('email_confirmed_at') or not user.get('id'):
        raise AuthenticationFailed('Unverified identity')
    with db.transaction():
        lock_account(db,email)
        generation,required,disabled=account_state(db,email,lock=True)
        if disabled or password_reset_required(db,email) or (expected_generation is not None and generation!=expected_generation):
            raise AuthenticationFailed('Account changed; authenticate again')
        if (required or email in email_list('RADAR_MFA_REQUIRED_EMAILS')) and assurance!='aal2':raise AuthenticationFailed('Second factor required')
        token=secrets.token_urlsafe(32)
        db.execute('''insert into radar_team_sessions(token_digest,user_id,email,expires_at,auth_generation,assurance_level,credential_fingerprint)
            values(%s,%s,%s,%s,%s,%s,(select credential_fingerprint from public.radar_auth_identities where id=%s))''',
                   (digest(token),user['id'],email,datetime.now(timezone.utc)+timedelta(days=7),generation,assurance,user['id']))
    return email,token


def password_login(db,email,password,*,provider=auth_request,origin='unknown'):
    if not isinstance(email,str) or not isinstance(password,str) or len(email)>254 or not 1<=len(password)<=128:
        raise AuthenticationFailed('Invalid credentials')
    email=email.strip().lower()
    throttle(db,email,origin)
    if not EMAIL_PATTERN.fullmatch(email) or email not in email_list('RADAR_TEAM_EMAILS'):
        raise AuthenticationFailed('Invalid credentials')
    generation,_,disabled=account_state(db,email)
    if disabled or password_reset_required(db,email):raise AuthenticationFailed('Use a new personal invite')
    try:response=provider('token?grant_type=password',{'email':email,'password':password})
    except HTTPError as exc:
        if exc.code in (400,401,403):raise AuthenticationFailed('Invalid credentials') from None
        raise
    from radar.mfa import finish_first_factor
    return finish_first_factor(db,response,email,generation)


def create_invite(db,email):
    email=email.strip().lower()
    if email not in email_list('RADAR_TEAM_EMAILS'):raise ValueError('Unknown team member')
    token=secrets.token_urlsafe(32)
    db.execute('insert into radar_account_invites(token_digest,email,expires_at) values(%s,%s,%s)',
               (digest(token),email,datetime.now(timezone.utc)+timedelta(hours=24)))
    return token


def setup_password(db,token,password,*,provider=auth_request,origin='unknown'):
    if not isinstance(token,str) or not re.fullmatch(r'[A-Za-z0-9_-]{43}',token):raise AuthenticationFailed('Invalid invite')
    if not isinstance(password,str) or not 12<=len(password)<=128:raise AuthenticationFailed('Invalid password')
    throttle(db,'invite:'+token,origin)
    with db.transaction():
        row=db.execute('select email from radar_account_invites where token_digest=%s and consumed_at is null and expires_at>now() for update',(digest(token),)).fetchone()
        if not row or row[0] not in email_list('RADAR_TEAM_EMAILS'):raise AuthenticationFailed('Expired invite')
        email=row[0]
        existing=db.execute('select id from public.radar_auth_identities where lower(email)=%s',(email,)).fetchone()
        generation=revoke_account(db,email)
    # Keep the revocation committed even if the remote provider or a later
    # insert fails. Retrying then requires a new invite, never an old session.
    if existing:
        response=provider('admin/users/'+str(existing[0]),{'password':password,'email_confirm':True},method='PUT')
    else:response=provider('admin/users',{'email':email,'password':password,'email_confirm':True})
    user=response.get('user',response)
    if user.get('email','').lower()!=email or not user.get('id') or not user.get('email_confirmed_at'):
        raise AuthenticationFailed('Unverified identity')
    with db.transaction():
        lock_account(db,email)
        current_generation,_,disabled=account_state(db,email,lock=True)
        if disabled or current_generation!=generation:raise AuthenticationFailed('Account changed; use a new invite')
        db.execute('update radar_account_security set password_reset_required=false,updated_at=now() where email=%s',(email,))
    factors=[factor for factor in user.get('factors',[]) if factor.get('status')=='verified']
    if factors or account_state(db,email)[1] or email in email_list('RADAR_MFA_REQUIRED_EMAILS'):
        # An administrative password response is not proof of a second factor.
        from radar.mfa import MFARequired
        raise MFARequired(None,[],enrollment_required=not bool(factors),password_changed=True)
    return create_session(db,user,email,expected_generation=generation)
