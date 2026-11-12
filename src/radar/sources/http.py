"""Bounded HTTPS reads for fixed official APIs; never follows redirects."""
from __future__ import annotations

import json
import random
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

HOSTS = frozenset({'pncp.gov.br', 'dadosabertos.compras.gov.br', 'api.queridodiario.ok.org.br'})


class SourceError(RuntimeError):
    def __init__(self, code, *, retry_after=0):
        super().__init__(code)
        self.code = code
        self.retry_after = retry_after


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise SourceError('redirect_blocked')


def validate_url(url):
    parsed = urlparse(url)
    if (parsed.scheme != 'https' or parsed.hostname not in HOSTS or parsed.username or
            parsed.password or parsed.port not in (None, 443) or parsed.fragment or
            '\\' in url or any(ord(c) < 32 for c in url)):
        raise SourceError('destination_blocked')
    return url


def retry_delay(headers, now=None):
    value = headers.get('Retry-After', '')
    try:
        delay = float(value)
    except (ValueError, TypeError):
        try:
            delay = (parsedate_to_datetime(value) - (now or datetime.now(timezone.utc))).total_seconds()
        except (ValueError, TypeError, OverflowError):
            delay = 2
    return min(3600, max(1, delay))


class PublicHTTP:
    def __init__(self, *, opener=None, sleeper=time.sleep, pause=0.7, clock=time.monotonic, recorder=None):
        self.opener = opener or build_opener(NoRedirect())
        self.sleeper, self.pause, self.clock = sleeper, pause, clock
        self.last_request = None
        self.recorder = recorder

    def read(self, url, *, max_bytes=2_000_000, timeout=10, attempts=2):
        validate_url(url)
        for attempt in range(attempts):
            if self.last_request is not None:
                self.sleeper(max(0, self.pause - (self.clock() - self.last_request)))
            self.last_request = self.clock()
            request = Request(url, headers={'User-Agent': 'NexoRadar/1.0 (public procurement; bounded reads)',
                                           'Accept': 'application/json, application/pdf;q=0.9',
                                           'Accept-Encoding': 'identity'})
            try:
                with self.opener.open(request, timeout=timeout) as response:
                    final_url = response.geturl() if hasattr(response, 'geturl') else url
                    if final_url != url:
                        raise SourceError('redirect_blocked')
                    declared = response.headers.get('Content-Length', '')
                    body = response.read(max_bytes + 1)
                    if len(body) > max_bytes or declared.isdigit() and int(declared) > max_bytes:
                        if self.recorder:
                            self.recorder(url,body[:max_bytes],status=200,truncated=True)
                        raise SourceError('response_too_large')
                    if self.recorder:
                        self.recorder(url, body)
                    return body
            except HTTPError as exc:
                if self.recorder:
                    body=exc.read(max_bytes+1)
                    self.recorder(url,body[:max_bytes],status=exc.code,truncated=len(body)>max_bytes)
                if exc.code == 429:
                    raise SourceError('rate_limited', retry_after=retry_delay(exc.headers)) from None
                if exc.code not in (500, 502, 503, 504) or attempt + 1 == attempts:
                    raise SourceError('http_' + str(exc.code)) from None
            except (URLError, TimeoutError, OSError):
                if attempt + 1 == attempts:
                    raise SourceError('transport_unavailable') from None
            self.sleeper(min(2, 0.5 * 2 ** attempt) + random.uniform(0, 0.25))
        raise SourceError('transport_unavailable')

    def json(self, url, **kwargs):
        try:
            return json.loads(self.read(url, **kwargs))
        except (ValueError, UnicodeError):
            raise SourceError('invalid_json') from None
