import os
import smtplib
import unittest
import uuid
from unittest.mock import MagicMock,patch
from radar.mail import send_reserved,verify_gmail,gmail_client,gmail_authenticate,MailUnavailable


class GmailTests(unittest.TestCase):
    def setUp(self):
        config={'RADAR_EMAIL_ENABLED':'1','RADAR_EMAIL_PROVIDER':'gmail','SMTP_USERNAME':'sender@gmail.com',
                'SMTP_APP_PASSWORD':'test-only-app-password','RADAR_TEAM_EMAILS':'member@example.com',
                'RADAR_EMAIL_DOMAIN':'gmail.com','RADAR_EMAIL_FROM':'Nexo Radar <sender@gmail.com>',
                'RADAR_EMAIL_REPLY_TO':'sender@gmail.com'}
        self.patch=patch.dict(os.environ,config,clear=True);self.patch.start();self.addCleanup(self.patch.stop)
        self.db=MagicMock();self.factory=MagicMock();self.smtp=self.factory.return_value.__enter__.return_value
        self.smtp.send_message.return_value={};self.identifier=str(uuid.uuid4())

    def send(self,recipient='member@example.com'):
        return send_reserved(self.db,self.identifier,recipient,'Nexo Radar','<p>Resumo</p>','Resumo',smtp_factory=self.factory)

    def test_encrypted_connection_exact_sender_and_single_recipient(self):
        result=self.send()
        self.assertEqual(self.factory.call_args.args,('smtp.gmail.com',465))
        self.assertTrue(self.factory.call_args.kwargs['context'].check_hostname)
        message=self.smtp.send_message.call_args.args[0]
        self.assertEqual(str(message['To']),'member@example.com')
        self.assertEqual(str(message['From']),'Nexo Radar <sender@gmail.com>')
        self.assertEqual(result,str(message['Message-ID']))
        self.assertIn("status='sent'",self.db.execute.call_args.args[0])

    def test_sender_cannot_impersonate_a_different_gmail(self):
        with patch.dict(os.environ,{'RADAR_EMAIL_FROM':'Someone <other@gmail.com>'}):
            with self.assertRaises(MailUnavailable):self.send()
        self.factory.assert_not_called()

    def test_unapproved_recipient_is_not_sent(self):
        with self.assertRaises(MailUnavailable):self.send('other@example.com')
        self.factory.assert_not_called()

    def test_ambiguous_delivery_is_not_retried(self):
        self.smtp.send_message.side_effect=smtplib.SMTPServerDisconnected('connection lost')
        with self.assertRaises(MailUnavailable):self.send()
        self.assertEqual(self.smtp.send_message.call_count,1)
        self.assertIn("status='unknown'",self.db.execute.call_args.args[0])

    def test_transport_check_authenticates_without_sending(self):
        self.assertTrue(verify_gmail(factory=self.factory)['smtpAuthenticated'])
        self.smtp.send_message.assert_not_called()

    def test_submission_port_requires_tls_before_use(self):
        with patch.dict(os.environ,{'RADAR_SMTP_PORT':'587'}):
            gmail_client(factory=self.factory)
        client=self.factory.return_value
        self.assertEqual(self.factory.call_args.args,('smtp.gmail.com',587))
        self.assertTrue(client.starttls.call_args.kwargs['context'].check_hostname)
        self.assertEqual(client.ehlo.call_count,2)

    def test_advertised_login_challenge_avoids_initial_response(self):
        smtp=MagicMock();smtp.esmtp_features={'auth':'LOGIN PLAIN'}
        gmail_authenticate(smtp,'sender@gmail.com','test-only')
        smtp.auth.assert_called_once_with('LOGIN',smtp.auth_login,initial_response_ok=False)
        smtp.login.assert_not_called()
