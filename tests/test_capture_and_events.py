import unittest
from contextlib import nullcontext
from unittest.mock import patch
import psycopg
from radar.postgres_store import PostgresStore,capture_observations,prepared_record
from radar.procurement_events import source_changes
from test_national_collection import payload


class Database:
    def __init__(self):self.calls=[]
    def transaction(self):return nullcontext()
    def execute(self,sql,params=None):self.calls.append((sql,params));return self


class CaptureTests(unittest.TestCase):
    def test_zero_score_still_has_card_and_source_identifiers_are_preserved(self):
        raw=payload(1,1)['data'][0];raw['objetoCompra']='Contratação de serviços para modernização de auditório com obras estruturais';record=prepared_record(raw)
        self.assertEqual(record[4],0);self.assertEqual(record[5].obj['id'],raw['numeroControlePNCP'])
        self.assertTrue(record[8]);self.assertTrue(record[9])

    def test_malformed_record_and_duplicate_are_quarantined_with_good_neighbors(self):
        good=payload(1,2)['data'];records=[good[0],{},good[0],good[1]]
        observations,valid=capture_observations(records)
        self.assertEqual([i for i,_ in valid],[0,3])
        self.assertEqual([r['reason'] for r in observations],[None,'invalid_identifier','duplicate_source_identifier',None])
        self.assertTrue(all(r['content_hash'] for r in observations))

    def test_normal_page_writes_once_and_loads_profiles_once(self):
        db=Database();store=PostgresStore.__new__(PostgresStore);store.db=db
        rows=payload(1,50)['data']
        with patch('radar.profiles.profile_context',return_value=nullcontext()) as profiles,patch.object(store,'_write_records_with_profiles') as write:
            ids=store.ingest_capture(42,rows)
        self.assertEqual(len(ids),50);write.assert_called_once_with(rows);profiles.assert_called_once_with(db)
        self.assertLess(len(db.calls),6)

    def test_constraint_failure_isolated_without_swallowing_valid_neighbors(self):
        db=Database();store=PostgresStore.__new__(PostgresStore);store.db=db
        rows=payload(1,3)['data'];bad=rows[1]['numeroControlePNCP'];writes=[]
        def write(batch):
            if any(row['numeroControlePNCP']==bad for row in batch):raise psycopg.DataError('fixed test anomaly')
            writes.extend(row['numeroControlePNCP'] for row in batch)
        with patch('radar.profiles.profile_context',return_value=nullcontext()),patch.object(store,'_write_records_with_profiles',side_effect=write):
            ids=store.ingest_capture(42,rows)
        self.assertEqual(ids,writes);self.assertEqual(len(ids),2);self.assertNotIn(bad,ids)
        documents=next(params[1].obj for sql,params in db.calls if 'insert into radar_source_observations' in sql)
        self.assertEqual(documents[1]['reason'],'record_storage_failed')

    def test_infrastructure_failure_propagates_so_cursor_cannot_skip_data(self):
        store=PostgresStore.__new__(PostgresStore);store.db=Database()
        with patch('radar.profiles.profile_context',return_value=nullcontext()),patch.object(store,'_write_records_with_profiles',side_effect=psycopg.OperationalError()):
            with self.assertRaises(psycopg.OperationalError):store.ingest_capture(42,payload(1,1)['data'])


class EventTests(unittest.TestCase):
    def test_official_changes_only_without_private_fields(self):
        before={'objetoCompra':'Old','dataEncerramentoProposta':'2026-11-11','private_note':'secret'}
        after={**before,'dataEncerramentoProposta':'2026-11-12','private_note':'other'}
        events=source_changes('id',before,after)
        self.assertEqual(len(events),1);self.assertEqual(events[0]['kind'],'deadline_changed')
        self.assertNotIn('secret',str(events));self.assertEqual(events[0]['old_value'],'2026-11-11')

    def test_identical_replay_deduplicates_and_repeated_later_transition_is_retained(self):
        before={'objetoCompra':'A'};after={'objetoCompra':'B'}
        first=source_changes('id',before,after,transition_id='t1')
        self.assertEqual(first,source_changes('id',before,after,transition_id='t1'))
        self.assertNotEqual(first[0]['event_key'],source_changes('id',before,after,transition_id='t2')[0]['event_key'])
        self.assertEqual(source_changes('id',after,after),[])
