"""A bounded collection batch, callable only by this repository's scheduled job."""
import json
import os
from http.server import BaseHTTPRequestHandler


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.respond(405, {'error': 'Use POST.'})

    def do_POST(self):
        from radar.job_auth import authenticate
        try:
            run_key = authenticate(self.headers.get('Authorization', ''))
        except Exception:
            self.respond(403, {'error': 'Execução não autorizada.'})
            return
        if os.environ.get('RADAR_COLLECTION_ENABLED') != '1':
            self.respond(503, {'error': 'Coleta automática não habilitada.'})
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 1 <= length <= 4096:
                raise ValueError('Invalid request size')
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict) or body.get('kind', 'incremental') not in ('incremental', 'open', 'backfill'):
                raise ValueError('Invalid request')
            execution_id = body.get('executionId')
            if execution_id is not None and (type(execution_id) is not int or execution_id < 1):
                raise ValueError('Invalid execution')
            budget_seconds = body.get('budgetSeconds', 140)
            if type(budget_seconds) is not int or not 10 <= budget_seconds <= 140:
                raise ValueError('Invalid batch budget')
        except (ValueError, TypeError):
            self.respond(400, {'error': 'Parâmetros inválidos.'})
            return
        from radar.postgres_store import PostgresStore
        from radar.sync import run_chunk
        store = None
        try:
            store = PostgresStore()
            result = run_chunk(store, body.get('kind', 'incremental'), run_key=run_key,
                               execution_id=execution_id, budget_seconds=budget_seconds)
            self.respond(200, result)
        except Exception as exc:
            # PostgreSQL exceptions can include passwords/DSNs: report type only in server logs.
            print(json.dumps({'event': 'collection_failed', 'errorType': type(exc).__name__}))
            self.respond(503, {'error': 'Coleta interrompida. O progresso salvo será retomado.'})
        finally:
            if store:
                store.close()

    def respond(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        if status == 405:
            self.send_header('Allow', 'POST')
        self.end_headers()
        self.wfile.write(body)
