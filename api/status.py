import json
import os
from http.server import BaseHTTPRequestHandler
from radar.catalog_storage import load_collection_status


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            payload=load_collection_status() if os.environ.get('RADAR_CATALOG_STORE')=='supabase' else {'enabled':False,'collections':{},'executions':[]}
            status=200
        except Exception:
            payload,status={'error':'Situação da atualização temporariamente indisponível.'},503
        body=json.dumps(payload,ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Cache-Control','public, max-age=15' if status==200 else 'no-store')
        self.end_headers()
        self.wfile.write(body)
