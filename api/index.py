"""Authenticated server-side pages; never download the national catalog to the browser."""
import json
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse,parse_qs
from radar.catalog_query import options,load_catalog_page
from radar.company_access import resolve_access,AccessDenied
from radar.postgres_store import PostgresStore
from radar.team_auth import session_token

CATALOG=Path(__file__).resolve().parents[1]/'web'/'public'/'catalog.json'

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        query=parse_qs(urlparse(self.path).query);store=None
        try:
            options(query)
            if query.get('bulk',['0'])[0]=='1':raise ValueError('Use paginated requests')
        except (ValueError,TypeError,OverflowError):
            self.respond(400,{'error':'Confira a página, os filtros e o limite (1 a 100). A consulta usa paginação.'});return
        try:
            if not session_token(self.headers.get('Cookie')):raise AccessDenied(401)
            store=PostgresStore()
            _,company,_=resolve_access(store.db,self.headers.get('Cookie'),query.get('company',[None])[0])
            snapshot=json.loads(CATALOG.read_text(encoding='utf-8'))
            self.respond(200,load_catalog_page(snapshot,company,query,store.db))
        except AccessDenied as exc:self.respond(exc.status,{'error':str(exc)})
        except Exception:self.respond(503,{'error':'Catálogo indisponível. Tente novamente em instantes.'})
        finally:
            if store:store.close()

    def respond(self,status,payload):
        self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Cache-Control','private, no-store');self.send_header('Vary','Cookie');self.end_headers()
        self.wfile.write(json.dumps(payload,ensure_ascii=False).encode())

if __name__=='__main__':
    from http.server import ThreadingHTTPServer
    ThreadingHTTPServer(('127.0.0.1',8000),handler).serve_forever()
