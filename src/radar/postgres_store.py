"""Radar-only PostgreSQL access. Never expose a connection exception to a client."""
from __future__ import annotations

import hashlib
import json
import os
from datetime import date, datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import psycopg
from psycopg.types.json import Jsonb

from radar.canonical import to_card
from radar.relevance import TZ
from radar.sync import initial_cursor, public_progress
from radar.raw_codec import encode_raw

PROJECT_REF = os.environ.get('RADAR_SUPABASE_PROJECT_REF', '')
LOCK_ID = 739241663


def connection_string():
    url = os.environ.get('SUPABASE_URL', '')
    if not PROJECT_REF or urlparse(url).hostname != PROJECT_REF + '.supabase.co':
        raise ValueError('Unexpected Radar database')
    raw = os.environ.get('POSTGRES_URL_NON_POOLING') or os.environ.get('POSTGRES_URL')
    parsed = urlparse(raw or '')
    if parsed.scheme not in ('postgres', 'postgresql') or not parsed.password:
        raise ValueError('Postgres connection unavailable')
    if PROJECT_REF not in (parsed.username or '') and PROJECT_REF not in (parsed.hostname or ''):
        raise ValueError('Unexpected Postgres project')
    if parsed.port == 6543:
        raise ValueError('Session pooling is required for collection locks')
    query = {k: v for k, v in parse_qsl(parsed.query) if k in ('sslmode', 'application_name')}
    query.update(sslmode='require', connect_timeout='15', application_name='radar-collector')
    return urlunparse(parsed._replace(query=urlencode(query)))


def source_version(row):
    raw = row.get('dataAtualizacaoGlobal') or row.get('dataAtualizacao') or row.get('dataPublicacaoPncp')
    if not raw:
        return None
    value = datetime.fromisoformat(raw.replace('Z', '+00:00'))
    return (value.replace(tzinfo=TZ) if value.tzinfo is None else value).astimezone(timezone.utc)


def prepared_record(row):
    card = to_card(row)
    raw = json.dumps(row, sort_keys=True, ensure_ascii=False)
    return (row['numeroControlePNCP'], Jsonb(row), Jsonb(card['scores']), card['ruleVersion'],
            card['score'], Jsonb(card) if card['score']>=40 else None, source_version(row), hashlib.sha256(raw.encode()).hexdigest())


class PostgresStore:
    def __init__(self, connection=None):
        self.db = connection or psycopg.connect(connection_string(), autocommit=True)
        self.db.execute("set statement_timeout='25s'")
        self.db.execute("set lock_timeout='5s'")

    def close(self):
        self.db.close()

    def acquire(self):
        return self.db.execute('select pg_try_advisory_lock(%s)', (LOCK_ID,)).fetchone()[0]

    def release(self):
        self.db.execute('select pg_advisory_unlock(%s)', (LOCK_ID,))

    def start_or_resume(self, kind, run_key, execution_id, today):
        found = self.db.execute('select cursor from radar_checkpoints where key=%s', ('sync:' + kind,)).fetchone()
        if found:
            cursor = found[0]
            if execution_id is not None and cursor['execution_id'] != execution_id:
                raise ValueError('Collection execution changed')
            if cursor['status'] != 'ok' or cursor.get('run_key') == run_key or execution_id is not None:
                return cursor['execution_id'], cursor
        if execution_id is not None:
            raise ValueError('Unknown collection execution')
        if self.db.execute('select pg_database_size(current_database())').fetchone()[0] > 450 * 1024 * 1024:
            raise ValueError('Database storage guard reached')
        published = self.db.execute("select content from radar_catalog_state where id='publications'").fetchone()
        last = date.fromisoformat(published[0]['window']['end']) if published else None
        cursor = initial_cursor(kind, today, last)
        with self.db.transaction():
            execution_id = self.db.execute('insert into radar_executions(task,status) values(%s,%s) returning id',
                                           ('sync:' + kind, 'running')).fetchone()[0]
            cursor.update(execution_id=execution_id, run_key=run_key)
            self._checkpoint(kind, cursor)
        return execution_id, cursor

    def _checkpoint(self, kind, cursor):
        self.db.execute('''insert into radar_checkpoints(key,cursor) values(%s,%s)
            on conflict(key) do update set cursor=excluded.cursor,updated_at=now()''',
                        ('sync:' + kind, Jsonb(cursor)))

    def write_records(self, records):
        with self.db.transaction():
            self._write_records(records)

    def _write_records(self, records):
        records=list(records)
        rows = [prepared_record(row) for row in records]
        if not rows:return
        self.db.execute('''insert into radar_raw(opportunity_id,content_hash,payload_gzip)
            select * from unnest(%s::text[],%s::text[],%s::bytea[]) on conflict do nothing''',
                        ([r[0] for r in rows],[r[7] for r in rows],[encode_raw(record) for record in records]))
        best={}
        for record,r in zip(records,rows):
            previous=best.get(r[0])
            if previous and previous[1][6] and (not r[6] or r[6]<previous[1][6]):continue
            best[r[0]]=(record,r)
        documents=[{'id':r[0],'payload':record,'product_scores':r[2].obj,'rule_version':r[3],
                    'score':r[4],'card':r[5].obj if r[5] else None,'source_updated_at':r[6].isoformat() if r[6] else None,
                    'content_hash':r[7]} for record,r in best.values()]
        self.db.execute('''insert into radar_opportunities(id,payload,product_scores,rule_version,score,card,source_updated_at,content_hash)
                select id,payload,product_scores,rule_version,score,card,source_updated_at,content_hash
                from jsonb_to_recordset(%s::jsonb) as r(id text,payload jsonb,product_scores jsonb,rule_version text,
                    score integer,card jsonb,source_updated_at timestamptz,content_hash text)
                on conflict(id) do update set payload=excluded.payload,
                product_scores=excluded.product_scores,rule_version=excluded.rule_version,score=excluded.score,
                card=excluded.card,source_updated_at=excluded.source_updated_at,content_hash=excluded.content_hash,updated_at=now()
                where (radar_opportunities.source_updated_at is null
                   or excluded.source_updated_at >= radar_opportunities.source_updated_at)
                  and (radar_opportunities.content_hash is distinct from excluded.content_hash
                       or radar_opportunities.rule_version<>excluded.rule_version)''', (Jsonb(documents),))

    def national_page(self,execution_id,pass_number,page):
        result=self.db.execute('select content_hash from radar_national_pages where execution_id=%s and pass_number=%s and page_number=%s',
                               (execution_id,pass_number,page)).fetchone()
        return result[0] if result else None

    def national_counts(self,execution_id,pass_number,current_only=False):
        unique=self.db.execute('select count(*) from radar_opportunities where national_execution_id=%s'+(' and national_pass=%s' if current_only else ''),
                               (execution_id,pass_number) if current_only else (execution_id,)).fetchone()[0]
        pages=self.db.execute('select count(*) from radar_national_pages where execution_id=%s and pass_number=%s',
                              (execution_id,pass_number)).fetchone()[0]
        return unique,pages

    def commit_national_page(self,execution_id,records,cursor,page,digest,total,pages):
        if self.db.execute('select pg_database_size(current_database())').fetchone()[0]>450*1024*1024:raise ValueError('storage_guard')
        with self.db.transaction():
            self._write_records(records)
            self.db.execute('update radar_opportunities set national_execution_id=%s,national_pass=%s where id=any(%s)',
                             (execution_id,cursor.get('passNumber',1),[row['numeroControlePNCP'] for row in records]))
            self.db.execute('insert into radar_national_pages(execution_id,pass_number,page_number,content_hash,record_count,source_total,source_pages) values(%s,%s,%s,%s,%s,%s,%s)',
                             (execution_id,cursor.get('passNumber',1),page,digest,len(records),total,pages))
            self._checkpoint('national_open',cursor)
            self.db.execute("update radar_executions set status='running',metrics=%s where id=%s",(Jsonb(public_progress(cursor,execution_id)),execution_id))

    def commit_page(self, execution_id, kind, records, cursor):
        if self.db.execute('select pg_database_size(current_database())').fetchone()[0]>450*1024*1024:
            raise ValueError('storage_guard')
        with self.db.transaction():
            self.write_records(records)
            self._checkpoint(kind, cursor)
            self.db.execute("update radar_executions set status='running',metrics=%s where id=%s",
                            (Jsonb(public_progress(cursor, execution_id)), execution_id))

    def save_failure(self, execution_id, kind, cursor):
        with self.db.transaction():
            self._checkpoint(kind, cursor)
            self.db.execute("update radar_executions set status=%s,metrics=%s where id=%s",
                            (cursor['status'],Jsonb(public_progress(cursor, execution_id)), execution_id))

    def complete(self, execution_id, kind, cursor):
        with self.db.transaction():
            from datetime import timedelta
            cutoff=(date.fromisoformat(cursor['end'])-timedelta(days=29)).isoformat()
            now=datetime.now(TZ).replace(tzinfo=None).isoformat()
            if kind=='national_open':
                total,candidates=self.db.execute('select count(*),count(*) filter(where score>=40) from radar_opportunities where national_execution_id=%s and national_pass>=%s',
                                                 (execution_id,cursor.get('minimumPass',1))).fetchone()
            else:
                total, candidates = self.db.execute('''select count(*),count(*) filter(where score>=40) from radar_opportunities
                where coalesce(payload->>'dataPublicacaoPncp','') >= %s
                   or coalesce(payload->>'dataPublicacaoPncp','') = ''
                   or (payload->>'situacaoCompraId'='1' and coalesce(payload->>'dataEncerramentoProposta','') >= %s)''',
                                                   (cutoff,now)).fetchone()
            content = {**public_progress(cursor, execution_id), 'completedAt': datetime.now(timezone.utc).isoformat(),
                       **({'minimumPass':cursor.get('minimumPass',1),'basePagesComplete':True} if kind=='national_open' else {}),
                       'catalogWindow':{'scope':'all_open_brazil','publicationDateFilter':None} if kind=='national_open' else {'start':cutoff,'end':cursor['end']},
                       'metrics': {'unique': total, 'candidates': candidates, 'discarded': total - candidates}}
            self._checkpoint(kind, cursor)
            self.db.execute("update radar_executions set status='ok',metrics=%s,finished_at=now() where id=%s",
                            (Jsonb(content), execution_id))
            self.db.execute('''insert into radar_catalog_state(id,content) values(%s,%s)
                on conflict(id) do update set content=excluded.content,updated_at=now()''',
                            ('open' if kind in ('open','national_open') else 'publications', Jsonb(content)))
