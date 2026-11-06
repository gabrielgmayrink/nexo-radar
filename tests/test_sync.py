import copy
import unittest
from datetime import date,datetime,timedelta,timezone
from radar.pncp import PNCPError,RequestMetric
from radar.sync import initial_cursor,page_query,run_chunk,partitions,upgrade_cursor


class MemoryStore:
    def __init__(self):
        self.cursor=None;self.rows={};self.locked=False;self.released=False;self.fail_commit=False
    def acquire(self):return not self.locked
    def release(self):self.released=True
    def start_or_resume(self,kind,run_key,execution_id,today):
        self.cursor=self.cursor or initial_cursor(kind,today)
        return 1,copy.deepcopy(self.cursor)
    def commit_page(self,execution_id,kind,records,cursor):
        if self.fail_commit:raise RuntimeError('simulated database interruption')
        self.rows.update({r['numeroControlePNCP']:r for r in records})
        self.cursor=copy.deepcopy(cursor)
    def save_failure(self,execution_id,kind,cursor):self.cursor=copy.deepcopy(cursor)
    def complete(self,execution_id,kind,cursor):self.cursor=copy.deepcopy(cursor)


class Client:
    def __init__(self,responses):self.responses=iter(responses);self.queries=[]
    def get_page(self,path,params,**kwargs):
        self.queries.append((path,dict(params)))
        result=next(self.responses)
        if isinstance(result,Exception):raise result
        kwargs['metrics'].requests.append(RequestMetric(path,kwargs['modality'],kwargs['page'],200,12,len(result['data'])))
        return result


class SyncTests(unittest.TestCase):
    def test_backfill_covers_thirty_days_and_open_uses_future_horizon(self):
        cursor=initial_cursor('backfill',date(2026,11,5))
        self.assertEqual(cursor['start'],'2026-10-07')
        self.assertEqual(len(partitions('backfill')),33)
        self.assertIn(('publicacao',9),partitions('backfill'))
        self.assertIn(('proposta',9),partitions('backfill'))
        self.assertEqual(page_query(cursor)[2]['dataFinal'],'20261105')
        query=page_query(initial_cursor('open',date(2026,11,5)))[2]
        self.assertEqual(query['dataFinal'],'20271105')
        self.assertNotIn('dataInicial',query)

    def test_partial_page_failure_resumes_without_duplicate_records(self):
        records=[{'numeroControlePNCP':str(i)} for i in range(50)]
        store=MemoryStore()
        first=run_chunk(store,run_key='1',today=date(2026,11,5),client=Client([
            {'data':records,'totalPaginas':2},PNCPError('http_503')]),max_pages=2)
        self.assertEqual(first['status'],'partial')
        self.assertEqual(store.cursor['pending_tasks'][-1]['page'],2)
        store.cursor.pop('next_attempt_at',None)
        client=Client([{'data':[{'numeroControlePNCP':'final'}],'totalPaginas':2}])
        result=run_chunk(store,run_key='2',execution_id=1,client=client,max_pages=1)
        self.assertEqual(client.queries[0][1]['codigoModalidadeContratacao'],6)
        self.assertEqual(client.queries[0][1]['pagina'],1)
        self.assertEqual(result['recordsReceived'],51)
        self.assertEqual(len(store.rows),51)

    def test_repeated_page_does_not_advance_cursor(self):
        data={'data':[{'numeroControlePNCP':str(i)} for i in range(50)],'totalPaginas':3}
        store=MemoryStore()
        store.cursor=upgrade_cursor(initial_cursor('open',date(2026,11,5)))
        store.cursor['pending_tasks']=store.cursor['pending_tasks'][:1]
        result=run_chunk(store,'open',run_key='1',client=Client([data,data]),max_pages=2)
        self.assertEqual(result['status'],'partial')
        self.assertEqual(store.cursor['page'],2);self.assertEqual(len(store.rows),50)

    def test_malformed_page_is_not_partly_written(self):
        store=MemoryStore()
        result=run_chunk(store,run_key='1',client=Client([{'data':[{'numeroControlePNCP':'valid'},{}]}]),max_pages=1)
        self.assertEqual(result['status'],'partial');self.assertEqual(store.rows,{})
        self.assertEqual(store.cursor['page'],1)

    def test_write_interruption_preserves_previous_cursor_and_releases_lock(self):
        store=MemoryStore();store.fail_commit=True
        with self.assertRaises(RuntimeError):
            run_chunk(store,run_key='1',client=Client([{'data':[{'numeroControlePNCP':'1'}]}]),max_pages=1)
        self.assertEqual(store.cursor['page'],1);self.assertEqual(store.rows,{})
        self.assertTrue(store.released)

    def test_empty_intermediate_page_is_not_completion(self):
        store=MemoryStore()
        result=run_chunk(store,run_key='1',client=Client([{'data':[],'totalPaginas':3}]),max_pages=1)
        self.assertEqual(result['status'],'partial');self.assertFalse(result['done'])

    def test_all_partitions_complete_before_success(self):
        store=MemoryStore()
        total=len(partitions('open'))
        result=run_chunk(store,'open',run_key='1',client=Client([{'data':[]}]*total))
        self.assertTrue(result['done']);self.assertEqual(store.cursor['partition'],total)

    def test_round_robin_reaches_each_modality_before_a_second_page(self):
        store=MemoryStore()
        total=len(partitions('open'))
        data={'data':[{'numeroControlePNCP':'sample'}],'totalPaginas':3}
        client=Client([data]*(total+1))
        run_chunk(store,'open',run_key='1',client=client,max_pages=total+1)
        self.assertEqual([q[1]['codigoModalidadeContratacao'] for q in client.queries[:total]], [m for _,m in partitions('open')])
        self.assertEqual(client.queries[-1][1]['pagina'],2)

    def test_legacy_checkpoint_retains_page_and_fingerprint_after_upgrade(self):
        cursor=initial_cursor('incremental',date(2026,11,5))
        cursor.update(partition=0,page=29,fingerprints=['saved'],pages=28,received=1400)
        updated=upgrade_cursor(cursor)
        task=next(t for t in updated['pending_tasks'] if t['mode']=='publicacao' and t['modality']==6)
        self.assertEqual(task['page'],29)
        self.assertEqual(task['fingerprints'],['saved'])
        self.assertEqual(updated['received'],1400)
        self.assertEqual(page_query(updated)[1],9)

    def test_concurrent_batch_is_rejected_without_accessing_provider(self):
        store=MemoryStore();store.locked=True
        self.assertTrue(run_chunk(store,run_key='1',client=Client([]))['busy'])
        self.assertIsNone(store.cursor)

    def test_time_budget_yields_without_losing_progress(self):
        store=MemoryStore();times=iter([0,0,190])
        result=run_chunk(store,run_key='1',client=Client([{'data':[]}]),clock=lambda:next(times))
        self.assertEqual(result['completedPartitions'],1);self.assertFalse(result['done'])

    def test_rate_limit_cooldown_is_shared_with_next_batch(self):
        store=MemoryStore()
        result=run_chunk(store,run_key='1',client=Client([PNCPError('http_429',retry_after_seconds=120)]))
        self.assertGreater(result['retryAfterSeconds'],110)
        second=run_chunk(store,run_key='2',client=Client([]))
        self.assertEqual(second['requests'],result['requests'])
        self.assertGreater(second['retryAfterSeconds'],0)

    def test_repeated_origin_failures_increase_wait_and_success_resets_it(self):
        store=MemoryStore();store.cursor=upgrade_cursor(initial_cursor('open',date(2026,11,5)))
        store.cursor['pending_tasks']=store.cursor['pending_tasks'][:1]
        first=run_chunk(store,run_key='1',client=Client([PNCPError('timeout')]))
        self.assertGreaterEqual(first['retryAfterSeconds'],13)
        store.cursor.pop('next_attempt_at',None)
        store.cursor['pending_tasks'][0].pop('next_attempt_at',None)
        second=run_chunk(store,run_key='2',client=Client([PNCPError('timeout')]))
        self.assertGreaterEqual(second['retryAfterSeconds'],28)
        self.assertEqual(store.cursor['consecutive_errors'],2)
        store.cursor.pop('next_attempt_at',None)
        store.cursor['pending_tasks'][0].pop('next_attempt_at',None)
        run_chunk(store,run_key='3',client=Client([{'data':[]}]),max_pages=1)
        self.assertEqual(store.cursor['consecutive_errors'],0)

    def test_timeout_preserves_failed_page_and_allows_other_modalities(self):
        store=MemoryStore()
        first=run_chunk(store,'open',run_key='1',client=Client([PNCPError('timeout')]))
        self.assertEqual(first['status'],'running')
        self.assertEqual(first['retryAfterSeconds'],0)
        self.assertEqual(store.cursor['pending_tasks'][-1]['modality'],9)
        self.assertEqual(store.cursor['pending_tasks'][-1]['page'],1)
        healthy=Client([{'data':[]}])
        run_chunk(store,'open',run_key='2',client=healthy,max_pages=1)
        self.assertEqual(healthy.queries[0][1]['codigoModalidadeContratacao'],6)
