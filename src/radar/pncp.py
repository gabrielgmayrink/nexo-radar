"""Cliente pequeno e conservador para a API pública de Consulta do PNCP."""

from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


BASE_URL = "https://pncp.gov.br/api/consulta"
PUBLICATION_MODALITIES = (6, 7, 8, 4, 5, 12, 2, 10, 11, 15)
PAGE_SIZE = 50
USER_AGENT = "Mozilla/5.0 (compatible; RadarLicitacoes/0.1; public-data-research)"


class PNCPError(RuntimeError):
    """Erro de transporte, HTTP ou contrato na API do PNCP."""
    def __init__(self, message, *, retry_after_seconds=None):
        super().__init__(message)
        self.retry_after_seconds=retry_after_seconds


@dataclass
class RequestMetric:
    endpoint: str
    modality: int
    page: int
    status: int | None
    elapsed_ms: float
    records: int = 0
    error: str | None = None


@dataclass
class CollectionMetrics:
    requests: list[RequestMetric] = field(default_factory=list)
    retries: int = 0

    def summary(self) -> dict[str, Any]:
        durations = sorted(m.elapsed_ms for m in self.requests)
        errors: dict[str, int] = {}
        for metric in self.requests:
            if metric.error:
                errors[metric.error] = errors.get(metric.error, 0) + 1
        p95_index = max(0, int((len(durations) - 1) * 0.95))
        return {
            "requests": len(self.requests),
            "retries": self.retries,
            "errors": errors,
            "http_statuses": _count_statuses(self.requests),
            "records_received": sum(m.records for m in self.requests),
            "latency_ms": {
                "mean": round(sum(durations) / len(durations), 2) if durations else None,
                "p95": round(durations[p95_index], 2) if durations else None,
                "max": round(max(durations), 2) if durations else None,
            },
        }


def _count_statuses(metrics: list[RequestMetric]) -> dict[str, int]:
    result: dict[str, int] = {}
    for metric in metrics:
        key = str(metric.status) if metric.status is not None else "sem_status"
        result[key] = result.get(key, 0) + 1
    return result


class PNCPClient:
    def __init__(
        self,
        *,
        base_url: str = BASE_URL,
        pause_seconds: float = 0.5,
        timeout_seconds: float = 60,
        retries: int = 5,
        opener=urlopen,
        sleeper=time.sleep,
        jitter=random.uniform,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.pause_seconds = pause_seconds
        self.timeout_seconds = timeout_seconds
        self.max_retries = retries
        self._opener = opener
        self._sleep = sleeper
        self._jitter = jitter
        self._last_request_at: float | None = None

    def get_page(
        self,
        endpoint: str,
        params: dict[str, Any],
        *,
        modality: int,
        page: int,
        metrics: CollectionMetrics,
    ) -> dict[str, Any]:
        query = urlencode(params)
        url = f"{self.base_url}{endpoint}?{query}"
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        for attempt in range(self.max_retries + 1):
            self._pace()
            started = time.perf_counter()
            status: int | None = None
            try:
                request = Request(url, headers=headers)
                with self._opener(request, timeout=self.timeout_seconds) as response:
                    status = response.status
                    body = response.read()
                elapsed = (time.perf_counter() - started) * 1000
                if status == 204:
                    metrics.requests.append(RequestMetric(endpoint, modality, page, status, elapsed, 0))
                    return {"data": []}
                if "html" in _response_content_type(response).lower() or body.lstrip().lower().startswith((b"<!doctype html", b"<html")):
                    raise PNCPError("resposta_html_waf")
                try:
                    payload = json.loads(body.decode("utf-8-sig"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise PNCPError("resposta_nao_json") from exc
                if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
                    raise PNCPError("contrato_resposta_sem_lista_data")
                metrics.requests.append(RequestMetric(endpoint, modality, page, status, elapsed, len(payload["data"])))
                return payload
            except HTTPError as exc:
                elapsed = (time.perf_counter() - started) * 1000
                status = exc.code
                retryable = status == 429 or 500 <= status <= 599
                label = f"http_{status}"
                metrics.requests.append(RequestMetric(endpoint, modality, page, status, elapsed, error=label))
                retry_after = exc.headers.get("Retry-After") if exc.headers else None
                if retryable and attempt < self.max_retries:
                    metrics.retries += 1
                    self._sleep(_retry_delay(attempt, retry_after, self._jitter))
                    continue
                raise PNCPError(label,retry_after_seconds=_retry_delay(attempt,retry_after,self._jitter) if status==429 else None) from exc
            except (URLError, TimeoutError, OSError) as exc:
                elapsed = (time.perf_counter() - started) * 1000
                label = "timeout" if isinstance(exc, TimeoutError) else "erro_transporte"
                metrics.requests.append(RequestMetric(endpoint, modality, page, None, elapsed, error=label))
                if attempt < self.max_retries:
                    metrics.retries += 1
                    self._sleep(min(1.5 * (2**attempt) + self._jitter(0, 0.5), 60))
                    continue
                raise PNCPError(label) from exc
            except PNCPError as exc:
                elapsed = (time.perf_counter() - started) * 1000
                metrics.requests.append(RequestMetric(endpoint, modality, page, status, elapsed, error=str(exc)))
                if str(exc) == "resposta_html_waf" and attempt < self.max_retries:
                    metrics.retries += 1
                    self._sleep(60)
                    continue
                raise
        raise AssertionError("loop de retentativa terminou inesperadamente")

    def _pace(self) -> None:
        if self._last_request_at is not None:
            remaining = self.pause_seconds - (time.monotonic() - self._last_request_at)
            if remaining > 0:
                self._sleep(remaining)
        self._last_request_at = time.monotonic()


def _response_content_type(response: Any) -> str:
    return response.headers.get("Content-Type", "")


def _retry_delay(attempt: int, retry_after: str | None, jitter=random.uniform) -> float:
    if retry_after:
        try:
            return max(0.0, float(retry_after))
        except ValueError:
            try:
                target = parsedate_to_datetime(retry_after)
                now = datetime.now(target.tzinfo or timezone.utc)
                return max(0.0, (target - now).total_seconds())
            except (TypeError, ValueError, OverflowError):
                pass
    return min(1.5 * (2**attempt) + jitter(0, 0.5), 60)


def page_count(payload: dict[str, Any], records_on_page: int, page_size: int) -> int | None:
    """Obtém contagem quando presente; None usa a regra segura de página curta."""
    for key in ("totalPaginas", "totalPages"):
        value = payload.get(key)
        if isinstance(value, int) and value >= 0:
            return value
    remaining = payload.get("paginasRestantes")
    if isinstance(remaining, int) and remaining >= 0:
        return int(payload.get("numeroPagina", 1)) + remaining
    if records_on_page < page_size:
        return 0
    return None


def date_range(days: int, end: date) -> tuple[date, date]:
    if days < 1:
        raise ValueError("days deve ser maior que zero")
    from datetime import timedelta

    return end - timedelta(days=days - 1), end
