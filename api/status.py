import json
import os
from http.server import BaseHTTPRequestHandler
from radar.catalog_storage import load_collection_status
from radar.company_access import request_access,AccessDenied


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            request_access(self.headers.get('Cookie'))
            payload=load_collection_status() if os.environ.get('RADAR_CATALOG_STORE')=='supabase' else {'enabled':False,'collections':{},'executions':[]}
            status=200
        except AccessDenied as exc:
            payload,status={'error':str(exc)},exc.status
        except Exception:
            payload,status={'error':'Situação da atualização temporariamente indisponível.'},503
        body=json.dumps(payload,ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Cache-Control','private, no-store')
        self.send_header('Vary','Cookie')
        self.end_headers()
        self.wfile.write(body)
