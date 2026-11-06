import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from radar.relevance import classify, procurement_state


class RelevanceTests(unittest.TestCase):
    def test_false_positives(self):
        for text in [
            "Aquisição por importação de microscópio invertido, com sistema óptico corrigido para infinito",
            "Sistema de Registro de Preços para aquisição de material de expediente conforme Termo de Referência",
            "Locação de software de videoconferência",
            "Aquisição de plataforma elevatória",
            "Aquisição de medicamentos conforme pesquisa de preços realizada pelo setor",
            "A presente pesquisa de preço refere-se a procedimento cirúrgico de castração",
        ]:
            self.assertLess(classify(text)["score"], 60, text)

    def profiles(self):
        # Synthetic examples for testing, not services assigned to the companies.
        return [
            {'name':'Public','enabled':True,'terms':['manutenção de bombas'],'excludeTerms':['peças avulsas']},
            {'name':'Gerico','enabled':True,'terms':['locação de andaimes'],'excludeTerms':[]},
        ]

    def test_unconfigured_companies_never_reuse_previous_products(self):
        for text in ('Licença de plataforma de pesquisa de preços','Digitalização de documentos'):
            result=classify(text,profiles=[])
            self.assertEqual(result['score'],0)
            self.assertTrue(result['configurationPending'])

    def test_public_services_include_administrative_training_and_ead(self):
        for text in ('Serviços de apoio administrativo','Palestras para desenvolvimento gerencial','Cursos técnicos por ensino a distância'):
            self.assertEqual(classify(text)['suggestedOffer'],'Public')

    def test_gerico_is_not_suggested_before_services_are_known(self):
        self.assertEqual(classify('Desenvolvimento de software')['scores']['Gerico'],0)

    def test_independent_and_overlapping_company_scopes(self):
        self.assertEqual(classify('Serviços de MANUTENÇÃO de bombas',profiles=self.profiles())['suggestedOffer'],'Public')
        self.assertEqual(classify('Locação de andaimes',profiles=self.profiles())['suggestedOffer'],'Gerico')
        self.assertEqual(classify('Manutenção de bombas e locação de andaimes',profiles=self.profiles())['suggestedOffer'],'Ambas')

    def test_exclusions_disabled_profiles_and_word_boundaries(self):
        profiles=self.profiles()
        self.assertEqual(classify('Manutenção de bombas: peças avulsas',profiles=profiles)['score'],0)
        profiles[0]['enabled']=False
        self.assertEqual(classify('Manutenção de bombas',profiles=profiles)['score'],0)
        self.assertEqual(classify('Realocação de andaimes',profiles=profiles)['score'],0)

    def test_additional_information_alone_cannot_recommend_a_company(self):
        result=classify('Equipamentos','Manutenção de bombas',profiles=self.profiles())
        self.assertEqual(result['score'],20)
        self.assertEqual(result['suggestedOffer'],'Revisar')

    def test_additional_boilerplate_not_promoted(self):
        self.assertLess(classify("Aquisição de equipamentos", "Pesquisa de preços com software")["score"], 40)

    def test_status_and_timezone(self):
        now = datetime(2026, 11, 4, 10, tzinfo=ZoneInfo("America/Sao_Paulo"))
        row = {"situacaoCompraId": 1, "tipoInstrumentoConvocatorioCodigo": 1, "dataEncerramentoProposta": "2026-11-04T11:00:00"}
        self.assertEqual(procurement_state(row, now), "Recebendo propostas")
        row["situacaoCompraId"] = 4
        self.assertEqual(procurement_state(row, now), "Inativa")


if __name__ == "__main__":
    unittest.main()
