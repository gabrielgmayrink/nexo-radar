"""Full SQL acceptance on an explicitly disposable loopback database, always rolled back."""
import os
import unittest
from unittest.mock import patch
import psycopg
from psycopg.types.json import Jsonb
from radar.postgres_store import PostgresStore
from radar.catalog_query import load_catalog_page
from radar.team_reviews import save_review

DSN=os.environ.get('RADAR_TEST_POSTGRES_DSN')

@unittest.skipUnless(DSN,'Disposable local database not configured')
class CatalogPostgresTests(unittest.TestCase):
    def setUp(self):
        options=psycopg.conninfo.conninfo_to_dict(DSN)
        if options.get('host') not in ('127.0.0.1','localhost') or not options.get('dbname','').startswith('radar_restore_test_'):raise ValueError('Disposable database required')
        self.db=psycopg.connect(DSN,autocommit=True,connect_timeout=5)
        self.tx=self.db.transaction(force_rollback=True);self.tx.__enter__();self.store=PostgresStore(self.db)
        self.db.execute('delete from radar_company_profiles') # test-local preferences, restored by rollback
        self.row={'numeroControlePNCP':'99887766000190-1-990001/2026','objetoCompra':'Contratação de apoio administrativo especializado para rotinas da secretaria',
            'situacaoCompraId':1,'tipoInstrumentoConvocatorioCodigo':1,'dataEncerramentoProposta':'2099-01-01T12:00:00',
            'modalidadeNome':'Pregão - Eletrônico','dataPublicacaoPncp':'2026-11-11T10:00:00',
            'unidadeOrgao':{'ufSigla':'MG','municipioNome':'Cidade de homologação'},'orgaoEntidade':{'cnpj':'99887766000190','razaoSocial':'Órgão de homologação'}}
        self.store.write_records([self.row]);self.identifier=self.row['numeroControlePNCP']
    def tearDown(self):self.tx.__exit__(None,None,None);self.db.close()
    def page(self,company='public',**filters):return load_catalog_page({},company,{k:[str(v)] for k,v in filters.items()},self.db,status_loader=lambda:{})
    def test_captured_record_visible_before_first_national_completion(self):
        self.db.execute("delete from radar_catalog_state where id='open'")
        page=self.page(q='"Órgão de homologação"')
        self.assertEqual(page['total'],1);self.assertFalse(page['coverageComplete'])
        self.assertEqual(set(page['opportunities'][0]['scores']),{'Public'})
        self.assertEqual(self.page('gerico',q='homologação')['total'],0)
    def test_searches_enriched_items_without_duplicating_the_procurement(self):
        sha=self.db.execute('select content_hash from radar_opportunities where id=%s',(self.identifier,)).fetchone()[0]
        for source in ('pncp','compras_gov'):
            self.db.execute('insert into radar_item_search values(%s,%s,%s,%s,%s)',(self.identifier,sha,source,'1','consultoria estrategica municipal'))
        result=self.page(q='estratégica municipal');self.assertEqual(result['total'],1)
    def test_checklist_owner_and_closed_tracked_record_survive_reload(self):
        review={'id':self.identifier,'offer':'Public','status':'Vou participar','reason':'Acompanhar teste','version':0,
            'reasonCode':'aderente','expectedScope':'','sourceObject':self.row['objetoCompra'],'sourceAdditional':'',
            'owner':'Analista QA','checklist':[{'id':'edital','label':'Conferir edital','done':True}]}
        save_review(self.db,review,'public.qa@example.com','public')
        self.db.execute("update radar_opportunities set payload=jsonb_set(payload,'{dataEncerramentoProposta}','\"2020-01-01T12:00:00\"'),catalog_seen_at='2019-01-01' where id=%s",(self.identifier,))
        self.db.execute("insert into radar_catalog_state(id,content) values('open',%s) on conflict(id) do update set content=excluded.content",(Jsonb({'completedAt':'2026-11-11T00:00:00Z','executionId':0}),))
        result=self.page(view='tracked');found=result['pageReviews'][self.identifier]
        self.assertEqual(found['owner'],'Analista QA');self.assertTrue(found['checklist'][0]['done'])
    def test_suspended_is_official_status_four(self):
        self.db.execute("update radar_opportunities set payload=jsonb_set(payload,'{situacaoCompraId}','4') where id=%s",(self.identifier,))
        self.assertEqual(self.page(q='homologação',situation='suspended')['total'],1)
        self.assertEqual(self.page(q='homologação',situation='open')['total'],0)

    def test_restricted_role_blocks_cross_company_profile_write(self):
        from radar.database_roles import company_transaction
        self.db.execute("insert into radar_memberships(email,company_id,role) values('role.qa@example.com','public','owner') on conflict do nothing")
        with patch.dict(os.environ,{'RADAR_DB_ENFORCE_ROLES':'1'}),company_transaction(self.db,'role.qa@example.com','public'):
            self.assertEqual(self.db.execute('select current_user').fetchone()[0],'radar_web')
            with self.assertRaises(psycopg.errors.InsufficientPrivilege),self.db.transaction():
                self.db.execute("insert into radar_company_profiles(company_id,configuration,actor) values('gerico','{}','role.qa@example.com')")
            self.assertEqual(self.db.execute("select count(*) from radar_company_profiles where company_id='gerico'").fetchone()[0],0)
