"""Set the two owner-specified passwords and validate company isolation over HTTPS."""
import json
import os
import sys
from http.cookies import SimpleCookie
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from pathlib import Path
from runtime_env import load

load()
os.environ['RADAR_SUPABASE_PROJECT_REF']='hxngkmrsthyjycxaellk'
ACCOUNTS={'public':'publicgerencia9@gmail.com','gerico':'gericomayrink@gmail.com'}
os.environ['RADAR_TEAM_EMAILS']=','.join(ACCOUNTS.values())
from radar.postgres_store import PostgresStore
from radar.password_auth import create_invite,setup_password
from radar.team_auth import digest,COOKIE
from radar.company_access import memberships

BASE='https://nexo-radar-taupe.vercel.app'


def http(path,*,body=None,cookie=None):
    headers={'Accept':'application/json'}
    if cookie:headers['Cookie']=cookie
    if body:headers.update({'Origin':BASE,'Content-Type':'application/json'})
    request=Request(BASE+path,headers=headers,data=json.dumps(body).encode() if body else None)
    try:
        with urlopen(request,timeout=60) as response:return response.status,json.load(response),response.headers
    except HTTPError as exc:return exc.code,json.load(exc),exc.headers


def run():
    data=json.load(sys.stdin)
    if not isinstance(data,dict) or set(data)!=set(ACCOUNTS):raise ValueError('Unexpected accounts')
    if any(not isinstance(value,str) or not 12<=len(value)<=128 for value in data.values()):raise ValueError('Invalid passwords')
    store=PostgresStore()
    try:
        for company,email in ACCOUNTS.items():
            if memberships(store.db,email)!=[company]:raise ValueError('Unexpected membership')
            invite=create_invite(store.db,email)
            _,temporary=setup_password(store.db,invite,data[company])
            store.db.execute('delete from radar_team_sessions where token_digest=%s',(digest(temporary),))
            store.db.execute('update radar_account_invites set consumed_at=now() where email=%s and consumed_at is null',(email,))
            token=None
            try:
                code,_,headers=http('/api/team',body={'action':'password_login','email':email,'password':data[company]})
                if code!=200:raise ValueError('Password login failed')
                cookies=SimpleCookie();cookies.load(headers.get('Set-Cookie',''))
                token=cookies[COOKIE].value;cookie=COOKIE+'='+token
                code,session,_=http('/api/team?company='+company,cookie=cookie)
                if code!=200 or session.get('companies')!=[company]:raise ValueError('Unexpected account access')
                other='gerico' if company=='public' else 'public'
                if http('/api/opportunities?company='+company,cookie=cookie)[0]!=200:raise ValueError('Own catalog unavailable')
                if http('/api/opportunities?company='+other,cookie=cookie)[0]!=403:raise ValueError('Cross-company access allowed')
                if http('/api/team',body={'action':'logout'},cookie=cookie)[0]!=200:raise ValueError('Logout failed')
                if http('/api/opportunities',cookie=cookie)[0]!=401:raise ValueError('Session not revoked')
            finally:
                if token:store.db.execute('delete from radar_team_sessions where token_digest=%s',(digest(token),))
            private=Path('.local')/('acesso-'+company+'.html')
            if private.exists():
                import re
                text=private.read_text(encoding='utf-8')
                text=re.sub(r'/#setup=[A-Za-z0-9_-]{43}','/',text).replace('Criar minha senha e entrar','Entrar na minha conta').replace('Convite pessoal válido por 24 horas e utilizável uma única vez. Defina uma senha com pelo menos 12 caracteres.','Use a senha definida para esta empresa.')
                private.write_text(text,encoding='utf-8')
            data[company]=''
            print(json.dumps({'company':company,'passwordConfigured':True,'realPasswordLogin':True,'crossCompanyDenied':True,'logoutVerified':True,'emailSent':False}),flush=True)
    finally:store.close()


if __name__=='__main__':
    try:run()
    except Exception as exc:
        print(json.dumps({'activationFailed':type(exc).__name__}));raise SystemExit(1)
