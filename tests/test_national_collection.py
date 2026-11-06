import copy
import unittest
from radar.sync import initial_cursor
from radar.national_collection import handle_national,validate_payload,StalePage


def payload(page,total=120,ids=None):
    ids=ids if ids is not None else range((page-1)*50,min(page*50,total))
    return {'data':[{'numeroControlePNCP':f'12345678000100-1-{i:06d}/2026','objetoCompra':'Public procurement'} for i in ids],
            'numeroPagina':page,'totalRegistros':total,'totalPaginas':(total+49)//50}


class Store:
    def __init__(self):self.cursor=None;self.ledger={};self.rows={};self.locked=False;self.fail=False;self.interrupt_finish=False
    def acquire(self):return not self.locked
    def release(self):pass
    def start_or_resume(self,kind,run_key,execution_id,today):
        self.cursor=self.cursor or initial_cursor(kind,today)
        return 1,copy.deepcopy(self.cursor)
    def national_page(self,execution_id,pass_number,page):return self.ledger.get((pass_number,page))
    def commit_national_page(self,execution_id,rows,cursor,page,digest,total,pages):
        if self.fail:raise RuntimeError('Interrupted write')
        for row in rows:self.rows[row['numeroControlePNCP']]=cursor['passNumber']
        self.ledger[(cursor['passNumber'],page)]=digest;self.cursor=copy.deepcopy(cursor)
    def national_counts(self,execution_id,pass_number,current_only=False):
        if self.interrupt_finish:self.interrupt_finish=False;raise RuntimeError('Interrupted finalization')
        return sum(value==pass_number for value in self.rows.values()) if current_only else len(self.rows),sum(key[0]==pass_number for key in self.ledger)
    def save_failure(self,execution_id,kind,cursor):self.cursor=copy.deepcopy(cursor)
    def complete(self,execution_id,kind,cursor):self.cursor=copy.deepcopy(cursor)


def commit(store,data,pass_number=1):
    return handle_national(store,'national_commit',{'executionId':1,'page':data['numeroPagina'],'passNumber':pass_number,'payload':data},'run')


class NationalTests(unittest.TestCase):
    def test_plan_has_no_company_state_modality_or_publication_window(self):
        result=handle_national(Store(),'national_plan',{},'run')
        self.assertEqual(result['scope'],'all_open_brazil')
        self.assertEqual(result['plan']['query'],{'pagina':1,'tamanhoPagina':50,'dataFinal':'99991231'})
        self.assertFalse(result['done'])

    def test_every_page_is_received_before_coverage_can_be_complete(self):
        store=Store()
        self.assertFalse(commit(store,payload(1))['done'])
        self.assertFalse(commit(store,payload(2))['done'])
        final=commit(store,payload(3))
        self.assertFalse(final['done']);self.assertEqual(final['passNumber'],2)
        final=commit(store,payload(1),pass_number=2)
        self.assertTrue(final['done']);self.assertTrue(final['coverageComplete'])
        self.assertEqual(final['uniqueRecords'],120);self.assertEqual(len(store.ledger),4)

    def test_lost_response_retries_do_not_duplicate_or_skip_pages(self):
        store=Store();data=payload(1)
        first=commit(store,data);again=commit(store,data)
        self.assertEqual(first['plan'],again['plan'])
        self.assertTrue(again['alreadyCommitted']);self.assertEqual(len(store.rows),50)

    def test_future_page_cannot_skip_pending_page(self):
        store=Store()
        with self.assertRaises(StalePage):commit(store,payload(2))
        self.assertEqual(store.rows,{})

    def test_short_empty_wrong_page_and_missing_metadata_are_rejected(self):
        for data in ({'data':[]},{**payload(1),'data':[]},{**payload(1),'data':payload(1)['data'][:10]},payload(2)):
            with self.assertRaises(ValueError):validate_payload(data,1)

    def test_duplicates_across_pages_trigger_reconciliation_instead_of_complete(self):
        store=Store();commit(store,payload(1,total=51))
        result=commit(store,payload(2,total=51,ids=[0]))
        self.assertFalse(result['done']);self.assertFalse(result['coverageComplete'])
        self.assertEqual(result['passNumber'],2);self.assertEqual(result['plan']['page'],1)
        commit(store,payload(1,total=51),pass_number=2)
        self.assertTrue(commit(store,payload(2,total=51),pass_number=2)['done'])

    def test_write_interruption_does_not_advance_page(self):
        store=Store();store.fail=True
        with self.assertRaises(RuntimeError):commit(store,payload(1))
        store.fail=False
        self.assertEqual(handle_national(store,'national_plan',{},'run')['plan']['page'],1)

    def test_final_page_interruption_recovers_using_committed_coverage(self):
        store=Store();store.interrupt_finish=True
        with self.assertRaises(RuntimeError):commit(store,payload(1,total=1))
        result=handle_national(store,'national_plan',{},'run')
        self.assertFalse(result['done']);self.assertEqual(result['passNumber'],2)
        result=commit(store,payload(1,total=1),pass_number=2)
        self.assertTrue(result['done']);self.assertEqual(result['uniqueRecords'],1)

    def test_source_timeout_preserves_page_and_cannot_set_complete(self):
        store=Store();commit(store,payload(1))
        result=handle_national(store,'national_failure',{'executionId':1,'passNumber':1,'page':2,'reason':'timeout'},'run')
        self.assertEqual(result['plan']['page'],2);self.assertFalse(result['coverageComplete'])

    def test_empty_success_with_explicit_metadata_can_complete_zero_records(self):
        store=Store();commit(store,payload(1,total=0))
        result=commit(store,payload(1,total=0),pass_number=2)
        self.assertTrue(result['done']);self.assertEqual(result['uniqueRecords'],0)

    def test_records_published_during_full_pass_are_collected_in_final_check(self):
        store=Store();commit(store,payload(1,total=51));commit(store,payload(2,total=51))
        result=commit(store,payload(1,total=52,ids=[51]+list(range(49))),pass_number=2)
        self.assertTrue(result['done']);self.assertEqual(result['uniqueRecords'],52)

    def test_source_with_fewer_pages_can_be_reconciled_without_stalling(self):
        store=Store();commit(store,payload(1,total=60))
        result=handle_national(store,'national_reconcile',{'executionId':1,'passNumber':1,'page':2,'payload':payload(1,total=40)},'run')
        self.assertEqual(result['passNumber'],2);self.assertFalse(result['done'])
        result=commit(store,payload(1,total=40),pass_number=2)
        self.assertTrue(result['done']);self.assertEqual(result['uniqueRecords'],40)
        self.assertEqual(store.cursor['minimumPass'],2)
