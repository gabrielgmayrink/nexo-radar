"""Exercise real Supabase password auth with a new, disposable test identity."""
import json
import os
import secrets
import uuid
from runtime_env import load

load()
os.environ['RADAR_SUPABASE_PROJECT_REF']='hxngkmrsthyjycxaellk'
email='nexo-test-'+uuid.uuid4().hex+'@example.invalid'
os.environ['RADAR_TEAM_EMAILS']=email
from radar.postgres_store import PostgresStore
from radar.password_auth import create_invite,setup_password,password_login,AuthenticationFailed
from radar.team_auth import auth_request

store=PostgresStore();user_id=None
try:
    password=secrets.token_urlsafe(28)
    invite=create_invite(store.db,email)
    accepted,session=setup_password(store.db,invite,password)
    assert accepted==email and len(session)==43
    user_id=store.db.execute('select id from auth.users where email=%s',(email,)).fetchone()[0]
    assert password_login(store.db,email,password)[0]==email
    try:setup_password(store.db,invite,password)
    except AuthenticationFailed:pass
    else:raise ValueError('Invite was reusable')
    try:password_login(store.db,email,secrets.token_urlsafe(20))
    except AuthenticationFailed:pass
    else:raise ValueError('Wrong password was accepted')
    print(json.dumps({'realPasswordLogin':True,'oneTimeInvite':True,'invalidPasswordRejected':True,'emailSent':False}))
finally:
    if user_id:auth_request('admin/users/'+str(user_id),{},method='DELETE')
    store.db.execute('delete from radar_account_invites where email=%s',(email,))
    store.close()
