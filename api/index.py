"""Read-only catalog API for Vercel and the local Python server."""
import json
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import os
from radar.catalog_storage import load_database_catalog
from radar.search import parse_query,matches_query
from radar.company_access import request_access,AccessDenied

CATALOG = Path(__file__).resolve().parents[1] / "web" / "public" / "catalog.json"


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        query = parse_qs(urlparse(self.path).query)
        try:
            page = max(1, int(query.get('page',['1'])[0]))
            limit = min(100, max(1, int(query.get('limit',['20'])[0])))
        except ValueError:
            self.respond(400,{'error':'Página e limite devem ser números inteiros.'});return
        try:
            _,company,_=request_access(self.headers.get('Cookie'),query.get('company',[None])[0])
            catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
            if os.environ.get('RADAR_CATALOG_STORE') == 'supabase':
                catalog=load_database_catalog(catalog,company=company)
            else:
                catalog['opportunities']=[]
                catalog['dataSource']='snapshot'
            clauses = parse_query(query.get('q',[''])[0])
            offer = query.get("offer", [""])[0]
            rows = catalog.pop("opportunities")
            rows = [r for r in rows if matches_query(r,clauses) and (not offer or r['suggestedOffer'] in (offer,'Ambas'))]
            bulk=query.get('bulk',['0'])[0]=='1'
            if bulk and len(rows)>10000:raise ValueError('Catalog budget exceeded')
            self.respond(200, {**catalog, 'total':len(rows),'page':1 if bulk else page,'opportunities':rows if bulk else rows[(page-1)*limit:page*limit]})
        except AccessDenied as exc:
            self.respond(exc.status,{'error':str(exc)})
        except Exception:
            self.respond(503, {"error": "Catálogo indisponível. Execute o processamento dos dados."})

    def respond(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "private, no-store")
        self.send_header('Vary','Cookie')
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    from http.server import ThreadingHTTPServer
    ThreadingHTTPServer(("127.0.0.1", 8000), handler).serve_forever()
