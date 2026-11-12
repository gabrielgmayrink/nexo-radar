"""Local-only acceptance server using real routes/SQL and a synthetic Auth provider.

Never loads dotenv. Requires a disposable radar_restore_test_* database on loopback.
The provider fixture is not a validation of Supabase Auth or external email delivery.
"""
import functools
import importlib
import json
import os
from pathlib import Path
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlparse
import uuid
import sys
import psycopg

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
TEST_PASSWORD='Homologacao-local@2026'


def main():
    dsn=os.environ.get('RADAR_TEST_POSTGRES_DSN','')
    options=psycopg.conninfo.conninfo_to_dict(dsn)
    if options.get('host') not in ('localhost','127.0.0.1') or not options.get('dbname','').startswith('radar_restore_test_'):
        raise ValueError('Only explicitly configured disposable local databases are accepted')
    os.environ.update(RADAR_APP_URL='http://localhost:8000',RADAR_TEAM_ENABLED='1',RADAR_EMAIL_ENABLED='0',
        RADAR_COLLECTION_ENABLED='0',RADAR_CATALOG_STORE='supabase',
        RADAR_TEAM_EMAILS='public.qa@example.com,gerico.qa@example.com,admin.qa@example.com')
    from radar import settings
    settings.app_url=lambda:'http://localhost:8000'
    from radar import postgres_store,password_auth
    from radar import team_auth
    # Local HTTP gets a different cookie name; production __Host-/Secure is unchanged.
    team_auth.COOKIE='radar_qa_session'
    team_auth.session_cookie=lambda token,clear=False:'radar_qa_session='+('' if clear else token)+'; Path=/; HttpOnly; SameSite=Strict; Max-Age='+('0' if clear else '604800')
    class LocalStore(postgres_store.PostgresStore):
        def __init__(self,**kwargs):super().__init__(psycopg.connect(dsn,autocommit=True,connect_timeout=5),**kwargs)
    postgres_store.PostgresStore=LocalStore
    def provider(path,payload,**kwargs):
        email=payload.get('email','')
        if path!='token?grant_type=password' or email not in os.environ['RADAR_TEAM_EMAILS'].split(',') or payload.get('password')!=TEST_PASSWORD:
            raise password_auth.AuthenticationFailed('Invalid local test credentials')
        return {'user':{'id':str(uuid.uuid5(uuid.NAMESPACE_DNS,email)),'email':email,'email_confirmed_at':'2026-11-11T00:00:00Z','factors':[]}}
    password_auth.password_login=functools.partial(password_auth.password_login,provider=provider)
    routes={name:importlib.import_module('api.'+module).handler for name,module in
            [('team','team'),('profile','profile'),('opportunities','index'),('detail','detail'),('status','status'),('health','health')]}
    class Router(SimpleHTTPRequestHandler):
        def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(ROOT/'web'/'dist'),**kwargs)
        def dispatch(self):
            path=urlparse(self.path).path
            if path=='/qa/mobile' and self.command=='GET':
                body=b'''<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>Homologacao responsiva local</title></head><body style="margin:0;background:#eee"><iframe title="Homologacao movel 390px" src="/" style="display:block;width:390px;height:844px;border:0"></iframe></body></html>'''
                self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.end_headers();self.wfile.write(body);return
            target=routes.get(path.removeprefix('/api/')) if path.startswith('/api/') else None
            if target:
                self.__class__=target
                getattr(target,'do_'+self.command)(self)
            elif path.startswith('/api/'):self.send_error(404)
            elif self.command=='GET':super().do_GET()
            else:self.send_error(405)
        do_GET=dispatch
        do_POST=dispatch
    print('LOCAL QA ONLY: http://localhost:8000; synthetic Auth; external delivery disabled',flush=True)
    ThreadingHTTPServer(('127.0.0.1',8000),Router).serve_forever()


if __name__=='__main__':main()
