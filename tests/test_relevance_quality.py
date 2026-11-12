import unittest
from radar.relevance import classify,classification_version
from radar.profiles import load_profiles


class RelevanceQualityTests(unittest.TestCase):
    def test_positive_paraphrases_and_ead(self):
        for obj in ('Prestação de serviços de apoio às rotinas administrativas',
                    'Contratação de serviços de ensino na modalidade a distância para graduação e pós-graduação'):
            with self.subTest(obj=obj):
                result=classify(obj)
                self.assertGreaterEqual(result['scores']['Public'],60)
                self.assertEqual(result['decisionByCompany']['Public']['status'],'selected')

    def test_context_negation_and_presential_are_not_recommendations(self):
        for obj in ('Contratação de seguro para participantes de cursos profissionalizantes',
                    'Contratação de empresa especializada para isolamento e tratamento acústico da sala de edição e realização de aulas de ensino à distância do IEP.',
                    'Contratação de serviços de manutenção, excluídos os cursos de capacitação de servidores',
                    'Modernização do auditório onde ocorrem palestras',
                    'Contratação de curso de graduação presencial em medicina'):
            with self.subTest(obj=obj):
                result=classify(obj)
                self.assertEqual(result['scores']['Public'],0)
                self.assertEqual(result['decisionByCompany']['Public']['status'],'excluded')

    def test_mixed_object_requires_review(self):
        result=classify('Fornecimento de material didático e realização de cursos de capacitação de servidores')
        self.assertEqual(result['scores']['Public'],45)
        self.assertIn('mixed_object',result['decisionByCompany']['Public']['reasonCodes'])
        mixed=classify('Licenciamento de software e realização de cursos de capacitação de servidores')
        self.assertEqual(mixed['scores']['Public'],45)
        self.assertEqual(mixed['decisionByCompany']['Public']['status'],'review')

    def test_evidence_offsets_are_source_text_and_other_company_is_unconfigured(self):
        obj='Serviços de apoio às rotinas administrativas para a secretaria'
        result=classify(obj)
        for evidence in result['decisionByCompany']['Public']['evidence']:
            self.assertEqual(obj[evidence['start']:evidence['end']],evidence['matchedText'])
        self.assertEqual(result['decisionByCompany']['Gerico']['status'],'unconfigured')
        self.assertEqual(result['scores']['Gerico'],0)

    def test_version_fingerprint_changes_with_profile(self):
        profiles=load_profiles();old=classification_version(profiles)
        profiles[0]['terms'].append('novo critério de revisão')
        self.assertNotEqual(old,classification_version(profiles))
