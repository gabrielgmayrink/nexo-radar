"""Private company configuration. No browser-chosen identity or role is trusted."""
import json
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs,urlparse
from radar.company_access import resolve_access,AccessDenied
from radar.company_profiles import get_profile,save_profile,ProfileConflict
from radar.postgres_store import PostgresStore
from radar.mail import APP_URL
from radar.team_auth import session_token

class handler(BaseHTTPRequestHandler):
    def do_GET(self):self.handle_profile(False)
    def do_POST(self):self.handle_profile(True)
    def handle_profile(self,write):
        store=None
        try:
            query=parse_qs(urlparse(self.path).query)
            if write:
                if self.headers.get('Origin')!=APP_URL or self.headers.get('Content-Type','').split(';')[0]!='application/json':raise AccessDenied()
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=100_000:raise ValueError('Invalid body size')
                data=json.loads(self.rfile.read(length))
            if not session_token(self.headers.get('Cookie')):raise AccessDenied(401)
            store=PostgresStore()
            email,company,_=resolve_access(store.db,self.headers.get('Cookie'),query.get('company',[None])[0])
            result=save_profile(store.db,company,email,data) if write else get_profile(store.db,company,email)
            self.respond(200,result)
        except AccessDenied as exc:self.respond(exc.status,{'error':str(exc)})
        except ProfileConflict:self.respond(409,{'error':'O perfil foi alterado por outra pessoa. Recarregue antes de salvar.'})
        except (ValueError,TypeError):self.respond(400,{'error':'Confira os critérios e os limites informados.'})
        except Exception:self.respond(503,{'error':'Não foi possível consultar o perfil da empresa.'})
        finally:
            if store:store.close()
    def respond(self,status,payload):
        self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Cache-Control','private, no-store');self.send_header('Vary','Cookie');self.end_headers()
        self.wfile.write(json.dumps(payload,ensure_ascii=False).encode())
