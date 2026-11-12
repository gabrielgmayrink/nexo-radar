import json
import os
from http.server import BaseHTTPRequestHandler
from radar.catalog_storage import load_collection_status
from radar.company_access import request_access,AccessDenied


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        store=None
        try:
            request_access(self.headers.get('Cookie'))
            if os.environ.get('RADAR_CATALOG_STORE')=='supabase':
                from radar.postgres_store import PostgresStore
                store=PostgresStore();payload=load_collection_status(db=store.db)
            else:payload={'enabled':False,'collections':{},'executions':[]}
            status=200
        except AccessDenied as exc:
            payload,status={'error':str(exc)},exc.status
        except Exception:
            payload,status={'error':'Situação da atualização temporariamente indisponível.'},503
        finally:
            if store:store.close()
        body=json.dumps(payload,ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Cache-Control','private, no-store')
        self.send_header('Vary','Cookie')
        self.end_headers()
        self.wfile.write(body)
