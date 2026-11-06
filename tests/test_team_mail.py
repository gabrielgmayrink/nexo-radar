from radar.mail import APP_URL
import io
import json
import os
import unittest
from datetime import datetime,timedelta,timezone
from types import SimpleNamespace
from unittest.mock import patch,MagicMock
from urllib.error import URLError
from radar.mail import email_list,send_reserved,MailUnavailable
from radar.team_auth import confirm_login,session_cookie,session_user
from radar.team_reviews import validate_review
from radar.notifications import select_cards,render_digest,render_onboarding


class TeamMailTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'RADAR_EMAIL_ENABLED':'1','RESEND_API_KEY':'unit-test-only',
            'RADAR_TEAM_EMAILS':'member@example.com','RADAR_EMAIL_FROM':'Radar <radar@mail.example.com>',
            'RADAR_EMAIL_REPLY_TO':'contact@example.com','RADAR_EMAIL_DOMAIN':'mail.example.com'})
        self.env.start();self.addCleanup(self.env.stop)

    def test_private_recipient_allowlist_and_header_injection(self):
        db=MagicMock()
        with self.assertRaises(MailUnavailable):
            send_reserved(db,'test','stranger@example.com','Title','<p>Hi</p>','Hi')
        with patch.dict(os.environ,{'RADAR_TEAM_EMAILS':'member@example.com\r\nBcc: other@example.com'}):
            with self.assertRaises(ValueError):email_list('RADAR_TEAM_EMAILS')
        with self.assertRaises(ValueError):
            send_reserved(db,'test','member@example.com','Title\r\nBcc: other@example.com','','')

    def test_send_is_idempotent_and_uses_only_fixed_provider(self):
        db=MagicMock();opener=MagicMock()
        response=io.BytesIO(json.dumps({'id':'provider-1'}).encode())
        opener.open.return_value.__enter__.return_value=response
        result=send_reserved(db,'reservation-1','member@example.com','Title','<p>Hi</p>','Hi',opener=opener)
        self.assertEqual(result,'provider-1')
        request=opener.open.call_args.args[0]
        self.assertEqual(request.full_url,'https://api.resend.com/emails')
        self.assertEqual(request.get_header('Idempotency-key'),'radar/reservation-1')
        self.assertTrue(request.get_header('User-agent').startswith('RadarLicitacoes/'))
        self.assertEqual(json.loads(request.data)['to'],['member@example.com'])
        self.assertIn("status='sent'",db.execute.call_args.args[0])

    def test_ambiguous_delivery_is_recorded_without_retry(self):
        db=MagicMock();opener=MagicMock();opener.open.side_effect=URLError('timeout')
        with self.assertRaises(MailUnavailable):
            send_reserved(db,'id','member@example.com','Title','','',opener=opener)
        self.assertEqual(opener.open.call_count,1)
        self.assertIn("status='unknown'",db.execute.call_args.args[0])

    def test_login_rejects_different_unconfirmed_or_missing_identity(self):
        for user in ({'email':'other@example.com','id':'id','email_confirmed_at':'now'},
                     {'email':'member@example.com','id':'id'},{}):
            db=MagicMock();db.execute.return_value.fetchone.return_value=('member@example.com','email')
            with self.assertRaises(ValueError):confirm_login(db,'x'*64,provider=lambda *args:{'user':user})
            self.assertEqual(db.execute.call_count,1)

    def test_session_cookie_flags_and_invalid_cookie_never_queries_database(self):
        cookie=session_cookie('x'*43)
        for flag in ('__Host-','HttpOnly','Secure','SameSite=Strict','Path=/'):self.assertIn(flag,cookie)
        self.assertIn('Max-Age=0',session_cookie('',clear=True))
        db=MagicMock();self.assertIsNone(session_user(db,'__Host-radar_session=invalid'))
        db.execute.assert_not_called()

    def test_review_validation_rejects_forged_and_oversized_input(self):
        data={'id':'12345678000100-1-000001/2026','offer':'Daltton','status':'Nova','reason':'Reason','version':0}
        self.assertEqual(validate_review(data),data['id'])
        for field,value in [('id','bad'),('offer','All'),('status','Admin'),('reason','x'*2001),('version',True),('version',-1)]:
            with self.assertRaises(ValueError):validate_review({**data,field:value})

    def test_notifications_exclude_inactive_expired_unrelated_and_unsafe_links(self):
        now=datetime(2026,11,5,tzinfo=timezone.utc)
        card={'statusId':1,'instrumentId':1,'proposalDeadline':(now+timedelta(hours=24)).isoformat(),
              'pncpUrl':'https://pncp.gov.br/app/editais/12345678000100/2026/1',
              'suggestedOffer':'Daltton','score':70,'object':'<script>alert(1)</script>','organization':'A&B'}
        good=(card,None,None)
        rows=[good,({**card,'statusId':2},None,None),({**card,'proposalDeadline':now.isoformat()},None,None),
              (card,'Nenhuma',None),(card,None,'Descartada'),({**card,'pncpUrl':'https://evil.example'},None,None)]
        selected=select_cards(rows,'urgent',now)
        self.assertEqual(len(selected),1)
        subject,body,text=render_digest(selected,'urgent',now)
        self.assertNotIn('<script>',body);self.assertIn('&lt;script&gt;',body)
        self.assertIn('IA desligada',body);self.assertIn('A&amp;B',body)
        self.assertIn('PNCP',text)

    def test_onboarding_explains_navigation_and_useful_feedback(self):
        subject,body,text=render_onboarding()
        for phrase in ('Mais compatíveis','Precisam de análise','Com prazo futuro','Entrar na equipe','Não tem relação',
                       'Publicar avaliação e ensinar o Radar','Aprendizado da equipe','rascunho','apenas parecidos','edital'):
            self.assertIn(phrase,text)
        self.assertIn(APP_URL,body)
        self.assertNotIn('API_KEY',body)
