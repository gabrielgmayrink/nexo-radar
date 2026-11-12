"""Opt-in real PostgreSQL tests. Only a local disposable database is permitted."""
import hashlib
import json
import os
import unittest
from datetime import date
from urllib.parse import urlparse
import psycopg
from radar.postgres_store import PostgresStore
from radar.sync import initial_cursor,advance
from radar.national_collection import finish_if_ready

DSN=os.environ.get('RADAR_TEST_POSTGRES_DSN')


def row(sequence,**extra):
    return {'numeroControlePNCP':f'99887766000190-1-{sequence:06d}/2026',
            'objetoCompra':'Contratação de serviços de assessoria em gestão pública',
            'dataAtualizacao':'2026-11-01T12:00:00Z',**extra}


@unittest.skipUnless(DSN,'Disposable local database not configured')
class IngestionIntegrationTests(unittest.TestCase):
    def setUp(self):
        options=psycopg.conninfo.conninfo_to_dict(DSN)
        if options.get('host') not in ('127.0.0.1','localhost') or not (options.get('dbname')=='postgres' or options.get('dbname','').startswith('radar_restore_test_')):
            raise ValueError('Integration tests require a disposable loopback PostgreSQL database')
        self.db=psycopg.connect(DSN,autocommit=True)
        self.transaction=self.db.transaction(force_rollback=True);self.transaction.__enter__()
        self.store=PostgresStore(self.db)
        self.execution=self.db.execute("insert into radar_executions(task,status) values('test:ingestion','running') returning id").fetchone()[0]

    def tearDown(self):
        self.transaction.__exit__(None,None,None);self.db.close()

    def capture(self,rows,number=1):
        page={'data':rows,'numeroPagina':1,'totalRegistros':len(rows),'totalPaginas':1}
        capture=self.store.capture_page(self.execution,number,1,page)
        return capture,page

    def test_bulk_storage_constraint_quarantines_only_bad_row_and_keeps_original(self):
        rows=[row(910001),row(910002,objetoCompra='Objeto com nul\x00 inválido'),row(910003)]
        receipt,_=self.capture(rows)
        indexed=self.store.ingest_capture(receipt,rows)
        self.assertEqual(indexed,[rows[0]['numeroControlePNCP'],rows[2]['numeroControlePNCP']])
        observations=self.db.execute('select ordinal,parse_state from radar_source_observations where capture_id=%s order by ordinal',(receipt,)).fetchall()
        self.assertEqual(observations,[(0,'indexed'),(1,'quarantined'),(2,'indexed')])
        self.assertEqual(self.db.execute('select reason from radar_quarantine where capture_id=%s and ordinal=1',(receipt,)).fetchone()[0],'record_storage_failed')
        import gzip
        raw=self.db.execute('select payload_gzip from radar_source_pages where id=%s',(receipt,)).fetchone()[0]
        self.assertEqual(json.loads(gzip.decompress(bytes(raw)))['data'],rows)

    def test_national_receipt_proof_uses_two_full_membership_and_hash_sets(self):
        cursor=initial_cursor('national_open',date(2026,11,11))
        for number in (1,2):
            rows=[row(920001),row(920002)]
            receipt,page=self.capture(rows,number)
            cursor=advance(cursor,rows,page)
            digest=hashlib.sha256(json.dumps(page,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
            self.store.commit_national_page(self.execution,rows,cursor,1,digest,2,1,capture_id=receipt)
            cursor=finish_if_ready(self.store,cursor,self.execution)
            self.assertEqual(cursor['coverageComplete'],number==2)
        self.assertEqual(cursor['consistency'],'stable_sets')

    def test_same_counts_changed_id_does_not_claim_consistency_in_real_ledger(self):
        cursor=initial_cursor('national_open',date(2026,11,11))
        for number in (1,2):
            rows=[row(930001),row(930002 if number==1 else 930003)]
            receipt,page=self.capture(rows,number)
            cursor=advance(cursor,rows,page)
            digest=hashlib.sha256(json.dumps(page,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
            self.store.commit_national_page(self.execution,rows,cursor,1,digest,2,1,capture_id=receipt)
            cursor=finish_if_ready(self.store,cursor,self.execution)
        self.assertTrue(cursor['captureComplete']);self.assertFalse(cursor['coverageComplete'])
        self.assertEqual(cursor['consistency'],'source_changed')

    def test_official_changes_are_transactional_idempotent_and_stale_safe(self):
        original=row(940001,dataEncerramentoProposta='2026-11-20T12:00:00')
        receipt,_=self.capture([original]);self.store.ingest_capture(receipt,[original])
        changed={**original,'dataEncerramentoProposta':'2026-12-20T12:00:00','dataAtualizacao':'2026-11-02T12:00:00Z'}
        receipt,_=self.capture([changed]);self.store.ingest_capture(receipt,[changed]);self.store.ingest_capture(receipt,[changed])
        receipt,_=self.capture([original]);self.store.ingest_capture(receipt,[original])
        events=self.db.execute('select kind,old_value,new_value from radar_procurement_events where opportunity_id=%s',(original['numeroControlePNCP'],)).fetchall()
        self.assertEqual(events,[('deadline_changed',original['dataEncerramentoProposta'],changed['dataEncerramentoProposta'])])
        saved=self.db.execute('select payload from radar_opportunities where id=%s',(original['numeroControlePNCP'],)).fetchone()[0]
        self.assertEqual(saved,changed)
