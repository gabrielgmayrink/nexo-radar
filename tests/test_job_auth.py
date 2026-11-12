from unittest.mock import patch
import time
import unittest
from types import SimpleNamespace
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from radar.job_auth import authenticate,verify_claims,AUDIENCE,ISSUER,WORKFLOW,SUBJECTS


@patch('radar.job_auth.REPOSITORY_ID', 'test-repository')
class JobAuthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        cls.client=SimpleNamespace(get_signing_key_from_jwt=lambda token:SimpleNamespace(key=cls.key.public_key()))

    def claims(self):
        now=int(time.time())
        return {'iss':ISSUER,'aud':AUDIENCE,'iat':now,'nbf':now-1,'exp':now+300,
                'sub':next(iter(SUBJECTS)),'repository':'gabrielgmayrink/nexo-radar',
                'repository_id':'test-repository','repository_owner_id':'169843370',
                'repository_visibility':'private','ref':'refs/heads/main','workflow_ref':WORKFLOW,
                'event_name':'workflow_dispatch','run_id':'123','run_attempt':'1'}

    def check(self,claims):
        token=jwt.encode(claims,self.key,algorithm='RS256')
        return authenticate('Bearer '+token,key_client=self.client)

    def test_valid_identity_and_immutable_subject(self):
        for subject in SUBJECTS:
            claims=self.claims();claims['sub']=subject
            self.assertEqual(self.check(claims),'123:1')

    def test_expired_wrong_audience_or_issuer_rejected(self):
        for field,value in [('exp',int(time.time())-60),('aud','https://attacker.example'),('iss','https://attacker.example')]:
            claims=self.claims();claims[field]=value
            with self.assertRaises(jwt.InvalidTokenError):self.check(claims)

    def test_other_repository_workflow_branch_and_pull_request_rejected(self):
        for field,value in [('repository_id','1'),('repository_owner_id','1'),('ref','refs/heads/other'),
                            ('workflow_ref',WORKFLOW.replace('collect.yml','other.yml')),('event_name','pull_request'),
                            ('repository_visibility','public')]:
            claims=self.claims();claims[field]=value
            with self.assertRaises(ValueError):self.check(claims)

    def test_forged_signature_and_missing_expiry_rejected(self):
        claims=self.claims()
        bad_key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        token=jwt.encode(claims,bad_key,algorithm='RS256')
        with self.assertRaises(jwt.InvalidTokenError):authenticate('Bearer '+token,key_client=self.client)
        del claims['exp']
        with self.assertRaises(jwt.InvalidTokenError):self.check(claims)

    def test_unsigned_request_rejected_before_key_fetch(self):
        with self.assertRaises(ValueError):authenticate('')

    def test_notification_identity_cannot_collect_and_collect_identity_cannot_send(self):
        claims=self.claims()
        token=jwt.encode(claims,self.key,algorithm='RS256')
        with self.assertRaises(jwt.InvalidTokenError):authenticate('Bearer '+token,key_client=self.client,purpose='notify')
        claims['aud']=AUDIENCE.rsplit('/',1)[0]+'/notify'
        claims['workflow_ref']=WORKFLOW.replace('collect.yml','notify.yml')
        token=jwt.encode(claims,self.key,algorithm='RS256')
        self.assertEqual(authenticate('Bearer '+token,key_client=self.client,purpose='notify'),'123:1')
        with self.assertRaises(jwt.InvalidTokenError):authenticate('Bearer '+token,key_client=self.client)

    def test_independent_health_identity_cannot_mutate_collection(self):
        claims=self.claims();claims['workflow_ref']=WORKFLOW.replace('collect.yml','health.yml')
        token=jwt.encode(claims,self.key,algorithm='RS256')
        self.assertEqual(authenticate('Bearer '+token,key_client=self.client,purpose='health'),'123:1')
        with self.assertRaises(ValueError):authenticate('Bearer '+token,key_client=self.client,purpose='collect')
