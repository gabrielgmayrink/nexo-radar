"""Only the notification workflow can send an allowlisted team digest."""
import json
from http.server import BaseHTTPRequestHandler


class RollbackProbe(Exception):pass


class handler(BaseHTTPRequestHandler):
    def do_GET(self):self.respond(405,{'error':'Use POST.'})
    def do_POST(self):
        from radar.job_auth import authenticate
        try:authenticate(self.headers.get('Authorization',''),purpose='notify')
        except Exception:
            self.respond(403,{'error':'Execução não autorizada.'});return
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 1<=length<=1024:raise ValueError()
            body=json.loads(self.rfile.read(length))
            if not isinstance(body,dict) or body.get('kind') not in ('weekly','urgent','test','verify'):raise ValueError()
        except (ValueError,TypeError):
            self.respond(400,{'error':'Parâmetros inválidos.'});return
        from radar.postgres_store import PostgresStore
        from radar.notifications import notify
        store=None
        try:
            store=PostgresStore()
            if body['kind']=='verify':
                def probe(records):
                    try:
                        with store.db.transaction():
                            store.write_records(records)
                            raise RollbackProbe()
                    except RollbackProbe:pass
                result=notify(store.db,'weekly',writer=probe,dry_run=True)
                self.respond(200,{**result,'databaseRolledBack':True})
            else:self.respond(200,notify(store.db,body['kind'],writer=store.write_records))
        except Exception as exc:
            print(json.dumps({'event':'notification_failed','errorType':type(exc).__name__}))
            self.respond(503,{'error':'Envio não concluído. Confira a coleta, a configuração e o registro de envios.'})
        finally:
            if store:store.close()
    def respond(self,status,payload):
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Cache-Control','no-store')
        self.end_headers();self.wfile.write(json.dumps(payload).encode())
