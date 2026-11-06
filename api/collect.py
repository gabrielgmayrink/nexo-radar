"""A bounded collection batch, callable only by this repository's scheduled job."""
import json
import os
import time
from http.server import BaseHTTPRequestHandler


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.respond(405, {'error': 'Use POST.'})

    def do_POST(self):
        started=time.monotonic()
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
            if not 1 <= length <= 3_500_000:
                raise ValueError('Invalid request size')
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):raise ValueError('Invalid request')
            national=body.get('action') in ('national_plan','national_commit','national_failure','national_reconcile')
            maintenance=body.get('action') in ('cleanup','weekly_summary')
            if 'action' in body and not (national or maintenance):raise ValueError('Invalid operation')
            if maintenance and type(body.get('dryRun',False)) is not bool:raise ValueError('Invalid preview')
            if not national and body.get('kind', 'incremental') not in ('incremental', 'open', 'backfill'):
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
        from radar.national_collection import handle_national,StalePage
        store = None
        try:
            store = PostgresStore()
            if maintenance:
                from radar.catalog_maintenance import cleanup,weekly_summary
                if body['action']=='weekly_summary' and os.environ.get('RADAR_EMAIL_ENABLED')!='1':
                    self.respond(503,{'error':'Resumos não habilitados.'});return
                result=cleanup(store,dry_run=body.get('dryRun',False),run_key=run_key) if body['action']=='cleanup' else weekly_summary(store,run_key,dry_run=body.get('dryRun',False))
                print(json.dumps({'event':'catalog_maintenance','task':body['action'],'done':result.get('done'),
                                  'removedFromActive':result.get('removedFromActive'),'receiverMs':round((time.monotonic()-started)*1000)}))
                self.respond(200,result);return
            result = handle_national(store,body['action'],body,run_key) if national else run_chunk(store, body.get('kind', 'incremental'), run_key=run_key,
                                                                                              execution_id=execution_id, budget_seconds=budget_seconds)
            if national and body['action']=='national_commit':
                print(json.dumps({'event':'national_page_received','page':body.get('page'),
                                  'sourceMs':body.get('sourceMs'),'receiverMs':round((time.monotonic()-started)*1000),
                                  'region':os.environ.get('VERCEL_REGION')}))
            self.respond(200, result)
        except StalePage:
            self.respond(409,{'error':'A página já avançou. Consulte o progresso atual.'})
        except ValueError as exc:
            label='storage_guard' if str(exc)=='storage_guard' else 'invalid_page'
            print(json.dumps({'event':'collection_rejected','error':label}))
            self.respond(400,{'error':label})
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
