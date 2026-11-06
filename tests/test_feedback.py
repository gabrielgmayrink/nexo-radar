import io
import json
import os
import unittest
from unittest.mock import patch
from radar.feedback_security import sign_feedback, verify_feedback, InvalidFeedbackToken
from api.feedback import handler, save_feedback

SECRET = 'unit-test-only-signing-fixture-' * 2
IDENTIFIER = '48031918000124-1-002720/2026'


class FeedbackTests(unittest.TestCase):
    def test_signature_expiry_and_tampering(self):
        token=sign_feedback(IDENTIFIER,'public','irrelevante',SECRET,now=100,ttl=60)
        self.assertEqual(verify_feedback(token,SECRET,now=159)['label'],'irrelevante')
        for invalid,now in [(token,160),(token+'x',100),(token.replace('a','b',1),100)]:
            with self.assertRaises(InvalidFeedbackToken):verify_feedback(invalid,SECRET,now=now)

    def test_other_secret_cannot_verify(self):
        token=sign_feedback(IDENTIFIER,'gerico','relevante',SECRET)
        with self.assertRaises(InvalidFeedbackToken):verify_feedback(token,'other-unit-test-fixture-'*3)

    def test_rejects_long_lived_link(self):
        with self.assertRaises(InvalidFeedbackToken):sign_feedback(IDENTIFIER,'public','relevante',SECRET,ttl=31*86400)

    def test_get_validates_without_writing(self):
        token=sign_feedback(IDENTIFIER,'public','irrelevante',SECRET)
        instance=object.__new__(handler); instance.path='/api/feedback?token='+token
        result=[];instance.respond=lambda code,body:result.append((code,body))
        with patch.dict(os.environ,{'RADAR_SHARED_FEEDBACK_ENABLED':'1','SUPABASE_URL':'https://unit-test.supabase.co','SUPABASE_SECRET_KEY':'unit-test-only','FEEDBACK_SIGNING_SECRET':SECRET}),patch('api.feedback.save_feedback') as save:
            instance.do_GET()
            save.assert_not_called()
            self.assertEqual(result[0][0],200)
            self.assertFalse(result[0][1]['saved'])

    def test_post_rejects_invalid_token_before_storage(self):
        instance=object.__new__(handler);payload=b'{"token":"invalid"}'
        instance.headers={'Content-Length':str(len(payload))};instance.rfile=io.BytesIO(payload)
        result=[];instance.respond=lambda code,body:result.append((code,body))
        with patch.dict(os.environ,{'RADAR_SHARED_FEEDBACK_ENABLED':'1','SUPABASE_URL':'https://unit-test.supabase.co','SUPABASE_SECRET_KEY':'unit-test-only','FEEDBACK_SIGNING_SECRET':SECRET}),patch('api.feedback.save_feedback') as save:
            instance.do_POST();save.assert_not_called();self.assertEqual(result[0][0],403)

    def test_no_configuration_makes_no_external_request(self):
        instance=object.__new__(handler);instance.path='/api/feedback?token=anything'
        result=[];instance.respond=lambda code,body:result.append(code)
        with patch.dict(os.environ,{},clear=True),patch('api.feedback.save_feedback') as save:
            instance.do_GET();save.assert_not_called();self.assertEqual(result,[503])

    def test_credentials_alone_do_not_enable_feedback(self):
        instance=object.__new__(handler);instance.path='/api/feedback?token=anything'
        result=[];instance.respond=lambda code,body:result.append(code)
        with patch.dict(os.environ,{'SUPABASE_URL':'https://unit-test.supabase.co','SUPABASE_SECRET_KEY':'unit-test-only','FEEDBACK_SIGNING_SECRET':SECRET},clear=True),patch('api.feedback.save_feedback') as save:
            instance.do_GET();save.assert_not_called();self.assertEqual(result,[503])

    def test_upsert_is_bound_to_signed_event_and_fixed_destination(self):
        claims=verify_feedback(sign_feedback(IDENTIFIER,'public','irrelevante',SECRET),SECRET)
        requests=[]
        class Response:
            status=201
            def __enter__(self):return self
            def __exit__(self,*args):pass
        def opener(request,**kwargs):requests.append(request);return Response()
        with patch.dict(os.environ,{'SUPABASE_URL':'https://unit-test.supabase.co','SUPABASE_SECRET_KEY':'unit-test-only'}):
            save_feedback(claims,opener=opener)
        self.assertIn('on_conflict=event_id',requests[0].full_url)
        self.assertEqual(json.loads(requests[0].data)['event_id'],claims['event_id'])
        self.assertNotIn('token',json.loads(requests[0].data))

if __name__=='__main__':unittest.main()
