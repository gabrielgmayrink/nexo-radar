import copy
import unittest
from datetime import date
from radar.sync import initial_cursor,partitions,upgrade_cursor,advance
from radar.incremental_collection import handle_incremental
from radar.national_collection import StalePage
from test_national_collection import Store,payload


class IncrementalStore(Store):
    def commit_page(self,execution_id,kind,rows,cursor,**kwargs):
        if self.fail:raise RuntimeError('Interrupted write')
        for row in rows:
            if isinstance(row,dict) and row.get('numeroControlePNCP'):self.rows[row['numeroControlePNCP']]=row
        self.cursor=copy.deepcopy(cursor)


def send(store,action,data=None):
    progress=handle_incremental(store,'incremental_plan',{},'run')
    plan=progress['plan']
    return handle_incremental(store,action,{**{key:plan[key] for key in ('executionId','page','mode','modality')},**(data or {})},'run')


class IncrementalTests(unittest.TestCase):
    def test_daily_capture_only_publication_and_update_with_complete_domain(self):
        store=IncrementalStore();seen=[]
        while True:
            progress=handle_incremental(store,'incremental_plan',{},'run')
            if progress['done']:break
            plan=progress['plan'];seen.append((plan['mode'],plan['modality']))
            self.assertNotIn('uf',plan['query']);self.assertEqual(set(plan['query']),{'dataInicial','dataFinal','pagina','tamanhoPagina','codigoModalidadeContratacao'})
            send(store,'incremental_commit',{'payload':{'data':[]}})
        self.assertEqual(set(seen),{(mode,modality) for mode in ('publicacao','atualizacao') for modality in range(1,20)})
        self.assertEqual(len(store.captures),38)

    def test_overlap_and_outage_catchup_have_no_silent_thirty_day_cap(self):
        cursor=initial_cursor('incremental',date(2026,11,11),date(2026,8,1))
        self.assertEqual(cursor['start'],'2026-07-30');self.assertEqual(cursor['end'],'2026-08-28')
        cursor=upgrade_cursor(cursor)
        for _ in range(len(partitions('incremental'))):cursor=advance(cursor,[],{'data':[]})
        self.assertEqual(cursor['start'],'2026-08-26');self.assertEqual(cursor['end'],'2026-09-24')
        self.assertTrue(cursor['pending_tasks']);self.assertEqual(cursor['target_end'],'2026-11-11')

    def test_failure_keeps_original_and_cursor_then_valid_retry_advances(self):
        store=IncrementalStore();store.fail=True
        with self.assertRaises(RuntimeError):send(store,'incremental_commit',{'payload':payload(1,1)})
        self.assertEqual(len(store.captures),1)
        self.assertEqual(handle_incremental(store,'incremental_plan',{},'run')['plan']['modality'],9)
        store.fail=False;send(store,'incremental_commit',{'payload':payload(1,1)})
        self.assertEqual(len(store.rows),1)
        self.assertEqual(handle_incremental(store,'incremental_plan',{},'run')['plan']['modality'],6)

    def test_invalid_contract_preserved_without_advancing(self):
        store=IncrementalStore()
        with self.assertRaises(ValueError):send(store,'incremental_commit',{'payload':{**payload(1,1),'data':[]}})
        self.assertEqual(store.quarantined,{1});self.assertEqual(store.rows,{})

    def test_stale_partition_cannot_commit_into_next_page(self):
        store=IncrementalStore();progress=handle_incremental(store,'incremental_plan',{},'run')
        ref={key:progress['plan'][key] for key in ('executionId','page','mode','modality')}
        send(store,'incremental_commit',{'payload':{'data':[]}})
        with self.assertRaises(StalePage):handle_incremental(store,'incremental_commit',{**ref,'payload':payload(1,1)},'run')

    def test_rate_limit_cools_whole_source_and_timeout_keeps_failed_page(self):
        store=IncrementalStore();result=send(store,'incremental_failure',{'reason':'http_429','retryAfterSeconds':120})
        self.assertGreater(result['retryAfterSeconds'],100)
        self.assertEqual(len(store.cursor['pending_tasks']),38)
        store=IncrementalStore();result=send(store,'incremental_failure',{'reason':'timeout','retryAfterSeconds':120})
        self.assertEqual(result['plan']['modality'],6)
        failed=next(t for t in store.cursor['pending_tasks'] if t['mode']=='publicacao' and t['modality']==9)
        self.assertEqual(failed['page'],1);self.assertIn('next_attempt_at',failed)

    def test_legacy_queue_adds_missing_modalities_without_rewinding_completed_ones(self):
        cursor=initial_cursor('incremental',date(2026,11,11));cursor.update(queue_version=3)
        cursor['pending_tasks']=[{'mode':'atualizacao','modality':6,'page':19,'fingerprints':['old']}]
        updated=upgrade_cursor(cursor)
        self.assertNotIn(('publicacao',9),[(t['mode'],t['modality']) for t in updated['pending_tasks']])
        self.assertIn(('publicacao',19),[(t['mode'],t['modality']) for t in updated['pending_tasks']])
        saved=next(t for t in updated['pending_tasks'] if (t['mode'],t['modality'])==('atualizacao',6))
        self.assertEqual(saved['page'],19);self.assertEqual(saved['fingerprints'],['old'])
