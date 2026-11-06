"""Authenticate to Gmail without sending any message or printing credentials."""
import json
import smtplib
import ssl
import sys

try:
    values=json.load(sys.stdin)
    if values.get('username')!='nexoplataform@gmail.com':raise ValueError()
    with smtplib.SMTP_SSL('smtp.gmail.com',465,timeout=20,context=ssl.create_default_context()) as smtp:
        smtp.login(values['username'],values['password'].replace(' ',''))
    print(json.dumps({'gmailAuthentication':True,'emailSent':False}))
except Exception as exc:
    print(json.dumps({'gmailAuthentication':False,'errorType':type(exc).__name__,'emailSent':False}))
    raise SystemExit(1)
