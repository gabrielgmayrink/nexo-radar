import io
import json
import unittest
from unittest.mock import Mock,patch
from api.collect import handler


class CollectActionsTests(unittest.TestCase):
    def request(self,body):
        request=handler.__new__(handler)
        raw=json.dumps(body).encode()
        request.rfile=io.BytesIO(raw);request.headers={'Content-Length':str(len(raw)),'Authorization':'Bearer unit-test'}
        request.respond=Mock()
        return request

    def test_independent_health_identity_is_read_only_even_when_collection_paused(self):
        request=self.request({'action':'health'})
        store=Mock();report={'health':{'ok':True},'sources':[]}
        with patch.dict('os.environ',{},clear=True),patch('radar.job_auth.authenticate',return_value='run') as auth,patch('radar.postgres_store.PostgresStore',return_value=store),patch('radar.source_health.health_report',return_value=report) as health:
            request.do_POST()
        auth.assert_called_once_with('Bearer unit-test',purpose='health');health.assert_called_once_with(store)
        request.respond.assert_called_once_with(200,report);store.close.assert_called_once()

    def test_health_token_cannot_be_used_for_mutable_actions(self):
        request=self.request({'action':'quarantine'})
        with patch('radar.job_auth.authenticate',side_effect=ValueError()) as auth,patch('radar.postgres_store.PostgresStore') as store:
            request.do_POST()
        auth.assert_called_once_with('Bearer unit-test',purpose='collect');store.assert_not_called()
        self.assertEqual(request.respond.call_args.args[0],403)

    def test_unknown_action_rejected_before_database_access(self):
        request=self.request({'action':'arbitrary_sql'})
        with patch.dict('os.environ',{'RADAR_COLLECTION_ENABLED':'1'}),patch('radar.job_auth.authenticate',return_value='run'),patch('radar.postgres_store.PostgresStore') as store:
            request.do_POST()
        store.assert_not_called();self.assertEqual(request.respond.call_args.args[0],400)

    def test_quarantine_batch_holds_lock_and_uses_fixed_limit(self):
        request=self.request({'action':'quarantine'});store=Mock()
        store.acquire.return_value=True;store.reprocess_quarantine.return_value={'done':True,'processed':2}
        with patch.dict('os.environ',{'RADAR_COLLECTION_ENABLED':'1'}),patch('radar.job_auth.authenticate',return_value='run'),patch('radar.postgres_store.PostgresStore',return_value=store):
            request.do_POST()
        store.reprocess_quarantine.assert_called_once_with(limit=5);store.release.assert_called_once();store.close.assert_called_once()
        self.assertEqual(request.respond.call_args.args[0],200)

    def test_reclassification_and_enrichment_cannot_choose_unbounded_request_limits(self):
        for action,target,limit in (('reclassify','radar.reclassification.reclassify_batch',200),('enrich','radar.enrichment.enrich_batch',2)):
            request=self.request({'action':action,'limit':1000000});store=Mock()
            with patch.dict('os.environ',{'RADAR_COLLECTION_ENABLED':'1'}),patch('radar.job_auth.authenticate',return_value='run'),patch('radar.postgres_store.PostgresStore',return_value=store),patch(target,return_value={'done':True}) as batch:
                request.do_POST()
            batch.assert_called_once_with(store,limit=limit,deadline_seconds=45)
