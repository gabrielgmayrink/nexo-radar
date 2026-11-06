"""Time-limited HMAC capabilities for feedback. No writes are performed on GET."""
from __future__ import annotations
import base64
import hashlib
import hmac
import json
import re
import time
import uuid

LABELS = {'relevante','irrelevante','vai_participar','ganhou','perdeu'}
PRODUCTS = {'daltton','gerico'}
MAX_TTL = 30 * 24 * 60 * 60


class InvalidFeedbackToken(ValueError):
    pass


def encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b'=').decode('ascii')


def decode(value: str) -> bytes:
    return base64.b64decode(value + '=' * (-len(value) % 4), altchars=b'-_', validate=True)


def validate_claims(data: dict, now: int) -> None:
    if not isinstance(data,dict) or not re.fullmatch(r'\d{14}-1-\d{1,10}/\d{4}',str(data.get('opportunity_id',''))):
        raise InvalidFeedbackToken('Identificador inválido')
    if data.get('product_id') not in PRODUCTS or data.get('label') not in LABELS:
        raise InvalidFeedbackToken('Produto ou ação inválida')
    issued, expires = data.get('iat'), data.get('exp')
    if type(issued) is not int or type(expires) is not int or not 0 < expires-issued <= MAX_TTL or expires <= now or issued > now+60:
        raise InvalidFeedbackToken('Link expirado ou prazo inválido')
    try:
        uuid.UUID(data['event_id'])
    except (KeyError,ValueError,TypeError,AttributeError) as exc:
        raise InvalidFeedbackToken('Evento inválido') from exc


def sign_feedback(opportunity_id: str, product_id: str, label: str, secret: str, *, ttl=MAX_TTL, now=None) -> str:
    if len(secret.encode()) < 32:
        raise ValueError('Configure FEEDBACK_SIGNING_SECRET com pelo menos 32 bytes')
    now = int(time.time()) if now is None else now
    claims = {'opportunity_id':opportunity_id,'product_id':product_id,'label':label,'iat':now,'exp':now+ttl,'event_id':str(uuid.uuid4())}
    validate_claims(claims,now)
    payload=encode(json.dumps(claims,sort_keys=True,separators=(',',':')).encode())
    return payload+'.'+encode(hmac.new(secret.encode(),payload.encode(),hashlib.sha256).digest())


def verify_feedback(token: str, secret: str, *, now=None) -> dict:
    if len(secret.encode()) < 32:
        raise ValueError('Assinatura não configurada')
    try:
        if not isinstance(token,str) or len(token)>4096:
            raise ValueError('Token inválido')
        payload,signature=token.split('.')
        expected=hmac.new(secret.encode(),payload.encode('ascii'),hashlib.sha256).digest()
        if not hmac.compare_digest(expected,decode(signature)):
            raise InvalidFeedbackToken('Assinatura inválida')
        claims=json.loads(decode(payload))
        validate_claims(claims,int(time.time()) if now is None else now)
        return claims
    except (ValueError,TypeError,UnicodeError,KeyError) as exc:
        raise InvalidFeedbackToken('Link inválido ou expirado') from exc
