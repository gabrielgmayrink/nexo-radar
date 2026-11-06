import unittest
from unittest.mock import patch
import json
from radar.profiles import load_profiles


class ProfileTests(unittest.TestCase):
    def test_public_uses_confirmed_services_and_gerico_remains_pending(self):
        companies=load_profiles()
        self.assertEqual([company['name'] for company in companies],['Public','Gerico'])
        self.assertTrue(companies[0]['enabled'])
        self.assertEqual(len(companies[0]['services']),4)
        self.assertNotIn('desenvolvimento de sistemas',companies[0]['terms'])
        self.assertFalse(companies[1]['enabled'])
        self.assertEqual(companies[1]['terms'],[])

    def test_public_matches_confirmed_scope_without_software(self):
        from radar.relevance import classify
        for obj in ('Assessoria e consultoria administrativa', 'Curso de capacitação de servidores', 'Contratação de palestra', 'Curso de pós-graduação EAD'):
            self.assertEqual(classify(obj)['suggestedOffer'],'Public',obj)
        for obj in ('Desenvolvimento de sistemas e software', 'Suporte técnico em informática', 'Aquisição de equipamentos de TI'):
            self.assertEqual(classify(obj)['score'],0,obj)

    def test_software_contracts_with_incidental_training_do_not_return_as_public(self):
        from radar.relevance import classify
        for obj in ('Solução de gestão municipal com licenciamento de uso de software, treinamento e capacitação dos usuários',
                    'Locação de software em ambiente web, com capacitação de servidores',
                    'Desenvolvimento de sistemas, consultoria em gestão pública e treinamento profissional'):
            self.assertEqual(classify(obj)['score'],0,obj)
        self.assertEqual(classify('Curso de capacitação de servidores em gestão de contratos')['suggestedOffer'],'Public')

    def test_enabling_incomplete_profile_is_rejected(self):
        companies=load_profiles()
        companies[1]['enabled']=True
        with patch('pathlib.Path.read_text',return_value=json.dumps({'companies':companies})):
            with self.assertRaises(ValueError):load_profiles()

    def test_related_training_variations_are_review_candidates_not_recommendations(self):
        from radar.relevance import classify
        result=classify('Inscrição de servidores em curso sobre contratações públicas')
        self.assertEqual(result['score'],45)
        self.assertEqual(result['suggestedOffer'],'Revisar')
        self.assertEqual(classify('Compra de notebooks com treinamento de instalação')['score'],0)
