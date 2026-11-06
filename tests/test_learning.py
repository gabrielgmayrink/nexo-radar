import unittest
from radar.learning import apply_examples,object_hash


class LearningTests(unittest.TestCase):
    def setUp(self):
        self.obj='Contratação de assinatura de plataforma para pesquisa de preços e planejamento das contratações públicas, com acesso ao banco nacional.'
        self.card={'id':'new','object':self.obj,'additionalInfo':'','score':70}
        self.example={'opportunity_id':'reviewed','offer':'Nenhuma','reason_code':'produto_diferente',
                      'object_hash':object_hash(self.obj),'example_object':self.obj,'example_additional':''}

    def test_identical_object_uses_example_without_exposing_private_notes(self):
        result=apply_examples([self.card],[{**self.example,'actor':'private@example.com','reason':'Private note'}])[0]
        self.assertEqual(result['learning']['label'],'irrelevante')
        self.assertEqual(result['learning']['match'],'identical_object')
        self.assertNotIn('learning',self.card)
        self.assertNotIn('private@example.com',str(result));self.assertNotIn('Private note',str(result))

    def test_similar_negative_is_only_a_review_cue_never_rejected(self):
        result=apply_examples([{**self.card,'object':self.obj+' Serviço adicional.'}],[self.example])[0]
        self.assertEqual(result['learning']['label'],'revisar')
        self.assertEqual(result['learning']['match'],'similar_negative')
        self.assertEqual(result['score'],70)

    def test_conflicting_examples_require_review_and_direct_decision_wins(self):
        positive={**self.example,'opportunity_id':'positive','offer':'Daltton'}
        result=apply_examples([self.card],[self.example,positive])[0]
        self.assertEqual(result['learning']['match'],'conflicting_examples')
        direct={**positive,'opportunity_id':'new'}
        result=apply_examples([self.card],[self.example,direct])[0]
        self.assertEqual(result['learning']['label'],'relevante')

    def test_short_or_unrelated_objects_not_inferred_irrelevant(self):
        short={**self.card,'object':'Compra de software'}
        example={**self.example,'object_hash':object_hash(short['object']),'example_object':short['object']}
        self.assertNotIn('learning',apply_examples([short],[example])[0])
        unrelated={**self.card,'object':'Aquisição por importação de microscópio invertido com sistema óptico.'}
        self.assertNotIn('learning',apply_examples([unrelated],[self.example])[0])

    def test_additional_information_changes_identity(self):
        self.assertNotEqual(object_hash(self.obj),object_hash(self.obj,'Inclui licença do banco de preços'))

    def test_identical_positive_object_preserves_the_approved_product(self):
        example={**self.example,'offer':'Daltton','reason_code':'aderente'}
        learned=apply_examples([self.card],[example])[0]['learning']
        self.assertEqual(learned['label'],'relevante');self.assertEqual(learned['offer'],'Daltton')

    def test_contextual_rejection_does_not_discard_another_procurement(self):
        for reason in ('escopo_fora','edital_insuficiente','outro'):
            example={**self.example,'reason_code':reason}
            result=apply_examples([self.card],[example])[0]
            self.assertEqual(result['learning']['label'],'revisar')
            self.assertEqual(result['learning']['match'],'identical_context')
