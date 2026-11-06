"""Fetch one current public PNCP record; destination is fixed, never user-supplied."""
import json
import re
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from radar.relevance import classify
from radar.company_access import request_access,AccessDenied,visible_card

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        query=parse_qs(urlparse(self.path).query)
        try:_,company,_=request_access(self.headers.get('Cookie'),query.get('company',[None])[0])
        except AccessDenied as exc:
            self.respond(exc.status,{'error':str(exc)});return
        except Exception:
            self.respond(503,{'error':'Não foi possível verificar o acesso.'});return
        identifier=query.get('id',[''])[0]
        match=re.fullmatch(r'(\d{14})-1-(\d{1,10})/(\d{4})',identifier)
        if not match:
            self.respond(400,{'error':'Número PNCP inválido.'}); return
        cnpj,seq,year=match.groups()
        url=f'https://pncp.gov.br/api/consulta/v1/orgaos/{cnpj}/compras/{year}/{int(seq)}'
        try:
            request=Request(url,headers={'User-Agent':'Mozilla/5.0 RadarLicitacoes/0.2','Accept':'application/json'})
            with urlopen(request,timeout=20) as response:
                raw=response.read(2_000_001)
            if len(raw)>2_000_000: raise ValueError('Response too large')
            row=json.loads(raw)
            decision=visible_card(classify(row.get('objetoCompra') or '',row.get('informacaoComplementar') or ''),company)
            if not decision:
                self.respond(404,{'error':'A contratação não está no perfil desta empresa.'});return
            self.respond(200,{**decision,'checkedAt':datetime.now(timezone.utc).isoformat(),'statusId':row.get('situacaoCompraId'),'instrumentId':row.get('tipoInstrumentoConvocatorioCodigo'),'proposalDeadline':row.get('dataEncerramentoProposta') or '', 'proposalStart':row.get('dataAberturaProposta') or '', 'object':row.get('objetoCompra') or '', 'additionalInfo':row.get('informacaoComplementar') or '', 'sourceUrl':row.get('linkSistemaOrigem') or ''})
        except (HTTPError,URLError,TimeoutError,ValueError,OSError):
            self.respond(502,{'error':'O PNCP não respondeu. Tente novamente ou confira o edital no portal.'})

    def respond(self,status,payload):
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Cache-Control','no-store')
        self.end_headers(); self.wfile.write(json.dumps(payload,ensure_ascii=False).encode('utf-8'))
