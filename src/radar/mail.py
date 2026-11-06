"""Restricted recipients, durable deduplication and an application-level free-tier cap."""
import json
import os
import re
import uuid
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import parseaddr
from urllib.error import HTTPError,URLError
from urllib.request import Request,build_opener,HTTPRedirectHandler

from radar.settings import app_url
APP_URL=app_url()
EMAIL_PATTERN=re.compile(r'^[A-Za-z0-9.!#$%&\x27*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')
MAIL_LOCK=739241664


class MailUnavailable(RuntimeError):pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        raise MailUnavailable('Unexpected mail provider redirect')


def email_list(name):
    raw=os.environ.get(name,'')
    values=[v.strip().lower() for v in raw.split(',') if v.strip()]
    if len(values)>10 or any(not EMAIL_PATTERN.fullmatch(v) or '\r' in v or '\n' in v for v in values):
        raise ValueError('Invalid recipient configuration')
    return set(values)


def enabled():
    configured=bool(os.environ.get('SMTP_USERNAME') and os.environ.get('SMTP_APP_PASSWORD')) if os.environ.get('RADAR_EMAIL_PROVIDER')=='gmail' else bool(os.environ.get('RESEND_API_KEY'))
    return os.environ.get('RADAR_EMAIL_ENABLED')=='1' and configured


def reserve(db,recipient,kind,dedupe_key):
    if not enabled():raise MailUnavailable('Email is not enabled')
    if recipient not in email_list('RADAR_TEAM_EMAILS') or kind not in ('login','weekly','urgent','test'):
        raise ValueError('Recipient or message not authorized')
    with db.transaction():
        db.execute('select pg_advisory_xact_lock(%s)',(MAIL_LOCK,))
        if db.execute('select 1 from radar_mail_outbox where dedupe_key=%s',(dedupe_key,)).fetchone():return None
        daily,monthly=db.execute('''select count(*) filter(where created_at>=now()-interval '24 hours'),
            count(*) filter(where created_at>=date_trunc('month',now())) from radar_mail_outbox''').fetchone()
        if daily>=20 or monthly>=600:raise MailUnavailable('Application email quota reached')
        if kind=='login':
            minute,day=db.execute('''select count(*) filter(where created_at>=now()-interval '60 seconds'),count(*)
                from radar_mail_outbox where recipient=%s and kind='login' and created_at>=now()-interval '24 hours' ''',(recipient,)).fetchone()
            if minute or day>=5:return None
        identifier=str(uuid.uuid4())
        db.execute('insert into radar_mail_outbox(id,dedupe_key,recipient,kind) values(%s,%s,%s,%s)',
                   (identifier,dedupe_key,recipient,kind))
        return identifier


def send_reserved(db,identifier,recipient,subject,html,text,*,opener=None,smtp_factory=None):
    if not enabled() or recipient not in email_list('RADAR_TEAM_EMAILS'):
        raise MailUnavailable('Email is not configured')
    sender=os.environ.get('RADAR_EMAIL_FROM','')
    reply=os.environ.get('RADAR_EMAIL_REPLY_TO','')
    address=parseaddr(sender)[1]
    domain=os.environ.get('RADAR_EMAIL_DOMAIN','').lower()
    if not domain or not EMAIL_PATTERN.fullmatch(address) or address.split('@')[-1].lower()!=domain or '\r' in sender or '\n' in sender:
        raise MailUnavailable('Sender domain is not configured')
    if not EMAIL_PATTERN.fullmatch(reply) or '\r' in subject or '\n' in subject:
        raise ValueError('Invalid email headers')
    if os.environ.get('RADAR_EMAIL_PROVIDER')=='gmail':
        return send_gmail(db,identifier,recipient,subject,html,text,sender,reply,address,factory=smtp_factory)
    payload={'from':sender,'to':[recipient],'reply_to':[reply],'subject':subject,'html':html,'text':text}
    request=Request('https://api.resend.com/emails',data=json.dumps(payload).encode(),method='POST',
                    headers={'Authorization':'Bearer '+os.environ['RESEND_API_KEY'],'Content-Type':'application/json',
                             'User-Agent':'RadarLicitacoes/1.0 (+'+APP_URL+')',
                             'Idempotency-Key':'radar/'+identifier})
    opener=opener or build_opener(NoRedirect())
    try:
        with opener.open(request,timeout=15) as response:
            result=json.loads(response.read(65536))
        if not result.get('id'):raise MailUnavailable('Mail response is incomplete')
        db.execute("update radar_mail_outbox set status='sent',provider_id=%s,sent_at=now() where id=%s",
                   (result['id'],identifier))
        return result['id']
    except HTTPError as exc:
        raw=exc.read(8192).decode('utf-8','replace')
        try:name=json.loads(raw).get('name','unknown')
        except ValueError:name='firewall_1010' if '1010' in raw else 'non_json_error'
        allowed={'validation_error','missing_api_key','restricted_api_key','suspended_api_key','invalid_permission',
                 'rate_limit_exceeded','monthly_quota_exceeded','daily_quota_exceeded','firewall_1010','non_json_error'}
        print(json.dumps({'event':'mail_provider_rejected','httpStatus':exc.code,'category':name if name in allowed else 'unknown'}))
        db.execute("update radar_mail_outbox set status='failed',error_code=%s where id=%s",(exc.code,identifier))
        raise MailUnavailable('Email provider refused request') from None
    except (URLError,TimeoutError,OSError,ValueError,MailUnavailable):
        # An ambiguous response is never retried automatically: the provider may have delivered it.
        db.execute("update radar_mail_outbox set status='unknown' where id=%s",(identifier,))
        raise MailUnavailable('Email delivery could not be confirmed') from None


def send_gmail(db,identifier,recipient,subject,html,text,sender,reply,address,*,factory=None):
    username=os.environ.get('SMTP_USERNAME','').strip().lower()
    if address.lower()!=username or not username.endswith('@gmail.com') or not EMAIL_PATTERN.fullmatch(username):
        raise MailUnavailable('Unexpected Gmail sender')
    message=EmailMessage()
    message['From']=sender;message['To']=recipient;message['Reply-To']=reply;message['Subject']=subject
    message['Message-ID']='<nexo.'+str(uuid.UUID(identifier))+'@gmail.com>'
    message.set_content(text);message.add_alternative(html,subtype='html')
    try:
        with (factory or smtplib.SMTP_SSL)('smtp.gmail.com',465,timeout=20,context=ssl.create_default_context()) as smtp:
            smtp.login(username,os.environ['SMTP_APP_PASSWORD'].replace(' ',''))
            refused=smtp.send_message(message)
            if refused:raise MailUnavailable('Gmail refused recipient')
        provider_id=str(message['Message-ID'])
        db.execute("update radar_mail_outbox set status='sent',provider_id=%s,sent_at=now() where id=%s",(provider_id,identifier))
        return provider_id
    except smtplib.SMTPAuthenticationError:
        db.execute("update radar_mail_outbox set status='failed',error_code=535 where id=%s",(identifier,))
        raise MailUnavailable('Gmail authentication failed') from None
    except (smtplib.SMTPException,OSError,ValueError,MailUnavailable):
        db.execute("update radar_mail_outbox set status='unknown' where id=%s",(identifier,))
        raise MailUnavailable('Gmail delivery could not be confirmed') from None
