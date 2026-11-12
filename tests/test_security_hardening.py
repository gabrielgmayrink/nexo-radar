import base64
import io
import json
import os
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock,Mock,patch
import jwt
from cryptography.exceptions import InvalidTag
from radar.access_security import request_origin,throttle
from radar.backup import encrypt_archive,decrypt_archive,backup_key
from radar.database_tls import tls_parameters
from radar.mfa import MFARequired,finish_first_factor,verify,enroll
from radar.password_auth import AuthenticationFailed,password_login,setup_password
from radar.team_auth import session_user,digest
from radar.team_reviews import validate_review

USER={'id':'c39141b5-826d-41cc-95a5-35f16c57e657','email':'member@example.com','email_confirmed_at':'2026-11-06'}
FACTOR='946778ca-cd47-4898-a8aa-86ec97bf349b'
TOKEN='p'*43
TEMP_ROOT=Path(__file__).resolve().parents[1]/'.local'
TEMP_ROOT.mkdir(exist_ok=True)


class MFAFlowTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'RADAR_TEAM_EMAILS':USER['email'],'RADAR_MFA_REQUIRED_EMAILS':'',
            'RADAR_AUTH_ENCRYPTION_KEY':base64.urlsafe_b64encode(b'x'*32).decode()})
        self.env.start();self.addCleanup(self.env.stop)
        self.generation=0;self.pending=None;self.db=MagicMock()
        def execute(sql,args=()):
            if 'select count(*)' in sql:return SimpleNamespace(fetchone=lambda:(0,))
            if 'select generation,require_mfa' in sql:return SimpleNamespace(fetchone=lambda:(self.generation,False,None))
            if 'insert into radar_mfa_pending' in sql:
                self.pending=(args[1],args[2],args[3],args[4],json.loads(args[5]),args[6])
            if 'from radar_mfa_pending where' in sql:return SimpleNamespace(fetchone=lambda:self.pending)
            if 'returning email' in sql:return SimpleNamespace(fetchone=lambda:(USER['email'],))
            return MagicMock()
        self.db.execute.side_effect=execute

    def start(self):
        user={**USER,'factors':[{'id':FACTOR,'factor_type':'totp','status':'verified'}]}
        with self.assertRaises(MFARequired) as caught:
            finish_first_factor(self.db,{'user':user,'access_token':'first-factor-token-value'},USER['email'],0)
        return caught.exception.response['pendingToken']

    def provider(self,aal='aal2',user=None):
        token=jwt.encode({'aal':aal,'sub':USER['id'],'exp':int(time.time())+60},'unit-test-only-signing-key-32-bytes',algorithm='HS256')
        def request(path,payload=None,**kwargs):
            if path.endswith('/challenge'):return {'id':'provider-challenge'}
            if path.endswith('/verify'):return {'access_token':token}
            if path=='user':return user or USER
            raise AssertionError('Unexpected Auth path')
        return Mock(side_effect=request)

    def test_first_factor_is_encrypted_and_does_not_issue_app_session(self):
        pending=self.start()
        self.assertEqual(len(pending),43)
        self.assertNotIn(b'first-factor-token-value',self.pending[3])
        self.assertFalse(any('insert into radar_team_sessions' in c.args[0] for c in self.db.execute.call_args_list))

    def test_second_factor_requires_provider_identity_and_aal2(self):
        for assurance,user in [('aal1',USER),('aal2',{**USER,'email':'other@example.com'})]:
            pending=self.start()
            with self.assertRaises(AuthenticationFailed):verify(self.db,pending,FACTOR,'123456',provider=self.provider(assurance,user))
        pending=self.start();provider=self.provider()
        email,session=verify(self.db,pending,FACTOR,'123456',provider=provider)
        self.assertEqual(email,USER['email']);self.assertEqual(len(session),43)
        self.assertEqual(provider.call_args_list[-1].args[0],'user')
        insert=next(c for c in self.db.execute.call_args_list if 'insert into radar_team_sessions' in c.args[0])
        self.assertEqual(insert.args[1][0],digest(session));self.assertEqual(insert.args[1][5],'aal2')

    def test_wrong_factor_expired_pending_or_revocation_cannot_reach_provider(self):
        pending=self.start();provider=self.provider()
        with self.assertRaises(AuthenticationFailed):verify(self.db,pending,'not-authorized','123456',provider=provider)
        self.generation=1
        with self.assertRaises(AuthenticationFailed):verify(self.db,pending,FACTOR,'123456',provider=provider)
        self.pending=None
        with self.assertRaises(AuthenticationFailed):verify(self.db,pending,FACTOR,'123456',provider=provider)
        provider.assert_not_called()

    def test_password_reset_race_rejects_old_first_factor(self):
        def provider(*args):
            self.generation=1
            return {'user':USER}
        with self.assertRaises(AuthenticationFailed):password_login(self.db,USER['email'],'password',provider=provider)
        self.assertFalse(any('insert into radar_team_sessions' in c.args[0] for c in self.db.execute.call_args_list))

    def test_enrollment_is_only_available_after_required_first_factor(self):
        with patch.dict(os.environ,{'RADAR_MFA_REQUIRED_EMAILS':USER['email']}):
            with self.assertRaises(MFARequired) as caught:
                finish_first_factor(self.db,{'user':USER,'access_token':'first-factor-token-value'},USER['email'],0)
        pending=caught.exception.response['pendingToken']
        self.assertTrue(caught.exception.response['enrollmentRequired'])
        result=enroll(self.db,pending,provider=lambda *a,**k:{'id':FACTOR,'totp':{'qr_code':'<svg xmlns="http://www.w3.org/2000/svg"></svg>','secret':'never-return'}})
        self.assertTrue(result['qrCode'].startswith('data:image/svg+xml;base64,'));self.assertNotIn('secret',result)


class SecurityBoundaryTests(unittest.TestCase):
    def test_tls_refuses_downgrade_and_invalid_certificate(self):
        self.assertEqual(tls_parameters({'sslmode':'disable'},environ={})['sslmode'],'verify-full')
        self.assertEqual(tls_parameters({},environ={})['sslrootcert'],'system')
        with self.assertRaises(ValueError):tls_parameters({},environ={'RADAR_POSTGRES_CA_FILE':'relative.crt'})
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as root:
            self.assertTrue(Path(root).resolve().is_relative_to(TEMP_ROOT.resolve()))
            ca=Path(root)/'ca.crt';ca.write_text('public CA fixture')
            self.assertEqual(tls_parameters({},environ={'RADAR_POSTGRES_CA_FILE':str(ca)})['sslrootcert'],str(ca))

    def test_forwarded_address_only_trusted_on_vercel(self):
        with patch.dict(os.environ,{'VERCEL':'0'}):self.assertEqual(request_origin({'X-Forwarded-For':'1.2.3.4'},'127.0.0.1'),'127.0.0.1')
        with patch.dict(os.environ,{'VERCEL':'1'}):
            self.assertEqual(request_origin({'X-Forwarded-For':'1.2.3.4, 5.6.7.8'},'127.0.0.1'),'1.2.3.4')
            self.assertEqual(request_origin({'X-Forwarded-For':'2001:db8::123'}),'2001:db8::/64')

    def test_rate_limits_do_not_create_email_only_global_lock(self):
        db=MagicMock();db.execute.return_value.fetchone.return_value=(0,)
        throttle(db,'member@example.com','192.0.2.1')
        first=next(c.args[1][0] for c in db.execute.call_args_list if 'insert into radar_auth_attempts' in c.args[0])
        db.reset_mock();throttle(db,'member@example.com','192.0.2.2')
        second=next(c.args[1][0] for c in db.execute.call_args_list if 'insert into radar_auth_attempts' in c.args[0])
        self.assertEqual(len(set(first)&set(second)),1) # global budget only

    def test_session_checks_remote_password_fingerprint_ban_and_generation(self):
        db=MagicMock();db.execute.return_value.fetchone.return_value=None
        self.assertIsNone(session_user(db,'__Host-radar_session='+'x'*43))
        sql=db.execute.call_args.args[0]
        for guard in ('s.auth_generation','a.disabled_at','u.banned_until','md5(u.encrypted_password)','auth.mfa_factors'):
            self.assertIn(guard,sql)

    def test_alphanumeric_identifier_and_bounded_checklist(self):
        data={'id':'ABCD5678000100-1-1/2026','offer':'Public','status':'Nova','reason':'','version':0,
              'owner':'Analista','checklist':[{'id':'documentos','label':'Conferir edital','done':False}]}
        self.assertEqual(validate_review(data),data['id'])
        with self.assertRaises(ValueError):validate_review({**data,'checklist':[data['checklist'][0]]*2})


class BackupIntegrityTests(unittest.TestCase):
    def test_offline_roundtrip_and_tamper_rejection(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as root:
            self.assertTrue(Path(root).resolve().is_relative_to(TEMP_ROOT.resolve()))
            source=Path(root)/'dump';archive=Path(root)/'backup';restored=Path(root)/'restored'
            source.write_bytes(b'PGDMP'+os.urandom(2_100_000));key=backup_key(base64.b64encode(b'k'*32).decode())
            encrypt_archive(source,archive,key);decrypt_archive(archive,restored,key)
            self.assertEqual(source.read_bytes(),restored.read_bytes());restored.unlink()
            changed=bytearray(archive.read_bytes());changed[100]^=1;archive.write_bytes(changed)
            with self.assertRaises(InvalidTag):decrypt_archive(archive,restored,key)
            self.assertFalse(restored.exists())


if __name__=='__main__':unittest.main()
