"""Read-only catalog API for Vercel and the local Python server."""
import json
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import unicodedata
import os
from radar.catalog_storage import load_database_catalog

CATALOG = Path(__file__).resolve().parents[1] / "web" / "public" / "catalog.json"


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
            if os.environ.get('RADAR_CATALOG_STORE') == 'supabase':
                catalog=load_database_catalog(catalog)
            else:
                catalog['dataSource']='snapshot'
            query = parse_qs(urlparse(self.path).query)
            norm=lambda s: ''.join(c for c in unicodedata.normalize('NFKD',s.casefold()) if not unicodedata.combining(c))
            term = norm(query.get("q", [""])[0])
            offer = query.get("offer", [""])[0]
            rows = catalog.pop("opportunities")
            rows = [r for r in rows if (not term or term in norm(r["object"] + " " + r["organization"] + " " + r["city"])) and (not offer or r["suggestedOffer"] in (offer, "Ambas"))]
            try:
                page = max(1, int(query.get("page", ["1"])[0]))
                limit = min(100, max(1, int(query.get("limit", ["20"])[0])))
            except ValueError:
                self.respond(400, {"error": "Página e limite devem ser números inteiros."})
                return
            self.respond(200, {**catalog, "total": len(rows), "page": page, "opportunities": rows[(page-1)*limit:page*limit]})
        except (OSError, ValueError):
            self.respond(503, {"error": "Catálogo indisponível. Execute o processamento dos dados."})

    def respond(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "public, max-age=60" if status == 200 else "no-store")
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    from http.server import ThreadingHTTPServer
    ThreadingHTTPServer(("127.0.0.1", 8000), handler).serve_forever()
