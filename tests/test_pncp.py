from datetime import date
import json
import unittest

from radar.collector import _query_for
from radar.contract import endpoint_contract
from radar.pncp import CollectionMetrics, PNCPClient, PNCPError, date_range, page_count
from radar.report import render_markdown


class Response:
    status = 200
    headers = {"Content-Type": "application/json"}

    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


class EmptyResponse(Response):
    status = 204

    def read(self):
        return b""


class PNCPTests(unittest.TestCase):
    def test_publication_query_has_date_window_and_required_modality(self):
        query = _query_for("publicacao", 8, date(2026, 10, 5), date(2026, 11, 3))
        self.assertEqual(query["dataInicial"], "20261005")
        self.assertEqual(query["dataFinal"], "20261103")
        self.assertEqual(query["codigoModalidadeContratacao"], 8)
        self.assertEqual(query["tamanhoPagina"], 50)

    def test_open_proposal_query_uses_cutoff_date(self):
        query = _query_for("proposta_aberta", 8, date(2026, 10, 5), date(2026, 11, 3))
        self.assertEqual(query["dataFinal"], "20271103")
        self.assertNotIn("dataInicial", query)

    def test_page_count_supports_total_pages_and_short_page(self):
        self.assertEqual(page_count({"totalPaginas": 4}, 50, 50), 4)
        self.assertEqual(page_count({}, 3, 50), 0)
        self.assertIsNone(page_count({}, 50, 50))

    def test_page_count_supports_remaining_pages(self):
        self.assertEqual(page_count({"numeroPagina": 2, "paginasRestantes": 3}, 50, 50), 5)

    def test_date_range_is_inclusive(self):
        self.assertEqual(date_range(30, date(2026, 11, 3)), (date(2026, 10, 5), date(2026, 11, 3)))

    def test_metrics_records_latency_and_status(self):
        metrics = CollectionMetrics()
        client = PNCPClient(opener=lambda *a, **k: Response({"data": [{"id": 1}]}), pause_seconds=0)
        payload = client.get_page("/test", {"pagina": 1}, modality=8, page=1, metrics=metrics)
        self.assertEqual(len(payload["data"]), 1)
        self.assertEqual(metrics.summary()["http_statuses"], {"200": 1})
        self.assertGreaterEqual(metrics.summary()["latency_ms"]["max"], 0)

    def test_unexpected_response_contract_is_reported(self):
        metrics = CollectionMetrics()
        client = PNCPClient(opener=lambda *a, **k: Response({"items": []}), pause_seconds=0, retries=0)
        with self.assertRaisesRegex(PNCPError, "contrato_resposta_sem_lista_data"):
            client.get_page("/test", {}, modality=8, page=1, metrics=metrics)
        self.assertEqual(metrics.requests[0].error, "contrato_resposta_sem_lista_data")

    def test_http_204_is_a_valid_empty_collection(self):
        metrics = CollectionMetrics()
        client = PNCPClient(opener=lambda *a, **k: EmptyResponse({}), pause_seconds=0)
        payload = client.get_page("/test", {}, modality=7, page=1, metrics=metrics)
        self.assertEqual(payload, {"data": []})
        self.assertEqual(metrics.summary()["http_statuses"], {"204": 1})
        self.assertEqual(metrics.summary()["errors"], {})

    def test_contract_parser_preserves_required_and_bounds(self):
        spec = {"paths": {"/x": {"get": {"parameters": [
            {"name": "tamanhoPagina", "required": False, "schema": {"minimum": 10, "maximum": 50}},
        ]}}}}
        self.assertEqual(endpoint_contract(spec, "/x")[0]["maximum"], 50)

    def test_report_marks_partial_partitions(self):
        text = render_markdown({
            "window": {"start": "2026-10-05", "end": "2026-11-03", "days": 30},
            "modalities": [8],
            "elapsed_seconds": 1,
            "metrics": {"requests": 2, "retries": 0, "latency_ms": {"mean": 2, "p95": 2, "max": 2}, "errors": {}, "http_statuses": {"200": 2}},
            "endpoints": {"publicacao": {"8": {"status": "partial", "pages": 1, "records": 2}}},
            "unique": {},
            "failures": [{"endpoint": "publicacao", "modality": 8, "page": 2, "error": "http_503"}],
        })
        self.assertIn("http_503", text)
        self.assertIn("publicacao", text)


if __name__ == "__main__":
    unittest.main()
