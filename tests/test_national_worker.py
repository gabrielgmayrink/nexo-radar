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
            result=worker.run(budget_seconds=120,receiver=receiver,source=TimeoutSource())
        self.assertEqual(result,2)
        self.assertFalse(summary.call_args.args[1]);self.assertEqual(receiver.store.rows,{})
        self.assertEqual(receiver.store.cursor['status'],'partial')

    def test_temporary_source_server_error_is_not_a_completed_scan(self):
        receiver=Receiver()
        class ServerErrorSource:
            def fetch(self,page):raise worker.PNCPError('http_503')
        with patch.object(worker,'write_summary') as summary,patch('builtins.print'):
            worker.run(budget_seconds=120,receiver=receiver,source=ServerErrorSource())
        self.assertFalse(summary.call_args.args[1]);self.assertEqual(receiver.store.cursor['error'],'source_5xx')

    def test_incomplete_attempt_resumes_and_completes_in_the_same_job(self):
        with patch.object(worker,'run',side_effect=[2,0]) as run,patch.object(worker.time,'sleep') as sleep,patch('builtins.print'):
            self.assertEqual(worker.run_with_resume(budget_seconds=5400),0)
        self.assertEqual(run.call_count,2)
        sleep.assert_called_once_with(60)

    def test_exhausted_resume_budget_does_not_report_success(self):
        with patch.object(worker,'run',return_value=2) as run,patch.object(worker.time,'sleep'),patch('builtins.print'):
            self.assertEqual(worker.run_with_resume(budget_seconds=5400),2)
        self.assertEqual(run.call_count,3)

    def test_fatal_failure_and_short_diagnostics_are_not_automatically_repeated(self):
        for budget,result in ((5400,1),(120,2)):
            with self.subTest(budget=budget),patch.object(worker,'run',return_value=result) as run,patch.object(worker.time,'sleep') as sleep:
                self.assertEqual(worker.run_with_resume(budget_seconds=budget),result)
                run.assert_called_once_with(budget_seconds=budget)
                sleep.assert_not_called()

    def test_persisted_source_retry_delay_prevents_new_fetches(self):
        receiver=Receiver();source=Source(100)
        receiver.post({'action':'national_plan'})
        receiver.store.cursor['next_attempt_at']='2099-01-01T00:00:00+00:00'
        with patch.object(worker,'write_summary'),patch('builtins.print'):
            self.assertEqual(worker.run(budget_seconds=120,receiver=receiver,source=source),2)
        self.assertEqual(source.pages,[])

    def test_last_retry_preserves_the_source_retry_after(self):
        receiver=Receiver()
        class RateLimitedSource:
            def fetch(self,page):raise worker.PNCPError('http_429',retry_after_seconds=3600)
        with patch.object(worker,'write_summary'),patch('builtins.print'):
            self.assertEqual(worker.run(budget_seconds=120,receiver=receiver,source=RateLimitedSource()),2)
        self.assertEqual(receiver.store.cursor['error'],'http_429')
        self.assertIn('next_attempt_at',receiver.store.cursor)

    def test_decreasing_national_page_count_does_not_trap_the_worker(self):
        receiver=Receiver()
        class ChangingSource:
            calls=0
            def fetch(self,page):
                self.calls+=1
                if self.calls==1:return payload(1,total=60)
                if page>1:raise worker.PNCPError('http_400')
                return payload(1,total=40)
        with patch.object(worker,'write_summary') as summary,patch('builtins.print'):
            worker.run(budget_seconds=120,receiver=receiver,source=ChangingSource())
        self.assertTrue(summary.call_args.args[1]);self.assertEqual(summary.call_args.args[0]['uniqueRecords'],40)

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
