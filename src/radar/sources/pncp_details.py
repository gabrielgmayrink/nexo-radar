"""PNCP documented item/document reads, resumable one page at a time."""
from urllib.parse import urlencode, urlparse
from radar.identifiers import parse_pncp_id
from radar.sources.http import PublicHTTP, SourceError, validate_url

BASE = 'https://pncp.gov.br/api/pncp/v1/orgaos/'


def purchase_path(identifier):
    value = parse_pncp_id(identifier)
    return f'{value.cnpj}/compras/{value.year}/{int(value.sequence)}'


def document_url(identifier, url):
    validate_url(url)
    parsed = urlparse(url)
    paths = [base + purchase_path(identifier) + '/arquivos/'
             for base in ('/api/pncp/v1/orgaos/', '/pncp-api/v1/orgaos/')]
    path = next((prefix for prefix in paths if parsed.path.startswith(prefix)), None)
    # File API is fixed to this procurement; external origin URLs stay links only.
    if parsed.hostname != 'pncp.gov.br' or not path or parsed.query:
        raise SourceError('document_destination_blocked')
    suffix = parsed.path[len(path):]
    if not suffix.isdigit():
        raise SourceError('document_destination_blocked')
    return url


class PNCPDetailsConnector:
    source_id = 'pncp'

    def __init__(self, http=None):
        self.http = http or PublicHTTP()

    def page(self, identifier, kind, page=1, size=50):
        if kind not in ('itens', 'arquivos') or type(page) is not int or page < 1 or not 1 <= size <= 100:
            raise ValueError('Invalid detail page')
        url = BASE + purchase_path(identifier) + '/' + kind
        if kind == 'itens':
            url += '?' + urlencode({'pagina': page, 'tamanhoPagina': size})
        elif page != 1:
            raise ValueError('Document manifest is a single response')
        rows = self.http.json(url)
        if not isinstance(rows, list) or (kind == 'itens' and len(rows) > size) or any(not isinstance(r, dict) for r in rows):
            raise SourceError('invalid_schema')
        return {'rows': rows, 'url': url, 'nextPage': page + 1 if kind == 'itens' and len(rows) == size else None}

    def download(self, identifier, url):
        return self.http.read(document_url(identifier, url), max_bytes=3 * 1024 * 1024, timeout=8, attempts=1)
