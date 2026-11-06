import unittest
from datetime import datetime,timezone
from unittest.mock import patch
from radar.catalog_maintenance import archive_reason,weekly_ready,weekly_summary,cleanup


class MaintenanceTests(unittest.TestCase):
    def test_cleanup_uses_exact_deadline_and_preserves_unknown_dates(self):
        now=datetime(2026,11,8,12,tzinfo=timezone.utc)
        self.assertEqual(archive_reason(1,'2026-11-08T09:00:00',70,now),'expired')
        self.assertIsNone(archive_reason(1,'2026-11-08T09:00:01',70,now))
        self.assertEqual(archive_reason(2,'2099-01-01',70,now),'inactive')
        self.assertEqual(archive_reason(1,'2099-01-01',0,now),'outside_profile')
        self.assertIsNone(archive_reason(1,None,70,now))
        self.assertIsNone(archive_reason(1,'bad-date',70,now))
        self.assertIsNone(archive_reason(1,'2099-01-01',40,now))

    def test_weekly_digest_requires_monday_after_seven_and_current_completed_run(self):
        before=datetime(2026,11,9,9,59,tzinfo=timezone.utc)
        monday=datetime(2026,11,9,10,tzinfo=timezone.utc)
        cursor={'status':'ok','coverageComplete':True,'end':'2026-11-09','last_run_key':'123:1'}
        self.assertTrue(weekly_ready(cursor,'123:1',monday))
        self.assertTrue(weekly_ready(cursor,'123:2',monday))
        self.assertFalse(weekly_ready(cursor,'123:1',before))
        for changes in ({'status':'partial'},{'coverageComplete':False},{'end':'2026-11-02'},{'last_run_key':'122:1'}):
            self.assertFalse(weekly_ready(cursor|changes,'123:1',monday))
        self.assertFalse(weekly_ready(cursor|{'end':'2026-11-10'},'123:1',datetime(2026,11,10,10,tzinfo=timezone.utc)))

    def test_cleanup_cannot_run_during_incomplete_collection(self):
        class Store:
            released=False
            def acquire(self):return True
            def release(self):self.released=True
            @property
            def db(self):return self
            def execute(self,*args):return self
            def fetchone(self):return ({'status':'partial'},)
        store=Store()
        self.assertEqual(cleanup(store),{'done':False,'reason':'collection_incomplete'})
        self.assertTrue(store.released)

    def test_incomplete_or_unrelated_run_never_sends_weekly_mail(self):
        class Store:
            def acquire(self):return True
            def release(self):pass
            @property
            def db(self):return self
            def execute(self,*args):return self
            def fetchone(self):return ({'status':'partial'},)
        with patch('radar.notifications.notify') as send:
            result=weekly_summary(Store(),'123:1')
        self.assertFalse(result['done']);self.assertEqual(result['sent'],0);send.assert_not_called()

    def test_weekly_digest_passes_dry_run_and_storage_writer(self):
        class Store:
            def acquire(self):return True
            def release(self):pass
            def write_records(self,records):pass
            @property
            def db(self):return self
            def execute(self,*args):return self
            def fetchone(self):return ({'status':'ok','coverageComplete':True,'end':'2026-11-09','last_run_key':'123:1'},)
        store=Store()
        with patch('radar.notifications.notify',return_value={'sent':0,'dryRun':True}) as send:
            result=weekly_summary(store,'123:1',dry_run=True,now=datetime(2026,11,9,10,tzinfo=timezone.utc))
        self.assertTrue(result['done'])
        send.assert_called_once_with(store.db,'weekly',writer=store.write_records,dry_run=True)
