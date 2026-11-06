from unittest.mock import patch
from profile_fixtures import TEST_PROFILES
import io
import json
import unittest
from unittest.mock import patch
from radar.catalog_storage import load_database_catalog


@patch('radar.profiles.load_profiles', lambda: TEST_PROFILES)
class StorageTests(unittest.TestCase):
    def test_database_cards_keep_source_collection_date(self):
        row={'numeroControlePNCP':'48031918000124-1-002720/2026','objetoCompra':'Licença de uso de plataforma de pesquisa de preços','orgaoEntidade':{'cnpj':'48031918000124'},'anoCompra':2026,'sequencialCompra':2720}
        requests=[]
        def opener(request,**kwargs):
            requests.append(request)
            data=[{'payload':row}] if 'radar_opportunities?' in request.full_url else []
            return io.BytesIO(json.dumps(data).encode())
        with patch.dict('os.environ',{'SUPABASE_URL':'https://unit-test.supabase.co','SUPABASE_SECRET_KEY':'unit-test-only'},clear=True):
            result=load_database_catalog({'collectionDate':'2026-11-03','metrics':{'unique':92965}},opener=opener)
        self.assertEqual(result['collectionDate'],'2026-11-03')
        self.assertEqual(result['dataSource'],'supabase')
        self.assertEqual(result['opportunities'][0]['suggestedOffer'],'Public')
        self.assertNotIn('unit-test-only',json.dumps(result))
        self.assertIn('offset=0',requests[0].full_url)
        self.assertIn('score=gte.40',requests[0].full_url)
        self.assertIn('select=card&',requests[0].full_url)
        self.assertNotIn('select=payload',requests[0].full_url)

    def test_only_completed_publication_run_advances_date(self):
        def opener(request,**kwargs):
            if 'radar_catalog_state?' in request.full_url:
                data=[{'id':'publications','content':{'window':{'end':'2026-11-05'},'completedAt':'2026-11-05T12:00:00Z','metrics':{'unique':100000}}}]
            elif 'radar_executions?' in request.full_url:
                data=[{'id':2,'task':'sync:open','status':'partial','started_at':'2026-11-05T13:00:00Z','metrics':{'pages':7}}]
            else:data=[]
            return io.BytesIO(json.dumps(data).encode())
        with patch.dict('os.environ',{'SUPABASE_URL':'https://unit-test.supabase.co','SUPABASE_SECRET_KEY':'unit-test-only'},clear=True):
            result=load_database_catalog({'collectionDate':'2026-11-03','metrics':{'unique':92965}},opener=opener)
        self.assertEqual(result['collectionDate'],'2026-11-05')
        self.assertEqual(result['metrics']['unique'],100000)
        self.assertFalse(result['historical'])
        self.assertEqual(result['sync']['executions'][0]['status'],'partial')

    def test_invalid_destination_rejected_before_http(self):
        with patch.dict('os.environ',{'SUPABASE_URL':'https://example.com','SUPABASE_SECRET_KEY':'unit-test-only'},clear=True):
            with self.assertRaises(ValueError):load_database_catalog({})

    def test_collection_status_does_not_export_global_company_selection_totals(self):
        from radar.catalog_storage import load_collection_status
        def opener(request,**kwargs):
            rows=[{'id':'publications','content':{'window':{'end':'2026-11-06'},'metrics':{'unique':2000,'candidates':99,'discarded':1901},'companySelections':{'Gerico':50}}}] if 'radar_catalog_state?' in request.full_url else []
            return io.BytesIO(json.dumps(rows).encode())
        with patch.dict('os.environ',{'SUPABASE_URL':'https://unit-test.supabase.co','SUPABASE_SECRET_KEY':'unit-test-only'},clear=True):
            result=load_collection_status(opener=opener)
        self.assertEqual(result['collections']['publications']['metrics'],{'unique':2000})
        self.assertNotIn('companySelections',json.dumps(result))

    def test_public_status_exposes_only_known_error_labels(self):
        from radar.catalog_storage import load_collection_status
        for error,expected in [('http_429','http_429'),('storage_guard','storage_guard'),('private diagnostic containing credentials',None)]:
            def opener(request,**kwargs):
                data=[{'id':1,'task':'sync:open','status':'partial','started_at':'2026-11-05T12:00:00Z','metrics':{'error':error}}] if 'radar_executions?' in request.full_url else []
                return io.BytesIO(json.dumps(data).encode())
            with patch.dict('os.environ',{'SUPABASE_URL':'https://unit-test.supabase.co','SUPABASE_SECRET_KEY':'unit-test-only'},clear=True):
                status=load_collection_status(opener=opener)
            self.assertEqual(status['executions'][0]['error'],expected)
            self.assertNotIn('private diagnostic',json.dumps(status))
