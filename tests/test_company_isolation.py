import io
import json
import unittest
from unittest.mock import MagicMock,patch
from radar.company_access import AccessDenied,resolve_access,visible_card
from radar.team_reviews import list_reviews,save_review
from api.index import handler


class CompanyIsolationTests(unittest.TestCase):
    def test_membership_is_authoritative_even_for_forged_company_parameters(self):
        db=MagicMock();db.execute.return_value.fetchall.return_value=[('public',)]
        with patch('radar.company_access.session_user',return_value='public@example.com'):
            self.assertEqual(resolve_access(db,'cookie','public')[1],'public')
            with self.assertRaises(AccessDenied):resolve_access(db,'cookie','gerico')
            with self.assertRaises(AccessDenied):resolve_access(db,'cookie','public or gerico')

    def test_anonymous_requests_never_read_the_catalog(self):
        instance=object.__new__(handler);instance.headers={};instance.path='/api/opportunities'
        output=[];instance.respond=lambda code,body:output.append((code,body))
        with patch('api.index.load_catalog_page') as load:
            instance.do_GET()
        self.assertEqual(output[0][0],401);load.assert_not_called()

    def test_other_company_scores_and_evidence_are_removed(self):
        card={'id':'same','score':90,'scores':{'Public':70,'Gerico':90},'suggestedOffer':'Ambas','evidence':['Public: apoio administrativo','Gerico: other']}
        public=visible_card(card,'public');gerico=visible_card(card,'gerico')
        self.assertEqual(public['scores'],{'Public':70})
        self.assertEqual(public['evidence'],['Public: apoio administrativo'])
        self.assertEqual(gerico['scores'],{'Gerico':90})
        self.assertIsNone(visible_card({**card,'scores':{'Public':0,'Gerico':90}},'public'))

    def test_reviews_are_read_with_a_required_company_predicate(self):
        db=MagicMock();db.execute.return_value.fetchall.return_value=[]
        list_reviews(db,'gerico')
        sql,parameters=db.execute.call_args.args
        self.assertIn('r.company_id=%s',sql);self.assertEqual(parameters,('gerico',200,0))

    def test_review_cannot_assign_another_company_even_before_database_access(self):
        db=MagicMock()
        data={'id':'12345678000100-1-000001/2026','offer':'Gerico','status':'Nova','reason':'','version':0}
        with self.assertRaises(AccessDenied):save_review(db,data,'public@example.com','public')
        db.execute.assert_not_called()

    def test_signed_feedback_for_another_company_cannot_be_saved(self):
        from api.feedback import handler as FeedbackHandler
        from radar.feedback_security import sign_feedback
        secret='unit-test-only-private-signing-value-'*2
        token=sign_feedback('12345678000100-1-000001/2026','gerico','relevante',secret)
        instance=object.__new__(FeedbackHandler);instance.headers={}
        output=[];instance.respond=lambda code,body:output.append((code,body))
        with patch('api.feedback.configured',return_value=True),patch.dict('os.environ',{'FEEDBACK_SIGNING_SECRET':secret}),patch('api.feedback.request_access',return_value=('public@example.com','public',['public'])),patch('api.feedback.save_feedback') as save:
            instance.handle_feedback(token,write=True)
        self.assertEqual(output[0][0],403);save.assert_not_called()
