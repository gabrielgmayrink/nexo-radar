import importlib.util
import sys
import unittest
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
