"""Compras.gov.br documented read-only PNCP enrichment (not national coverage)."""
from urllib.parse import urlencode
from radar.identifiers import parse_pncp_id
from radar.sources.http import PublicHTTP, SourceError

BASE = 'https://dadosabertos.compras.gov.br/modulo-contratacoes/'


class ComprasGovConnector:
    source_id = 'compras_gov'

    def __init__(self, http=None):
        self.http = http or PublicHTTP()

    def _by_id(self, endpoint, identifier):
        identifier = parse_pncp_id(identifier).canonical
        url = BASE + endpoint + '?' + urlencode({'tipo': 'numeroControlePNCPCompra', 'codigo': identifier})
        result = self.http.json(url)
        if not isinstance(result, dict) or not isinstance(result.get('resultado'), list):
            raise SourceError('invalid_schema')
        rows = result['resultado']
        total = result.get('totalRegistros')
        if type(total) is not int or total != len(rows) or result.get('totalPaginas', 1) > 1:
            raise SourceError('incomplete_response')
        # Only exact official identifiers permit linking. Text similarity never merges.
        if any(not isinstance(r, dict) or
               (r.get('numeroControlePNCP') or r.get('numeroControlePNCPCompra')) != identifier for r in rows):
            raise SourceError('identity_mismatch')
        return rows, url

    def details(self, identifier):
        return self._by_id('1.1_consultarContratacoes_PNCP_14133_Id', identifier)

    def items(self, identifier):
        return self._by_id('2.1_consultarItensContratacoes_PNCP_14133_Id', identifier)
