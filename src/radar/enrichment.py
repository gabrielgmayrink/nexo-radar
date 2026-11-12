"""Resumable source/document enrichment. Public evidence; company decisions stay private."""
from __future__ import annotations

import gzip
import hashlib
import json
import time
import secrets
from datetime import datetime, timezone

from psycopg.types.json import Jsonb
from radar.company_access import COMPANIES, AccessDenied
from radar.identifiers import parse_pncp_id
from radar.pdf_extract import extract_pdf
from radar.sources import ComprasGovConnector, PNCPDetailsConnector
from radar.sources.http import PublicHTTP, SourceError
from radar.sources.pncp_details import document_url

TASK_SOURCE = {'pncp_items': 'pncp', 'pncp_documents': 'pncp', 'pdf': 'pncp',
               'compras_details': 'compras_gov', 'compras_items': 'compras_gov'}


def _hash(payload):
    return hashlib.sha256(payload).hexdigest()


def _enqueue(db):
    # Documents are expensive: first enrich candidates and records explicitly reviewed.
    # Raw national capture remains independent of this queue and of company filters.
    db.execute('''insert into radar_enrichment_jobs(opportunity_id,source_hash,task_type)
      select o.id,o.content_hash,t.task from radar_opportunities o
      cross join (values ('pncp_items'),('compras_details'),('compras_items'),('pncp_documents')) as t(task)
      where (o.score>=40 or exists(select 1 from radar_review_state r where r.opportunity_id=o.id))
      and not exists(select 1 from radar_enrichment_jobs j where j.opportunity_id=o.id
          and j.source_hash=o.content_hash and j.task_type=t.task and j.job_key='')
      order by o.catalog_seen_at desc nulls last,o.id,t.task limit 200 on conflict do nothing''')


def _claim(db):
    with db.transaction():
        row = db.execute('''select j.id,j.opportunity_id,j.source_hash,j.task_type,j.job_key,j.cursor,j.attempts
          from radar_enrichment_jobs j join radar_opportunities o on o.id=j.opportunity_id and o.content_hash=j.source_hash
          join radar_data_sources s on s.source_id=case when j.task_type in ('compras_details','compras_items') then 'compras_gov' else 'pncp' end
          where s.enabled and ((j.status in ('pending','retry') and j.next_attempt_at<=now()) or
             (j.status='processing' and j.lease_until<now()))
          order by j.next_attempt_at,j.id for update of j skip locked limit 1''').fetchone()
        if not row:
            return None
        token=secrets.token_hex(16)
        db.execute("update radar_enrichment_jobs set status='processing',lease_token=%s,attempts=attempts+1,lease_until=now()+interval '2 minutes',updated_at=now() where id=%s", (token,row[0]))
        return {**dict(zip(('id', 'opportunity', 'hash', 'task', 'key', 'cursor', 'attempts'), row)), 'leaseToken':token}


def _receipt(db, job, url, body, *, status=200, truncated=False):
    db.execute('''insert into radar_source_receipts(opportunity_id,source_id,source_hash,url,content_hash,payload_gzip)
      values(%s,%s,%s,%s,%s,%s) on conflict do nothing''',
               (job['opportunity'], TASK_SOURCE[job['task']], job['hash'], url, _hash(body), gzip.compress(body, mtime=0)))
    db.execute('''update radar_source_receipts set http_status=%s,truncated=%s where
      opportunity_id=%s and source_id=%s and source_hash=%s and url=%s and content_hash=%s''',
      (status,truncated,job['opportunity'],TASK_SOURCE[job['task']],job['hash'],url,_hash(body)))


def _link(db, job, rows, url, key, kind):
    content = json.dumps(rows, sort_keys=True, ensure_ascii=False).encode()
    db.execute('''insert into radar_source_links(opportunity_id,source_id,source_hash,external_id,link_type,url,content_hash,payload)
      values(%s,%s,%s,%s,%s,%s,%s,%s) on conflict do nothing''',
               (job['opportunity'], TASK_SOURCE[job['task']], job['hash'], key, kind, url, _hash(content), Jsonb(rows)))
    if kind=='item_page':
        items=[{'number':str(item['number']),'description':item['description']} for item in _items(TASK_SOURCE[job['task']],rows) if item['number'] is not None]
        if items:
            db.execute('''insert into radar_item_search(opportunity_id,source_hash,source_id,item_number,text_normalized)
              select %s,%s,%s,number,public.radar_search_normalize(description)
              from jsonb_to_recordset(%s::jsonb) as i(number text,description text)
              on conflict(opportunity_id,source_hash,source_id,item_number) do update set text_normalized=excluded.text_normalized''',
              (job['opportunity'],job['hash'],TASK_SOURCE[job['task']],Jsonb(items)))


def _manifest(db, job, rows):
    for row in rows:
        key = str(row.get('sequencialDocumento', ''))
        if not key.isdigit() or row.get('statusAtivo') is False:
            continue
        url = row.get('url') or row.get('uri') or ''
        title = str(row.get('titulo') or row.get('tipoDocumentoNome') or 'Documento do edital')[:500]
        try:
            document_url(job['opportunity'], url)
            state = 'pending'
        except SourceError:
            # Preserve the reference, but never fetch an unapproved origin automatically.
            state = 'external_link_only'
        db.execute('''insert into radar_documents(opportunity_id,source_hash,document_key,title,url,extraction_state)
          values(%s,%s,%s,%s,%s,%s) on conflict do nothing''',
                   (job['opportunity'], job['hash'], key, title, url[:2000], state))
        if state == 'pending':
            db.execute('''insert into radar_enrichment_jobs(opportunity_id,source_hash,task_type,job_key,cursor)
              values(%s,%s,'pdf',%s,%s) on conflict do nothing''',
                       (job['opportunity'], job['hash'], key, Jsonb({'url': url})))


def _execute(db, job, http):
    identifier, task = job['opportunity'], job['task']
    pncp, compras = PNCPDetailsConnector(http), ComprasGovConnector(http)
    if task in ('pncp_items', 'pncp_documents'):
        page = int(job['cursor'].get('page', 1))
        data = pncp.page(identifier, 'itens' if task == 'pncp_items' else 'arquivos', page)
        # Raw response is already committed by the HTTP recorder, before parsing/linking.
        with db.transaction():
            _link(db, job, data['rows'], data['url'], task + ':' + str(page),
                  'item_page' if task == 'pncp_items' else 'document_manifest')
            if task == 'pncp_documents':
                _manifest(db, job, data['rows'])
        return {'page': data['nextPage']} if data['nextPage'] else None
    if task in ('compras_details', 'compras_items'):
        rows, url = compras.details(identifier) if task == 'compras_details' else compras.items(identifier)
        _link(db, job, rows, url, identifier + ':' + task, 'official_id' if task == 'compras_details' else 'item_page')
        return None
    if task == 'pdf':
        url = job['cursor']['url']
        old = db.execute('''select payload_gzip from radar_documents
          where opportunity_id=%s and source_hash=%s and document_key=%s''', (identifier, job['hash'], job['key'])).fetchone()
        body = gzip.decompress(old[0]) if old and old[0] else pncp.download(identifier, url)
        # Original retained before attempting extraction; a failed parser does not lose the file.
        db.execute('''update radar_documents set content_hash=%s,payload_gzip=%s,extraction_state='captured'
          where opportunity_id=%s and source_hash=%s and document_key=%s''',
                   (_hash(body), gzip.compress(body, mtime=0), identifier, job['hash'], job['key']))
        result = extract_pdf(body)
        db.execute('''update radar_documents set pages=%s,extraction_state=%s,extracted_at=now()
          where opportunity_id=%s and source_hash=%s and document_key=%s''',
                   (Jsonb(result['pages']), result['state'], identifier, job['hash'], job['key']))
        return None
    raise SourceError('unknown_task')


def enrich_batch(store, limit=2, deadline_seconds=45):
    db, started = store.db, time.monotonic()
    if not 1 <= limit <= 20:
        raise ValueError('Invalid enrichment batch')
    # Free database capacity is a safety guard, not an excuse to drop pending work.
    if db.execute('select pg_database_size(current_database())').fetchone()[0] > 420 * 1024 * 1024:
        return {'done': False, 'processed': 0, 'remaining': None, 'state': 'storage_guard'}
    _enqueue(db)
    processed = 0
    while processed < limit and time.monotonic() - started < max(1, deadline_seconds - 22):
        if db.execute('select pg_database_size(current_database())').fetchone()[0] > 420 * 1024 * 1024:
            break
        job = _claim(db)
        if not job:
            break
        http = PublicHTTP(recorder=lambda url, body, **meta: _receipt(db, job, url, body, **meta))
        try:
            cursor = _execute(db, job, http)
            db.execute('''update radar_enrichment_jobs set status=%s,cursor=%s,attempts=0,
              lease_until=null,lease_token=null,last_error_code=null,next_attempt_at=now(),updated_at=now() where id=%s and lease_token=%s''',
                       ('pending' if cursor else 'done', Jsonb(cursor or {}), job['id'],job['leaseToken']))
            db.execute('''update radar_data_sources set last_success_at=now(),last_error_code=null,updated_at=now()
              where source_id=%s''', (TASK_SOURCE[job['task']],))
        except (SourceError, ValueError, TypeError, KeyError, OSError) as exc:
            code = exc.code if isinstance(exc, SourceError) else 'processing_failed'
            attempts = job['attempts'] + 1
            blocked = attempts >= 8 or code in ('destination_blocked', 'identity_mismatch', 'document_destination_blocked', 'response_too_large')
            delay = max(getattr(exc, 'retry_after', 0), min(3600, 30 * 2 ** min(attempts, 6)))
            db.execute('''update radar_enrichment_jobs set status=%s,last_error_code=%s,lease_until=null,
              next_attempt_at=now()+%s*interval '1 second',lease_token=null,updated_at=now() where id=%s and lease_token=%s''',
                       ('blocked' if blocked else 'retry', code, delay, job['id'],job['leaseToken']))
            if job['task'] == 'pdf':
                db.execute('''update radar_documents set extraction_state=%s
                  where opportunity_id=%s and source_hash=%s and document_key=%s''',
                           (code, job['opportunity'], job['hash'], job['key']))
            db.execute('update radar_data_sources set last_error_code=%s,updated_at=now() where source_id=%s',
                       (code, TASK_SOURCE[job['task']]))
        processed += 1
    row = db.execute("select count(*) filter(where status<>'done'),count(*) filter(where status='blocked') from radar_enrichment_jobs j join radar_opportunities o on o.id=j.opportunity_id and o.content_hash=j.source_hash").fetchone()
    return {'done': row[0] == 0, 'processed': processed, 'remaining': row[0], 'blocked': row[1]}


def _items(source, rows):
    for row in rows:
        description = row.get('descricao') if source == 'pncp' else row.get('descricaodetalhada') or row.get('descricaoResumida')
        if description:
            yield {'number': row.get('numeroItem') or row.get('numeroItemPncp'),
                   'description': str(description)[:6000], 'source': source}


def get_enrichment(db, identifier, company):
    """Call only after request_access; response contains no other company's decisions."""
    if company not in COMPANIES:
        raise AccessDenied()
    identifier = parse_pncp_id(identifier).canonical
    version = db.execute('select content_hash from radar_opportunities where id=%s', (identifier,)).fetchone()
    if not version:
        return {'analysisStatus': 'not_requested', 'items': [], 'documents': [], 'textExcerpts': [], 'sources': [], 'limitations': []}
    scope = (identifier, version[0])
    links = db.execute('''select l.source_id,s.name,l.url,l.external_id,l.link_type,l.payload from radar_source_links l
      join radar_data_sources s using(source_id) where opportunity_id=%s and source_hash=%s
      order by l.captured_at desc,l.id desc limit 200''', scope).fetchall()
    items, sources, seen = [], [], set()
    for source, name, url, external, kind, rows in links:
        sources.append({'id': source, 'name': name, 'url': url, 'externalId': external, 'linkType': kind})
        if kind == 'item_page':
            for item in _items(source, rows):
                key = (source, item['number'])
                if key not in seen:
                    seen.add(key); items.append(item)
    docs = db.execute('''select document_key,title,url,content_hash,extraction_state,pages from radar_documents
      where opportunity_id=%s and source_hash=%s order by id limit 100''', scope).fetchall()
    documents = [{'title': title, 'url': url, 'status': state, 'contentHash': sha, 'documentKey': key}
                 for key, title, url, sha, state, _ in docs]
    excerpts = [{'documentKey': key, 'page': page['page'], 'text': page['text'][:2000]}
                for key, _, _, _, _, pages in docs for page in pages if page.get('text')][:30]
    statuses = db.execute('select status,count(*) from radar_enrichment_jobs where opportunity_id=%s and source_hash=%s group by status', scope).fetchall()
    counts = dict(statuses)
    incomplete_docs = {r[4] for r in docs if r[4] != 'text_available'}
    state = ('pending' if any(counts.get(s) for s in ('pending', 'processing', 'retry')) else
             'partial' if counts.get('blocked') or incomplete_docs else 'available' if counts else 'not_requested')
    return {'analysisStatus': state, 'items': items[:300], 'documents': documents, 'textExcerpts': excerpts,
            'sources': sources[:30], 'limitations': sorted(incomplete_docs) + ['extractive_evidence_not_legal_analysis']}
