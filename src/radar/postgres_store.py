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
        with self.db.cursor() as c:
            c.executemany('''insert into radar_raw(opportunity_id,content_hash,payload_gzip) values(%s,%s,%s)
                on conflict do nothing''', [(r[0], r[7], encode_raw(record)) for r,record in zip(rows,records)])
            c.executemany('''insert into radar_opportunities(id,payload,product_scores,rule_version,score,card,source_updated_at,content_hash)
                values(%s,%s,%s,%s,%s,%s,%s,%s) on conflict(id) do update set payload=excluded.payload,
                product_scores=excluded.product_scores,rule_version=excluded.rule_version,score=excluded.score,
                card=excluded.card,source_updated_at=excluded.source_updated_at,content_hash=excluded.content_hash,updated_at=now()
                where (radar_opportunities.source_updated_at is null
                   or excluded.source_updated_at >= radar_opportunities.source_updated_at)
                  and (radar_opportunities.content_hash is distinct from excluded.content_hash
                       or radar_opportunities.rule_version<>excluded.rule_version)''', rows)

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
            total, candidates = self.db.execute('''select count(*),count(*) filter(where score>=40) from radar_opportunities
                where coalesce(payload->>'dataPublicacaoPncp','') >= %s
                   or coalesce(payload->>'dataPublicacaoPncp','') = ''
                   or (payload->>'situacaoCompraId'='1' and coalesce(payload->>'dataEncerramentoProposta','') >= %s)''',
                                               (cutoff,now)).fetchone()
            content = {**public_progress(cursor, execution_id), 'completedAt': datetime.now(timezone.utc).isoformat(),
                       'catalogWindow':{'start':cutoff,'end':cursor['end']},
                       'metrics': {'unique': total, 'candidates': candidates, 'discarded': total - candidates}}
            self._checkpoint(kind, cursor)
            self.db.execute("update radar_executions set status='ok',metrics=%s,finished_at=now() where id=%s",
                            (Jsonb(content), execution_id))
            self.db.execute('''insert into radar_catalog_state(id,content) values(%s,%s)
                on conflict(id) do update set content=excluded.content,updated_at=now()''',
                            ('open' if kind == 'open' else 'publications', Jsonb(content)))
