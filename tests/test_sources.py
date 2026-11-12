import io
import json
import unittest
from unittest.mock import Mock

from radar.sources.http import PublicHTTP, SourceError, validate_url, retry_delay
from radar.sources.compras import ComprasGovConnector
from radar.sources.pncp_details import PNCPDetailsConnector, document_url
from radar.enrichment import _items
from radar.enrichment import _execute
import hashlib

ID = '00394502000144-1-010615/2025'


class FakeResponse(io.BytesIO):
    def __init__(self, body, url):
        super().__init__(body)
        self.headers = {}
        self.url = url

    def geturl(self): return self.url


class SourceTests(unittest.TestCase):
    def test_destinations_are_fixed_and_redirects_cannot_exfiltrate(self):
        for url in ('http://pncp.gov.br/x', 'https://localhost/x', 'https://pncp.gov.br.evil/x',
                    'https://pncp.gov.br@127.0.0.1/x', 'https://pncp.gov.br:8443/x'):
            with self.subTest(url=url), self.assertRaises(SourceError): validate_url(url)
        http = PublicHTTP(opener=Mock(open=lambda *a, **k: FakeResponse(b'{}', 'https://localhost/secret')))
        with self.assertRaisesRegex(SourceError, 'redirect_blocked'):
            http.json('https://pncp.gov.br/x')

    def test_raw_response_is_recorded_before_schema_failure(self):
        saved = []
        url = 'https://pncp.gov.br/x'
        http = PublicHTTP(opener=Mock(open=lambda *a, **k: FakeResponse(b'not-json', url)),
                          recorder=lambda u, b: saved.append((u, b)))
        with self.assertRaisesRegex(SourceError, 'invalid_json'): http.json(url)
        self.assertEqual(saved, [(url, b'not-json')])

    def test_no_silent_partial_response(self):
        fake = Mock(json=lambda u: {'resultado': [{'numeroControlePNCP': ID}], 'totalRegistros': 2, 'totalPaginas': 1})
        with self.assertRaisesRegex(SourceError, 'incomplete_response'): ComprasGovConnector(fake).details(ID)

    def test_similar_object_does_not_link_another_procurement(self):
        fake = Mock(json=lambda u: {'resultado': [{'numeroControlePNCP': '00394502000144-1-010616/2025'}], 'totalRegistros': 1})
        with self.assertRaisesRegex(SourceError, 'identity_mismatch'): ComprasGovConnector(fake).details(ID)

    def test_items_use_documented_identity_field(self):
        rows = [{'numeroControlePNCPCompra': ID, 'numeroItemPncp': 1, 'descricaodetalhada': 'Realização de curso EAD'}]
        fake = Mock(json=lambda u: {'resultado': rows, 'totalRegistros': 1, 'totalPaginas': 1})
        received, url = ComprasGovConnector(fake).items(ID)
        self.assertIn('numeroControlePNCPCompra', url)
        self.assertEqual(list(_items('compras_gov', received))[0]['description'], 'Realização de curso EAD')

    def test_item_pages_resume_until_terminal_page(self):
        fake = Mock(json=lambda u: [{'numeroItem': 1}] * 50)
        self.assertEqual(PNCPDetailsConnector(fake).page(ID, 'itens')['nextPage'], 2)
        fake.json = lambda u: []
        self.assertIsNone(PNCPDetailsConnector(fake).page(ID, 'itens', 2)['nextPage'])

    def test_attachment_is_bound_to_the_official_procurement(self):
        valid = 'https://pncp.gov.br/api/pncp/v1/orgaos/00394502000144/compras/2025/10615/arquivos/1'
        self.assertEqual(document_url(ID, valid), valid)
        for url in (valid.replace('/10615/', '/10616/'), valid + '/../../x', 'https://example.com/a.pdf'):
            with self.assertRaises(SourceError): document_url(ID, url)

    def test_retry_after_does_not_get_ignored(self):
        self.assertEqual(retry_delay({'Retry-After': '120'}), 120)

    def test_repeated_detail_page_is_not_marked_complete(self):
        rows=[{'numeroItem':1,'descricao':'Curso EAD'}]*50
        fingerprint=hashlib.sha256(json.dumps(rows,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        job={'opportunity':ID,'task':'pncp_items','cursor':{'page':2,'lastPageHash':fingerprint}}
        with self.assertRaisesRegex(SourceError,'repeated_detail_page'):
            _execute(Mock(),job,Mock(json=lambda *a,**k:rows))


if __name__ == '__main__': unittest.main()
