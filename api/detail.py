"""Authorized evidence reads; refresh uses a fixed official PNCP destination."""
import json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from urllib.error import HTTPError, URLError

from radar.relevance import classify
from radar.company_access import request_access, AccessDenied, visible_card, review_card, COMPANIES
from radar.identifiers import parse_pncp_id
from radar.verification import fetch_record


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        query = parse_qs(urlparse(self.path).query)
        try:
            _, company, _ = request_access(self.headers.get('Cookie'), query.get('company', [None])[0])
        except AccessDenied as exc:
            self.respond(exc.status, {'error': str(exc)}); return
        except Exception:
            self.respond(503, {'error': 'Não foi possível verificar o acesso.'}); return
        try:
            identifier = parse_pncp_id(query.get('id', [''])[0]).canonical
        except ValueError:
            self.respond(400, {'error': 'Número PNCP inválido.'}); return
        metadata = query.get('metadata', [''])[0] == '1'
        reviewing = query.get('scope', [''])[0] == 'review'
        store = None
        try:
            from radar.postgres_store import PostgresStore
            from radar.profiles import profile_context
            from radar.enrichment import get_enrichment
            from radar.procurement_events import list_events
            store = PostgresStore()
            existing = store.db.execute('select payload from radar_opportunities where id=%s', (identifier,)).fetchone()
            if (reviewing or metadata) and not existing:
                self.respond(404, {'error': 'Contratação não encontrada no acervo oficial.'}); return
            row = existing[0] if metadata else fetch_record(identifier, timeout=12)
            if not metadata:
                store.write_records([row])
            with profile_context(store.db):
                classification = classify(row.get('objetoCompra') or '', row.get('informacaoComplementar') or '')
            saved = store.db.execute('''select offer from radar_review_state where company_id=%s and opportunity_id=%s
              and example_object=%s and example_additional=%s''',
                (company, identifier, row.get('objetoCompra') or '', row.get('informacaoComplementar') or '')).fetchone()
            rescued = saved and saved[0] == COMPANIES[company]
            decision = review_card(classification, company) if reviewing or rescued else visible_card(classification, company)
            if not decision:
                self.respond(404, {'error': 'A contratação não está no perfil desta empresa.'}); return
            review_history=store.db.execute('''select payload,created_at from radar_review_history
              where company_id=%s and opportunity_id=%s order by created_at desc,id desc limit 100''',
                (company,identifier)).fetchall()
            self.respond(200, {**decision, 'checkedAt': None if metadata else datetime.now(timezone.utc).isoformat(),
                'statusId': row.get('situacaoCompraId'), 'instrumentId': row.get('tipoInstrumentoConvocatorioCodigo'),
                'proposalDeadline': row.get('dataEncerramentoProposta') or '', 'proposalStart': row.get('dataAberturaProposta') or '',
                'object': row.get('objetoCompra') or '', 'additionalInfo': row.get('informacaoComplementar') or '',
                'sourceUrl': row.get('linkSistemaOrigem') or '', 'sourceSystem': row.get('usuarioNome') or '',
                'enrichment': get_enrichment(store.db, identifier, company),
                'procurementEvents': list_events(store.db, identifier),
                'reviewHistory': [{**payload,'createdAt':created.isoformat()} for payload,created in review_history],
                'cached': metadata})
        except (HTTPError, URLError, TimeoutError, ValueError, OSError):
            self.respond(502, {'error': 'Não foi possível atualizar. Consulte a fonte oficial ou tente novamente.'})
        except Exception:
            self.respond(503, {'error': 'A consulta está indisponível no momento.'})
        finally:
            if store: store.close()

    def respond(self, status, payload):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(json.dumps(payload, ensure_ascii=False).encode('utf-8'))
