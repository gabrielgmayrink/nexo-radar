from unittest.mock import patch
from profile_fixtures import TEST_PROFILES
import unittest
from datetime import datetime,timedelta,timezone
from types import SimpleNamespace
from unittest.mock import Mock,patch
from radar.canonical import to_card
from radar.notifications import notify


@patch('radar.profiles.load_profiles', lambda: TEST_PROFILES)
class NotificationFlowTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,11,5,15,tzinfo=timezone.utc)
        self.raw={'numeroControlePNCP':'12345678000100-1-000001/2026',
            'objetoCompra':'Assinatura de plataforma para pesquisa de preços públicos',
            'orgaoEntidade':{'cnpj':'12345678000100'},'anoCompra':2026,'sequencialCompra':1,
            'situacaoCompraId':1,'tipoInstrumentoConvocatorioCodigo':1,
            'dataEncerramentoProposta':(self.now+timedelta(hours=24)).isoformat()}
        self.env=patch.dict('os.environ',{'RADAR_TEAM_EMAILS':'member@example.com',
            'RADAR_NOTIFY_EMAILS':'member@example.com'})
        self.env.start();self.addCleanup(self.env.stop)

    def database(self,handled=0):
        def execute(sql,*args):
            if 'radar_memberships' in sql:return SimpleNamespace(fetchall=lambda:[('public',)])
            if 'radar_mail_outbox' in sql:return SimpleNamespace(fetchone=lambda:(handled,))
            if 'radar_catalog_state' in sql:return SimpleNamespace(fetchone=lambda:({'completedAt':(self.now-timedelta(days=10)).isoformat()},))
            if 'radar_opportunities o' in sql:return SimpleNamespace(fetchall=lambda:[(to_card(self.raw),None,None)])
            if 'radar_learning_examples' in sql:return SimpleNamespace(fetchall=lambda:[])
            raise AssertionError('Unexpected notification query')
        return SimpleNamespace(execute=execute)

    def test_live_verified_candidate_can_be_sent_while_bulk_collection_is_pending(self):
        writer=Mock();sender=Mock()
        with patch('radar.notifications.reserve',return_value='unit-reservation'):
            result=notify(self.database(),'weekly',now=self.now,fetcher=lambda _:self.raw,writer=writer,sender=sender)
        self.assertEqual(result['sent'],1);self.assertEqual(result['verified'],1)
        writer.assert_called_once();sender.assert_called_once()
        self.assertIn('conferida individualmente',sender.call_args.args[4])

    def test_cancelled_candidate_is_not_sent_from_a_stale_cached_card(self):
        sender=Mock()
        result=notify(self.database(),'urgent',now=self.now,fetcher=lambda _:{**self.raw,'situacaoCompraId':2},writer=Mock(),sender=sender)
        self.assertEqual(result['sent'],0);sender.assert_not_called()

    def test_already_handled_period_does_not_repeat_pncp_queries_or_delivery(self):
        fetcher=Mock();sender=Mock()
        result=notify(self.database(handled=1),'weekly',now=self.now,fetcher=fetcher,writer=Mock(),sender=sender)
        self.assertEqual(result['skipped'],1);fetcher.assert_not_called();sender.assert_not_called()

    def test_dry_run_checks_candidates_without_reserving_or_sending_messages(self):
        sender=Mock()
        with patch('radar.notifications.reserve') as reserve:
            result=notify(self.database(),'weekly',now=self.now,fetcher=lambda _:self.raw,writer=Mock(),sender=sender,dry_run=True)
        self.assertTrue(result['dryRun']);self.assertEqual(result['sent'],0);self.assertEqual(result['verified'],1)
        sender.assert_not_called();reserve.assert_not_called()
