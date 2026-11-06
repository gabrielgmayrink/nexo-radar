"""Password verification stays in Supabase; this app keeps opaque sessions only."""
import re
import secrets
from datetime import datetime,timedelta,timezone
from urllib.error import HTTPError
from radar.mail import EMAIL_PATTERN,email_list
from radar.team_auth import auth_request,digest


class AuthenticationFailed(ValueError): pass
class TooManyAttempts(ValueError): pass


def throttle(db,subject):
    hashed=digest(str(subject).strip().lower())
    with db.transaction():
        db.execute('select pg_advisory_xact_lock(%s)',(int(hashed[:15],16),))
        count=db.execute("select count(*) from radar_auth_attempts where subject_hash=%s and created_at>now()-interval '15 minutes'",(hashed,)).fetchone()[0]
        if count>=8:raise TooManyAttempts('Login temporarily limited')
        db.execute('insert into radar_auth_attempts(subject_hash) values(%s)',(hashed,))
        db.execute("delete from radar_auth_attempts where created_at<now()-interval '24 hours'")


def create_session(db,user,email):
    if user.get('email','').lower()!=email or not user.get('email_confirmed_at') or not user.get('id'):
        raise AuthenticationFailed('Unverified identity')
    token=secrets.token_urlsafe(32)
    db.execute('insert into radar_team_sessions(token_digest,user_id,email,expires_at) values(%s,%s,%s,%s)',
               (digest(token),user['id'],email,datetime.now(timezone.utc)+timedelta(days=7)))
    return email,token


def password_login(db,email,password,*,provider=auth_request):
    if not isinstance(email,str) or not isinstance(password,str) or len(email)>254 or not 1<=len(password)<=128:
        raise AuthenticationFailed('Invalid credentials')
    email=email.strip().lower()
    throttle(db,email)
    if not EMAIL_PATTERN.fullmatch(email) or email not in email_list('RADAR_TEAM_EMAILS'):
        raise AuthenticationFailed('Invalid credentials')
    try:response=provider('token?grant_type=password',{'email':email,'password':password})
    except HTTPError as exc:
        if exc.code in (400,401,403):raise AuthenticationFailed('Invalid credentials') from None
        raise
    return create_session(db,response.get('user') or {},email)


def create_invite(db,email):
    email=email.strip().lower()
    if email not in email_list('RADAR_TEAM_EMAILS'):raise ValueError('Unknown team member')
    token=secrets.token_urlsafe(32)
    db.execute('insert into radar_account_invites(token_digest,email,expires_at) values(%s,%s,%s)',
               (digest(token),email,datetime.now(timezone.utc)+timedelta(hours=24)))
    return token


def setup_password(db,token,password,*,provider=auth_request):
    if not isinstance(token,str) or not re.fullmatch(r'[A-Za-z0-9_-]{43}',token):raise AuthenticationFailed('Invalid invite')
    if not isinstance(password,str) or not 12<=len(password)<=128:raise AuthenticationFailed('Invalid password')
    throttle(db,'invite:'+token)
    with db.transaction():
        row=db.execute('select email from radar_account_invites where token_digest=%s and consumed_at is null and expires_at>now() for update',(digest(token),)).fetchone()
        if not row or row[0] not in email_list('RADAR_TEAM_EMAILS'):raise AuthenticationFailed('Expired invite')
        email=row[0]
        existing=db.execute('select id from auth.users where lower(email)=%s',(email,)).fetchone()
        if existing:
            response=provider('admin/users/'+str(existing[0]),{'password':password,'email_confirm':True},method='PUT')
        else:response=provider('admin/users',{'email':email,'password':password,'email_confirm':True})
        user=response.get('user',response)
        result=create_session(db,user,email)
        db.execute('update radar_account_invites set consumed_at=now() where token_digest=%s',(digest(token),))
    return result
