import unittest
from unittest.mock import Mock,patch
from api.health import handler
from radar.company_access import AccessDenied

class HealthApiTests(unittest.TestCase):
    def instance(self):
        item=object.__new__(handler);item.path='/api/health?company=public';item.headers={};item.respond=Mock();return item
    def test_unauthenticated_is_rejected_before_health_queries(self):
        item=self.instance()
        with patch('api.health.request_access',side_effect=AccessDenied(401)),patch('radar.source_health.health_report') as report:item.do_GET()
        item.respond.assert_called_once();self.assertEqual(item.respond.call_args.args[0],401);report.assert_not_called()
    def test_viewer_cannot_read_operator_diagnostics(self):
        item=self.instance();store=Mock()
        with patch('api.health.request_access',return_value=('viewer@example.com','public',['public'])),patch('radar.postgres_store.PostgresStore',return_value=store),patch('api.health.can_manage_company',return_value=False),patch('radar.source_health.health_report') as report:item.do_GET()
        self.assertEqual(item.respond.call_args.args[0],403);report.assert_not_called();store.close.assert_called_once()
    def test_manager_receives_safe_public_source_report(self):
        item=self.instance();store=Mock();data={'health':{'ok':False},'sources':[]}
        with patch('api.health.request_access',return_value=('owner@example.com','public',['public'])),patch('radar.postgres_store.PostgresStore',return_value=store),patch('api.health.can_manage_company',return_value=True),patch('radar.source_health.health_report',return_value=data):item.do_GET()
        item.respond.assert_called_once_with(200,data);store.close.assert_called_once()
