"""Company managers may inspect public-source health; no operator mutation is exposed."""
import json
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs,urlparse
from radar.company_access import request_access,AccessDenied,can_manage_company


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        store=None
        try:
            email,company,_=request_access(self.headers.get('Cookie'),parse_qs(urlparse(self.path).query).get('company',[None])[0])
            from radar.postgres_store import PostgresStore
            from radar.source_health import health_report
            store=PostgresStore()
            if not can_manage_company(store.db,email,company):raise AccessDenied()
            self.respond(200,health_report(store))
        except AccessDenied as exc:self.respond(exc.status,{'error':str(exc)})
        except Exception:self.respond(503,{'error':'Não foi possível consultar as fontes. Tente novamente.'})
        finally:
            if store:store.close()
    def respond(self,status,payload):
        self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Cache-Control','private, no-store');self.send_header('Vary','Cookie');self.end_headers()
        self.wfile.write(json.dumps(payload,ensure_ascii=False).encode())
