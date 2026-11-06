"""Bounded PNCP batches, with each page committed alongside its durable cursor."""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timedelta, timezone

from radar.pncp import CollectionMetrics, PAGE_SIZE, PUBLICATION_MODALITIES, PNCPClient, PNCPError, page_count
from radar.relevance import TZ

KINDS = ('incremental', 'backfill', 'open')


def initial_cursor(kind, today, last_completed=None):
    if kind not in KINDS:
        raise ValueError('Invalid collection kind')
    start = today - timedelta(days=29)
    if kind == 'incremental' and last_completed:
        start = max(start, min(today - timedelta(days=1), last_completed - timedelta(days=1)))
    return {'kind': kind, 'start': start.isoformat(), 'end': today.isoformat(),
            'horizon': (today + timedelta(days=365)).isoformat(),
            'partition': 0, 'page': 1, 'fingerprints': [], 'status': 'running',
            'pages': 0, 'received': 0, 'request_count': 0, 'request_errors': 0,
            'latency_total_ms': 0, 'latency_max_ms': 0, 'http_statuses': {}}


def partitions(kind):
    modes = ('proposta',) if kind == 'open' else ('publicacao', 'atualizacao')
    return [(mode, modality) for mode in modes for modality in PUBLICATION_MODALITIES]


def page_query(cursor):
    mode, modality = partitions(cursor['kind'])[cursor['partition']]
    params = {'codigoModalidadeContratacao': modality, 'pagina': cursor['page'], 'tamanhoPagina': PAGE_SIZE}
    if mode == 'proposta':
        params['dataFinal'] = cursor['horizon'].replace('-', '')
    else:
        params.update(dataInicial=cursor['start'].replace('-', ''), dataFinal=cursor['end'].replace('-', ''))
    return mode, modality, params


def advance(cursor, records, payload):
    """Validate before any record is written; leave the input cursor untouched."""
    if any(not isinstance(row, dict) or not row.get('numeroControlePNCP') for row in records):
        raise ValueError('invalid_procurement_record')
    total = page_count(payload, len(records), PAGE_SIZE)
    if not records and total and cursor['page'] < total:
        raise ValueError('empty_intermediate_page')
    digest = hashlib.sha256(json.dumps(records, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    if records and digest in cursor['fingerprints']:
        raise ValueError('repeated_page')
    next_cursor = {**cursor, 'pages': cursor['pages'] + 1, 'received': cursor['received'] + len(records),
                   'fingerprints': (cursor['fingerprints'] + [digest])[-64:]}
    done = not records or (total is not None and (not total or cursor['page'] >= total))
    if done:
        next_cursor.update(partition=cursor['partition'] + 1, page=1, fingerprints=[])
    else:
        if cursor['page'] >= 10000:
            raise ValueError('partition_page_limit')
        next_cursor['page'] += 1
    return next_cursor


def add_metrics(cursor, metrics):
    next_cursor = {**cursor, 'http_statuses': dict(cursor['http_statuses'])}
    for metric in metrics.requests:
        next_cursor['request_count'] += 1
        next_cursor['request_errors'] += int(bool(metric.error))
        next_cursor['latency_total_ms'] += metric.elapsed_ms
        next_cursor['latency_max_ms'] = max(next_cursor['latency_max_ms'], metric.elapsed_ms)
        key = str(metric.status) if metric.status is not None else 'transport'
        next_cursor['http_statuses'][key] = next_cursor['http_statuses'].get(key, 0) + 1
    return next_cursor


def public_progress(cursor, execution_id):
    remaining=max(0,int((datetime.fromisoformat(cursor['next_attempt_at'])-datetime.now(timezone.utc)).total_seconds())) if cursor.get('next_attempt_at') else 0
    return {'executionId': execution_id, 'kind': cursor['kind'], 'done': cursor['status'] == 'ok',
            'status': cursor['status'], 'window': {'start': cursor['start'], 'end': cursor['end']},
            'completedPartitions': cursor['partition'], 'totalPartitions': len(partitions(cursor['kind'])),
            'pages': cursor['pages'], 'recordsReceived': cursor['received'],
            'requests': cursor['request_count'], 'requestErrors': cursor['request_errors'],
            'latencyMeanMs': round(cursor['latency_total_ms'] / cursor['request_count'], 2) if cursor['request_count'] else None,
            'latencyMaxMs': round(cursor['latency_max_ms'], 2),
            'httpStatuses': cursor['http_statuses'], 'error': cursor.get('error'),'retryAfterSeconds':remaining}


def run_chunk(store, kind='incremental', *, run_key, execution_id=None, client=None,
              max_pages=40, budget_seconds=140, clock=time.monotonic, today=None):
    if kind not in KINDS or not 1 <= max_pages <= 100 or not 1 <= budget_seconds <= 220:
        raise ValueError('Invalid batch configuration')
    if not store.acquire():
        return {'busy': True, 'done': False}
    try:
        started = clock()
        execution_id, cursor = store.start_or_resume(kind, run_key, execution_id,
                                                   today or datetime.now(TZ).date())
        if cursor['status'] == 'ok':
            return public_progress(cursor, execution_id)
        if public_progress(cursor,execution_id)['retryAfterSeconds']>0:
            return public_progress(cursor,execution_id)
        client = client or PNCPClient(timeout_seconds=45, retries=0, pause_seconds=1.5)
        for _ in range(max_pages):
            if clock() - started >= budget_seconds:
                break
            if cursor['partition'] >= len(partitions(kind)):
                break
            mode, modality, params = page_query(cursor)
            metrics = CollectionMetrics()
            try:
                payload = client.get_page('/v1/contratacoes/' + mode, params,
                                          modality=modality, page=cursor['page'], metrics=metrics)
                records = payload['data']
                next_cursor = add_metrics(advance(cursor, records, payload), metrics)
                next_cursor.pop('error', None)
                next_cursor.pop('next_attempt_at',None)
                next_cursor['consecutive_errors']=0
                next_cursor['status'] = 'running'
                store.commit_page(execution_id, kind, records, next_cursor)
                cursor = next_cursor
            except (PNCPError, ValueError) as exc:
                # These exception classes carry fixed transport/contract labels, never DSNs.
                label = str(exc) if isinstance(exc, PNCPError) else 'storage_guard' if str(exc)=='storage_guard' else 'invalid_page'
                cursor = {**add_metrics(cursor, metrics), 'status': 'partial', 'error': label[:80]}
                cursor['consecutive_errors']=cursor.get('consecutive_errors',0)+1
                base=max(60,getattr(exc,'retry_after_seconds',None) or 90) if label=='http_429' else 60 if label=='resposta_html_waf' else 15
                delay=max(base,min(base*2**min(cursor['consecutive_errors']-1,6),1800))
                if label=='storage_guard':delay=21600
                cursor['next_attempt_at']=(datetime.now(timezone.utc)+timedelta(seconds=delay)).isoformat()
                store.save_failure(execution_id, kind, cursor)
                return public_progress(cursor, execution_id)
        if cursor['partition'] >= len(partitions(kind)):
            cursor = {**cursor, 'status': 'ok'}
            store.complete(execution_id, kind, cursor)
        return public_progress(cursor, execution_id)
    finally:
        store.release()
