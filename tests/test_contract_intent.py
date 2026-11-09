"""Distinguish the purchased service from its setting and ancillary services."""
import io
import json
import unittest
from unittest.mock import patch

from radar.canonical import to_card
from radar.catalog_storage import load_database_catalog
from radar.relevance import classify


class ContractIntentTests(unittest.TestCase):
    def test_context_and_bundled_services_do_not_select_public(self):
        objects = [
            'Contratação de serviços para MODERNIZAÇÃO DO AUDITÓRIO DO CENTRO ADMINISTRATIVO DE NITERÓI, com vistas a requalificar o espaço físico onde é realizado eventos institucionais, reuniões, palestras e atividades oficiais, por meio de melhorias estruturais.',
            'Compra de materiais para eventos e palestras de desenvolvimento profissional',
            'Aquisição de mobiliário para cursos técnicos e profissionalizantes',
            'Fornecimento de brindes para palestras de desenvolvimento gerencial',
            'Fornecimento de equipamentos de apoio administrativo e educacional',
            'Aquisição de pedra bruta para a Área de Apoio Administrativo Almirante José Carlos',
            'Contratação de intérpretes de Libras para tradução de palestras e cursos técnicos',
            'Serviços de transporte de servidores para participação em cursos de capacitação',
            'Aquisição de kits de formatura para cursos de capacitação',
            'Fornecimento de coffee break para reuniões, palestras e capacitação de servidores',
            'Licenciamento de Sistema Integrado de Gestão Pública, contemplando treinamento de servidores',
            'Licença de plataforma online de treinamento auditivo e cognitivo para profissionais',
            'Equipamentos radiográficos incluindo instalação, treinamento de pessoal e manutenção',
            'Auditoria de recertificação do Ensino Profissional Marítimo, incluindo capacitação de servidores',
            'Disponibilização de unidade móvel com médicos, equipamentos e apoio administrativo',
            'Produção audiovisual com gravação e entrega de material para cursos profissionalizantes',
            'Fornecimento de reagentes para atividades dos cursos técnicos',
            'Reforma do centro de treinamento profissional',
            'Serviços especializados na área da química, compreendendo responsabilidade técnica, assessoria técnica, controle da qualidade da água, incluindo elaboração de laudos e documentos técnicos',
            'Assessoria técnica em engenharia, incluindo relatórios e documentos administrativos',
        ]
        for obj in objects:
            with self.subTest(obj=obj):
                self.assertEqual(classify(obj)['score'], 0)

    def test_real_services_remain_even_when_the_topic_or_venue_is_unrelated(self):
        objects = [
            'Contratação de palestrante para ministrar palestra de desenvolvimento profissional',
            'Contratação de palestra sobre modernização de auditórios',
            'Curso de capacitação de servidores sobre licenciamento de software',
            'Treinamento profissional de operadores de equipamentos',
            'Serviços de apoio administrativo para hospital e unidade móvel',
            'Empresa destinada à prestação de serviços de apoio administrativo',
            'Curso de pós-graduação EAD com plataforma online e material didático',
            'Assessoria em gestão pública, incluindo capacitação de servidores',
            'Palestras a serem realizadas no auditório da prefeitura',
            'Preparação de documentos para contratação de equipamentos',
        ]
        for obj in objects:
            with self.subTest(obj=obj):
                result = classify(obj)
                self.assertEqual(result['suggestedOffer'], 'Public')
                self.assertTrue(all('objeto principal' in reason for reason in result['evidence']))

    def test_related_service_with_recipient_after_secondary_clause_is_reviewable(self):
        for obj in [
            'Capacitação e treinamento teórico-prático de brigada de incêndio, destinada a 50 servidores do hospital',
            'Organização e execução de capacitação destinada aos professores e servidores, incluindo confraternização',
            'Assessoria técnica na gestão administrativa de pessoal, compreendendo orientação aos servidores',
            'Inscrição de servidores em curso sobre contratações públicas',
        ]:
            with self.subTest(obj=obj):
                self.assertEqual(classify(obj)['score'], 45)

    def test_additional_information_does_not_promote_an_unrelated_object(self):
        self.assertEqual(classify('Compra de cadeiras', 'Uso em palestras e cursos técnicos')['score'], 0)

    def test_stored_false_positive_is_rejected_before_database_reclassification(self):
        row = {'numeroControlePNCP':'28521748000159-1-000244/2026',
               'objetoCompra':'Modernização do auditório para realização de palestras',
               'situacaoCompraId':1,'tipoInstrumentoConvocatorioCodigo':1,
               'dataEncerramentoProposta':'2099-12-31T23:00:00'}
        card = to_card(row)
        card.update(score=70,scores={'Public':70,'Gerico':0},ruleVersion='old',suggestedOffer='Public')
        def opener(request, **kwargs):
            data = [{'card':card}] if 'radar_national_candidates?' in request.full_url else []
            return io.BytesIO(json.dumps(data).encode())
        with patch.dict('os.environ', {'SUPABASE_URL':'https://unit-test.supabase.co','SUPABASE_SECRET_KEY':'unit-test-only'},clear=True):
            result = load_database_catalog({}, opener=opener, company='public')
        self.assertEqual(result['opportunities'], [])


if __name__ == '__main__':
    unittest.main()
