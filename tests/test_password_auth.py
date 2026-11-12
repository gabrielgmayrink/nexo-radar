import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock,Mock,patch
from urllib.error import HTTPError
from radar.password_auth import password_login,setup_password,AuthenticationFailed,TooManyAttempts
from radar.team_auth import digest

USER={'id':'c39141b5-826d-41cc-95a5-35f16c57e657','email':'member@example.com','email_confirmed_at':'2026-11-06T10:00:00Z'}


class PasswordAuthTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'RADAR_TEAM_EMAILS':'member@example.com'});self.env.start();self.addCleanup(self.env.stop)
        self.db=MagicMock();self.attempts=0;self.invite=('member@example.com',);self.generation=0
        def execute(sql,*args):
            if 'select generation,require_mfa' in sql:return SimpleNamespace(fetchone=lambda:(self.generation,False,None))
            if 'insert into radar_account_security' in sql:
                self.generation+=1
                return SimpleNamespace(fetchone=lambda:(self.generation,))
            if 'select count(*)' in sql:return SimpleNamespace(fetchone=lambda:(self.attempts,))
            if 'select email from radar_account_invites' in sql:return SimpleNamespace(fetchone=lambda:self.invite)
            if 'select id from auth.users' in sql:return SimpleNamespace(fetchone=lambda:None)
            return MagicMock()
        self.db.execute.side_effect=execute
        self.provider=Mock(return_value={'user':USER})

    def test_password_is_verified_by_provider_and_only_session_hash_is_stored(self):
        email,token=password_login(self.db,'MEMBER@example.com','test-password',provider=self.provider)
        self.assertEqual(email,'member@example.com')
        self.provider.assert_called_once_with('token?grant_type=password',{'email':'member@example.com','password':'test-password'})
        insert=next(call for call in self.db.execute.call_args_list if 'insert into radar_team_sessions' in call.args[0])
        self.assertEqual(insert.args[1][0],digest(token))
        self.assertNotIn('test-password',str(self.db.execute.call_args_list))

    def test_unknown_members_and_excessive_attempts_never_call_provider(self):
        with self.assertRaises(AuthenticationFailed):password_login(self.db,'other@example.com','test-password',provider=self.provider)
        self.attempts=8
        with self.assertRaises(TooManyAttempts):password_login(self.db,'member@example.com','test-password',provider=self.provider)
        self.provider.assert_not_called()

    def test_bad_credentials_and_forged_provider_identity_are_rejected(self):
        self.provider.side_effect=HTTPError('https://unit-test.invalid',400,'bad credentials',{},None)
        with self.assertRaises(AuthenticationFailed):password_login(self.db,'member@example.com','bad-password',provider=self.provider)
        self.provider.side_effect=None;self.provider.return_value={'user':{**USER,'email':'other@example.com'}}
        with self.assertRaises(AuthenticationFailed):password_login(self.db,'member@example.com','test-password',provider=self.provider)

    def test_setup_uses_server_invite_identity_and_consumes_it(self):
        email,_=setup_password(self.db,'a'*43,'a-test-password-123',provider=self.provider)
        self.assertEqual(email,'member@example.com')
        self.provider.assert_called_once_with('admin/users',{'email':'member@example.com','password':'a-test-password-123','email_confirm':True})
        for table in ('radar_account_invites','radar_login_requests','radar_mfa_pending'):
            self.assertTrue(any('update '+table in call.args[0] and 'consumed_at' in call.args[0] for call in self.db.execute.call_args_list))
        self.assertEqual(self.generation,1)

    def test_expired_invite_and_weak_password_cannot_create_an_account(self):
        with self.assertRaises(AuthenticationFailed):setup_password(self.db,'a'*43,'short',provider=self.provider)
        self.invite=None
        with self.assertRaises(AuthenticationFailed):setup_password(self.db,'a'*43,'a-test-password-123',provider=self.provider)
        self.provider.assert_not_called()
