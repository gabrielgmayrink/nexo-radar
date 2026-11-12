import copy
import hashlib
import json
import unittest
from radar.sync import initial_cursor
from radar.identifiers import parse_pncp_id
from radar.national_collection import handle_national,validate_payload,StalePage


def payload(page,total=120,ids=None):
    ids=ids if ids is not None else range((page-1)*50,min(page*50,total))
    return {'data':[{'numeroControlePNCP':f'12345678000100-1-{i:06d}/2026','objetoCompra':'Public procurement'} for i in ids],
            'numeroPagina':page,'totalRegistros':total,'totalPaginas':(total+49)//50}


class Store:
    """Immutable per-pass receipts; last-seen rows are never membership proof."""
    def __init__(self):
        self.cursor=None;self.ledger={};self.rows={};self.locked=False;self.fail=False
        self.interrupt_finish=False;self.captures={};self.receipts={};self.quarantined=set()
    def acquire(self):return not self.locked
    def release(self):pass
    def start_or_resume(self,kind,run_key,execution_id,today):
        self.cursor=self.cursor or initial_cursor(kind,today)
        return 1,copy.deepcopy(self.cursor)
    def capture_page(self,execution_id,pass_number,page,payload,**kwargs):
        identifier=len(self.captures)+1
        self.captures[identifier]={'payload':copy.deepcopy(payload),'wire':kwargs.get('wire'),'page':page,'pass':pass_number}
        return identifier
    def quarantine_page(self,capture_id,reason):self.quarantined.add(capture_id)
    def national_page(self,execution_id,pass_number,page):return self.ledger.get((pass_number,page))
    def commit_national_page(self,execution_id,rows,cursor,page,digest,total,pages,*,capture_id):
        if self.fail:raise RuntimeError('Interrupted write')
        for row in rows:
            try:identifier=parse_pncp_id(row.get('numeroControlePNCP') if isinstance(row,dict) else None).canonical
            except ValueError:self.quarantined.add(capture_id);continue
            self.rows[identifier]=cursor['passNumber']
        key=(cursor['passNumber'],page)
        self.ledger[key]=digest;self.receipts[key]=(capture_id,total,pages)
        self.cursor=copy.deepcopy(cursor)
    def pass_evidence(self,execution_id,pass_number):
        if self.interrupt_finish:self.interrupt_finish=False;raise RuntimeError('Interrupted finalization')
        receipts=[(page,*value) for (number,page),value in self.receipts.items() if number==pass_number]
        membership={};totals=[];pages=[];pending=0
        for page,capture_id,total,page_count in receipts:
            totals.append(total);pages.append(page_count);pending+=capture_id in self.quarantined
            for row in self.captures[capture_id]['payload']['data']:
                try:identifier=parse_pncp_id(row.get('numeroControlePNCP') if isinstance(row,dict) else None).canonical
                except ValueError:continue
                digest=hashlib.sha256(json.dumps(row,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
                membership.setdefault(identifier,[]).append(digest)
        ordered=[(identifier,min(hashes),max(hashes)) for identifier,hashes in sorted(membership.items())]
        complete=bool(receipts and sorted(r[0] for r in receipts)==list(range(1,max(1,max(pages))+1)))
        return {'complete':complete,'count':len(ordered),'quarantined':pending,
                'fingerprint':hashlib.sha256(json.dumps(ordered,separators=(',',':')).encode()).hexdigest(),
                'stableWithinPass':complete and min(totals)==max(totals)==len(ordered) and all(a==b for _,a,b in ordered)}
    def national_counts(self,execution_id,pass_number,current_only=False):
        return sum(v==pass_number for v in self.rows.values()) if current_only else len(self.rows),sum(k[0]==pass_number for k in self.ledger)
    def save_failure(self,execution_id,kind,cursor):self.cursor=copy.deepcopy(cursor)
    def complete(self,execution_id,kind,cursor):self.cursor=copy.deepcopy(cursor)


def commit(store,data,pass_number=1):
    return handle_national(store,'national_commit',{'executionId':1,'page':data['numeroPagina'],'passNumber':pass_number,'payload':data},'run')


def full_pass(store,total,number=1):
    for page in range(1,max(1,(total+49)//50)+1):result=commit(store,payload(page,total),number)
    return result


class NationalTests(unittest.TestCase):
    def test_plan_has_no_business_or_state_filter(self):
        result=handle_national(Store(),'national_plan',{},'run')
        self.assertEqual(result['scope'],'all_open_brazil')
        self.assertEqual(result['plan']['query'],{'pagina':1,'tamanhoPagina':50,'dataFinal':'99991231'})

    def test_two_full_identical_passes_required_including_last_page(self):
        store=Store();first=full_pass(store,120)
        self.assertFalse(first['done']);self.assertEqual(first['passNumber'],2)
        self.assertTrue(first['captureComplete']);self.assertFalse(first['coverageComplete'])
        for page in (1,2):self.assertFalse(commit(store,payload(page),2)['done'])
        final=commit(store,payload(3),2)
        self.assertTrue(final['done']);self.assertTrue(final['coverageComplete'])
        self.assertEqual(final['consistency'],'stable_sets');self.assertEqual(len(store.ledger),6)

    def test_equal_counts_replaced_id_outside_head_does_not_prove_complete(self):
        store=Store();full_pass(store,100);commit(store,payload(1,100),2)
        final=commit(store,payload(2,100,ids=list(range(50,99))+[100]),2)
        self.assertTrue(final['done']);self.assertTrue(final['captureComplete'])
        self.assertFalse(final['coverageComplete']);self.assertEqual(final['consistency'],'source_changed')
        self.assertIn('12345678000100-1-000100/2026',store.rows)

    def test_equal_ids_changed_body_cannot_prove_consistency(self):
        store=Store();full_pass(store,51);commit(store,payload(1,51),2)
        changed=payload(2,51);changed['data'][0]['objetoCompra']='Amended notice'
        final=commit(store,changed,2)
        self.assertFalse(final['coverageComplete']);self.assertEqual(final['consistency'],'source_changed')

    def test_growth_requires_all_new_pages_and_marks_source_changed(self):
        store=Store();full_pass(store,100)
        for page in (1,2,3):self.assertFalse(commit(store,payload(page,151),2)['done'])
        final=commit(store,payload(4,151),2)
        self.assertEqual(len(store.rows),151);self.assertTrue(final['done']);self.assertFalse(final['coverageComplete'])

    def test_lost_response_is_idempotent_and_cannot_skip_pending_page(self):
        store=Store();first=commit(store,payload(1));again=commit(store,payload(1))
        self.assertTrue(again['alreadyCommitted']);self.assertEqual(first['plan'],again['plan'])
        with self.assertRaises(StalePage):commit(store,payload(3))
        self.assertEqual(len(store.rows),50)

    def test_page_contract_failure_preserves_source_before_indexing(self):
        store=Store();bad={**payload(1),'data':[]}
        with self.assertRaises(ValueError):commit(store,bad)
        self.assertEqual(store.captures[1]['payload'],bad);self.assertEqual(store.quarantined,{1})
        self.assertEqual(store.rows,{})

    def test_bad_row_does_not_discard_good_neighbors_or_claim_coverage(self):
        store=Store();bad=payload(1,2);bad['data'][1]['numeroControlePNCP']='invalid'
        commit(store,bad);final=commit(store,bad,2)
        self.assertEqual(len(store.rows),1);self.assertEqual(len(store.captures),2)
        self.assertTrue(final['done']);self.assertFalse(final['indexingComplete'])
        self.assertFalse(final['coverageComplete']);self.assertEqual(final['consistency'],'quarantine_pending')

    def test_structural_ids_support_alpha_cnpj_and_preserve_mistyped_year(self):
        for identifier in ('AB123456000196-1-000001/2026','08241747000496-1-000001/20226'):
            data=payload(1,1);data['data'][0]['numeroControlePNCP']=identifier
            self.assertEqual(validate_payload(data,1)[0][0]['numeroControlePNCP'],identifier)
            store=Store();commit(store,data);self.assertIn(identifier,store.rows)

    def test_duplicate_membership_does_not_prove_consistency(self):
        store=Store()
        for number in (1,2):
            commit(store,payload(1,51),number);final=commit(store,payload(2,51,ids=[0]),number)
        self.assertTrue(final['done']);self.assertFalse(final['coverageComplete'])

    def test_write_interruption_preserves_capture_and_cursor(self):
        store=Store();store.fail=True
        with self.assertRaises(RuntimeError):commit(store,payload(1))
        self.assertEqual(len(store.captures),1);store.fail=False
        self.assertEqual(handle_national(store,'national_plan',{},'run')['plan']['page'],1)

    def test_finalization_interruption_recovers_from_committed_receipts(self):
        store=Store();store.interrupt_finish=True
        with self.assertRaises(RuntimeError):commit(store,payload(1,1))
        result=handle_national(store,'national_plan',{},'run')
        self.assertEqual(result['passNumber'],2);self.assertFalse(result['done'])
        self.assertTrue(commit(store,payload(1,1),2)['coverageComplete'])

    def test_timeout_does_not_advance_or_confirm_coverage(self):
        store=Store();commit(store,payload(1))
        result=handle_national(store,'national_failure',{'executionId':1,'passNumber':1,'page':2,'reason':'timeout'},'run')
        self.assertEqual(result['plan']['page'],2);self.assertFalse(result['coverageComplete'])

    def test_explicit_empty_dataset_requires_two_observations(self):
        store=Store();self.assertFalse(full_pass(store,0)['done']);result=full_pass(store,0,2)
        self.assertTrue(result['coverageComplete']);self.assertEqual(result['uniqueRecords'],0)

    def test_source_shrink_restarts_full_without_counting_partial_observation(self):
        store=Store();commit(store,payload(1,60))
        result=handle_national(store,'national_reconcile',{'executionId':1,'passNumber':1,'page':2,'payload':payload(1,40)},'run')
        self.assertEqual(result['passNumber'],2);self.assertFalse(full_pass(store,40,2)['done'])
        result=full_pass(store,40,3)
        self.assertTrue(result['coverageComplete']);self.assertEqual(result['completedFullPasses'],2)

    def test_missing_short_empty_wrong_page_metadata_rejected(self):
        for data in ({'data':[]},{**payload(1),'data':[]},{**payload(1),'data':payload(1)['data'][:10]},payload(2)):
            with self.assertRaises(ValueError):validate_payload(data,1)
