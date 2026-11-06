import importlib.util
import sys
import unittest
import gzip
import io
import json
import http.client
from pathlib import Path
from unittest.mock import patch
from test_national_collection import Store,payload
from radar.national_collection import handle_national

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import run_national_collection as worker


class Receiver:
    def __init__(self):self.store=Store()
    def post(self,body):return handle_national(self.store,body['action'],body,'run')


class Source:
    def __init__(self,total):self.total=total;self.pages=[]
    def fetch(self,page):self.pages.append(page);return payload(page,self.total)


class WorkerTests(unittest.TestCase):
    def test_worker_collects_all_pages_without_old_record_caps(self):
        receiver=Receiver();source=Source(10001)
        with patch.object(worker,'write_summary') as summary,patch('builtins.print'):
            result=worker.run(budget_seconds=120,receiver=receiver,source=source)
        self.assertEqual(result,0);self.assertEqual(len(receiver.store.rows),10001)
        self.assertEqual(set(source.pages),set(range(1,202)))
        self.assertTrue(summary.call_args.args[1])

    def test_source_plan_cannot_add_business_or_location_filters(self):
        good={'path':worker.SOURCE_PATH,'page':1,'query':{'dataFinal':'99991231','pagina':1,'tamanhoPagina':50}}
        self.assertEqual(worker.validate_plan(good),good)
        for invalid in ({**good,'path':'https://example.com'}, {**good,'query':{**good['query'],'uf':'MG'}},
                        {**good,'query':{**good['query'],'codigoModalidadeContratacao':6}}):
            with self.assertRaises(ValueError):worker.validate_plan(invalid)

    def test_timeout_preserves_checkpoint_and_reports_incomplete(self):
        receiver=Receiver()
        class TimeoutSource:
            def fetch(self,page):raise worker.PNCPError('timeout')
        with patch.object(worker,'write_summary') as summary,patch('builtins.print'):
            worker.run(budget_seconds=120,receiver=receiver,source=TimeoutSource())
        self.assertFalse(summary.call_args.args[1]);self.assertEqual(receiver.store.rows,{})
        self.assertEqual(receiver.store.cursor['status'],'partial')

    def test_source_reuses_connection_and_decodes_gzip(self):
        original=json.dumps(payload(1,total=1)).encode()
        class Connection:
            closed=False
            requests=[]
            def request(self,*args,**kwargs):self.requests.append(kwargs['headers'])
            def getresponse(self):
                return worker.BufferedResponse(gzip.compress(original),200,{'Content-Type':'application/json','Content-Encoding':'gzip'})
            def close(self):self.closed=True
        source=worker.Source();connection=Connection();source.local.connection=connection
        request=worker.Request('https://pncp.gov.br/api/consulta'+worker.SOURCE_PATH+'?pagina=1')
        with patch.dict('os.environ',{},clear=True):
            for _ in range(2):
                with source.open(request,60) as response:self.assertEqual(response.read(),original)
        self.assertEqual(len(connection.requests),2);self.assertFalse(connection.closed)
        self.assertEqual(connection.requests[0]['Accept-Encoding'],'gzip')

    def test_invalid_source_destinations_are_never_requested(self):
        source=worker.Source()
        with self.assertRaises(ValueError):source.open(worker.Request('https://example.com/api/consulta'+worker.SOURCE_PATH),60)

    def test_broken_persistent_connection_is_closed_before_retry(self):
        class Connection:
            closed=False
            def request(self,*args,**kwargs):raise http.client.RemoteDisconnected('closed')
            def close(self):self.closed=True
        source=worker.Source();connection=Connection();source.local.connection=connection
        with patch.dict('os.environ',{},clear=True):
            with self.assertRaises(worker.URLError):source.open(worker.Request('https://pncp.gov.br/api/consulta'+worker.SOURCE_PATH),60)
        self.assertTrue(connection.closed);self.assertIsNone(source.local.connection)
