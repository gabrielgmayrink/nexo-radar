import unittest
from unittest.mock import MagicMock
from radar.reclassification import reclassify_batch

class ReclassificationTests(unittest.TestCase):
    def store(self,rows,*,remaining=0,updated=None):
        store=MagicMock();store.acquire.return_value=True
        def execute(sql,params=None):
            result=MagicMock()
            if sql.startswith('select company_id,configuration'):result.fetchall.return_value=[]
            elif sql.startswith('select id,payload,content_hash'):result.fetchall.return_value=rows
            elif sql.startswith('select count'):result.fetchone.return_value=(remaining,)
            elif sql.startswith('update radar_opportunities'):result.rowcount=len(rows) if updated is None else updated
            return result
        store.db.execute.side_effect=execute
        return store

    def test_previously_zero_records_are_reclassified_and_remain_reviewable(self):
        identifier='12345678000100-1-000001/2026'
        store=self.store([(identifier,{'numeroControlePNCP':identifier,'objetoCompra':'Aquisição de cadeiras para o auditório'},'source-hash')])
        result=reclassify_batch(store)
        self.assertTrue(result['done']);self.assertEqual(result['updated'],1)
        update=next(call for call in store.db.execute.call_args_list if call.args[0].startswith('update radar_opportunities'))
        value=update.args[1][0].obj[0]
        self.assertEqual(value['score'],0);self.assertIsNotNone(value['card']);self.assertEqual(value['hash'],'source-hash')
        self.assertIn('o.content_hash is not distinct from r.hash',update.args[0])
        self.assertIn("catalog_archive_reason='outside_profile'",update.args[0]);store.release.assert_called_once()

    def test_concurrent_source_change_does_not_mark_classification_complete(self):
        store=self.store([('identifier',{'objetoCompra':'Serviços de apoio às rotinas administrativas'},'old-hash')],remaining=1,updated=0)
        result=reclassify_batch(store)
        self.assertFalse(result['done']);self.assertEqual(result['remaining'],1);self.assertEqual(result['updated'],0)

    def test_busy_collector_is_respected(self):
        store=self.store([]);store.acquire.return_value=False
        self.assertEqual(reclassify_batch(store)['reason'],'collection_busy');store.db.execute.assert_not_called();store.release.assert_not_called()

    def test_failure_releases_collection_lock(self):
        store=self.store([]);store.db.execute.side_effect=RuntimeError('database failed')
        with self.assertRaises(RuntimeError):reclassify_batch(store)
        store.release.assert_called_once()
