import unittest
from radar.catalog_query import options,filter_sql,private_card
from radar.relevance import classify

class CatalogQueryTests(unittest.TestCase):
    def test_company_synonyms_and_organization_scope_are_parameterized(self):
        sql,params=filter_sql(options({'q':['backoffice']}),{'synonyms':{'apoio administrativo':['backoffice']},'organizations':['Prefeitura de São Paulo']})
        self.assertIn(' apoio administrativo ',params)
        self.assertIn(['prefeitura de sao paulo'],params)
        self.assertIn('radar_item_search',sql)
    def test_query_language_is_parameterized_and_preserves_exclusions(self):
        config=options({'q':['"apoio administrativo" -seguro'], 'city':["Belo Horizonte' or true --"],'minValue':['0'],'publishedTo':['2026-11-11']})
        sql,params=filter_sql(config)
        self.assertNotIn('Belo Horizonte',sql);self.assertNotIn('seguro',sql)
        self.assertIn('not (',sql);self.assertIn(' apoio administrativo ',params)
        self.assertIn('belo horizonte or true',params);self.assertIn('2026-11-11',params)

    def test_profile_limits_remain_server_controlled_and_optional(self):
        sql,params=filter_sql(options({}),{'states':['MG','ES'],'cities':['São Paulo'],'minValue':100})
        self.assertIn('uf=any(%s)',sql);self.assertIn(['MG','ES'],params);self.assertIn(['sao paulo'],params)
        self.assertIn(100,params)

    def test_discovery_can_return_zero_without_exposing_other_company_decisions(self):
        obj='Aquisição de materiais para modernização de auditório onde acontecem palestras.'
        stored={'id':'12345678000100-1-000001/2026','object':obj,'evidence':[],**classify(obj)}
        card=private_card({'objetoCompra':obj},stored,'public',review_candidate=True)
        self.assertTrue(card['reviewCandidate']);self.assertEqual(card['score'],0)
        self.assertEqual(set(card['scores']),{'Public'});self.assertEqual(set(card['decisionByCompany']),{'Public'})
