from datetime import datetime,timezone
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from radar.source_health import health_report


class CapacityHealthTests(unittest.TestCase):
    def report(self,size):
        def execute(query):
            value=(size,) if 'pg_database_size' in query else (datetime.now(timezone.utc),) if 'max(finished_at)' in query else (0,)
            return SimpleNamespace(fetchone=lambda:value,fetchall=lambda:[])
        store=Mock();store.db.execute.side_effect=execute
        return health_report(store)
    def test_capacity_warns_before_collection_guard_without_claiming_data_loss(self):
        self.assertTrue(self.report(390*1024*1024)['health']['ok'])
        report=self.report(405*1024*1024)
        self.assertFalse(report['health']['ok'])
        self.assertEqual([c['id'] for c in report['health']['checks'] if not c['ok']],['database_capacity'])
        self.assertLess(report['storage']['databaseBytes'],report['storage']['collectionStopAtBytes'])
