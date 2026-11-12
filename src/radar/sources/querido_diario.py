"""Documented complementary gazette search. Disabled until live API validation.

Results are evidence candidates, never procurement records by text similarity.
"""
from datetime import date
from urllib.parse import urlencode
from radar.sources.http import PublicHTTP, SourceError


class QueridoDiarioConnector:
    source_id = 'querido_diario'

    def __init__(self, http=None):
        self.http = http or PublicHTTP(pause=1.1)

    def search(self, query, since, until, *, offset=0, size=10):
        if not isinstance(query, str) or not 3 <= len(query) <= 200 or offset < 0 or not 1 <= size <= 100:
            raise ValueError('Invalid gazette query')
        date.fromisoformat(since); date.fromisoformat(until)
        params = {'querystring': query, 'published_since': since, 'published_until': until,
                  'offset': offset, 'size': size, 'excerpt_size': 500, 'number_of_excerpts': 1}
        url = 'https://api.queridodiario.ok.org.br/gazettes?' + urlencode(params)
        result = self.http.json(url)
        if not isinstance(result, dict) or not isinstance(result.get('gazettes'), list):
            raise SourceError('invalid_schema')
        return {'rows': result['gazettes'], 'url': url, 'total': result.get('total_gazettes'),
                'nextOffset': offset + size if len(result['gazettes']) == size else None,
                'identityStatus': 'requires_official_identity_confirmation'}
