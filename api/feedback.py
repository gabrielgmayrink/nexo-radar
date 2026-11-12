"""Signed feedback endpoint. Requires server-side Supabase configuration."""
import json
import os
from datetime import datetime,timezone
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs,urlparse
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError
from radar.feedback_security import verify_feedback, InvalidFeedbackToken
from radar.company_access import request_access,AccessDenied
from radar.mail import APP_URL,NoRedirect
from urllib.request import build_opener


def configured():
    return bool(os.environ.get('RADAR_SHARED_FEEDBACK_ENABLED') == '1' and os.environ.get('SUPABASE_URL') and (os.environ.get('SUPABASE_SECRET_KEY') or os.environ.get('SUPABASE_SERVICE_ROLE_KEY')) and len(os.environ.get('FEEDBACK_SIGNING_SECRET','').encode())>=32)


def save_feedback(claims: dict, *, opener=None) -> None:
    base=os.environ.get('SUPABASE_URL','').rstrip('/')
    parsed=urlparse(base)
    from radar.postgres_store import PROJECT_REF
    if base!='https://'+PROJECT_REF+'.supabase.co':
        raise ValueError('SUPABASE_URL inválida')
    key=os.environ.get('SUPABASE_SECRET_KEY') or os.environ['SUPABASE_SERVICE_ROLE_KEY']
    headers={'apikey':key,'Content-Type':'application/json','Prefer':'resolution=ignore-duplicates,return=minimal'}
    if key.startswith('eyJ'):
        headers['Authorization']='Bearer '+key
    payload={k:claims[k] for k in ('event_id','opportunity_id','product_id','label')}
    payload['created_at']=datetime.now(timezone.utc).isoformat()
    request=Request(base+'/rest/v1/radar_feedback?on_conflict=event_id',method='POST',data=json.dumps(payload).encode(),headers=headers)
    with (opener or build_opener(NoRedirect()).open)(request,timeout=20) as response:
        if response.status not in (200,201,204):
            raise ValueError('Falha ao salvar feedback')


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        token=parse_qs(urlparse(self.path).query).get('token',[''])[0]
        self.handle_feedback(token,write=False)

    def do_POST(self):
        if self.headers.get('Origin')!=APP_URL or self.headers.get('Content-Type','').split(';')[0]!='application/json':
            self.respond(403,{'error':'Origem não autorizada.'});return
        try:
            length=int(self.headers.get('Content-Length','0'))
            if length<1 or length>8192:
                self.respond(413,{'error':'Tamanho de solicitação inválido'});return
            payload=json.loads(self.rfile.read(length))
            if not isinstance(payload,dict):raise ValueError()
            token=payload.get('token','')
        except (ValueError,TypeError):
            self.respond(400,{'error':'Solicitação inválida'});return
        self.handle_feedback(token,write=True)

    def handle_feedback(self,token,*,write):
        if not configured():
            self.respond(503,{'error':'Revisão compartilhada ainda não configurada'});return
        try:
            claims=verify_feedback(token,os.environ['FEEDBACK_SIGNING_SECRET'])
        except InvalidFeedbackToken:
            self.respond(403,{'error':'Link inválido ou expirado'});return
        try:
            _,company,_=request_access(self.headers.get('Cookie'))
            if claims['product_id']!=company:raise AccessDenied()
            if write:save_feedback(claims)
            self.respond(200,{'saved':write,'opportunityId':claims['opportunity_id'],'productId':claims['product_id'],'label':claims['label']})
        except AccessDenied as exc:
            self.respond(exc.status,{'error':str(exc)})
        except Exception:
            self.respond(502,{'error':'Não foi possível salvar. Tente novamente.'})

    def respond(self,status,payload):
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Cache-Control','no-store')
        self.send_header('Referrer-Policy','no-referrer')
        self.end_headers();self.wfile.write(json.dumps(payload,ensure_ascii=False).encode())
