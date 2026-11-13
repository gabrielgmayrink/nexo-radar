"""Radar-only PostgreSQL access. Never expose a connection exception to a client."""
from __future__ import annotations

import hashlib
import json
import os
import gzip
from datetime import date, datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import psycopg
from psycopg.types.json import Jsonb

from radar.canonical import to_card
from radar.relevance import TZ
from radar.sync import initial_cursor, public_progress
from radar.raw_codec import encode_raw
from radar.identifiers import parse_pncp_id
from radar.learning import object_hash

PROJECT_REF = os.environ.get('RADAR_SUPABASE_PROJECT_REF', '')
LOCK_ID = 739241663


def connection_string(*,service=None):
    url = os.environ.get('SUPABASE_URL', '')
    if not PROJECT_REF or urlparse(url).hostname != PROJECT_REF + '.supabase.co':
        raise ValueError('Unexpected Radar database')
    if service not in (None,'api','collector'):raise ValueError('Invalid database service')
    raw=os.environ.get('RADAR_'+service.upper()+'_DATABASE_URL') if service else None
    if service and not raw and os.environ.get('RADAR_DB_SERVICE_CREDENTIALS')=='1':
        raise ValueError('Dedicated service credential required')
    raw = raw or os.environ.get('POSTGRES_URL_NON_POOLING') or os.environ.get('POSTGRES_URL')
    parsed = urlparse(raw or '')
    if parsed.scheme not in ('postgres', 'postgresql') or not parsed.password:
        raise ValueError('Postgres connection unavailable')
    if PROJECT_REF not in (parsed.username or '') and PROJECT_REF not in (parsed.hostname or ''):
        raise ValueError('Unexpected Postgres project')
    if parsed.port == 6543:
        raise ValueError('Session pooling is required for collection locks')
    from radar.database_tls import tls_parameters
    query = tls_parameters({k: v for k, v in parse_qsl(parsed.query) if k in ('sslmode', 'sslrootcert', 'application_name')})
    query.update(connect_timeout='15', application_name='radar-collector')
    return urlunparse(parsed._replace(query=urlencode(query)))


def source_version(row):
    raw = row.get('dataAtualizacaoGlobal') or row.get('dataAtualizacao') or row.get('dataPublicacaoPncp')
    if not raw:
        return None
    value = datetime.fromisoformat(raw.replace('Z', '+00:00'))
    return (value.replace(tzinfo=TZ) if value.tzinfo is None else value).astimezone(timezone.utc)


def prepared_record(row):
    card = to_card(row)
    identifier=parse_pncp_id(row['numeroControlePNCP']).canonical
    card['id']=identifier
    raw = json.dumps(row, sort_keys=True, ensure_ascii=False)
    return (identifier, Jsonb(row), Jsonb(card['scores']), card['ruleVersion'],
            card['score'], Jsonb(card) if card['score']>=40 else None, source_version(row), hashlib.sha256(raw.encode()).hexdigest(),
            card.get('classificationVersion',card['ruleVersion']),object_hash(card['object'],card['additionalInfo']))


def capture_observations(records):
    observations=[];valid=[];seen=set()
    for ordinal,row in enumerate(records):
        identifier=None;reason=None;duplicate=False
        raw=json.dumps(row,sort_keys=True,ensure_ascii=False).encode()
        try:
            identifier=parse_pncp_id(row.get('numeroControlePNCP') if isinstance(row,dict) else None).canonical
            duplicate=identifier in seen
            if duplicate:raise ValueError('duplicate_source_identifier')
            seen.add(identifier)
            prepared_record(row)
        except (ValueError,TypeError,KeyError,AttributeError,ArithmeticError):
            reason='invalid_identifier' if identifier is None else 'duplicate_source_identifier' if duplicate else 'record_processing_failed'
        observations.append({'ordinal':ordinal,'opportunity_id':identifier,'content_hash':hashlib.sha256(raw).hexdigest(),
                             'parse_state':'quarantined' if reason else 'indexed','reason':reason})
        if not reason:valid.append((ordinal,row))
    return observations,valid


class PostgresStore:
    def __init__(self, connection=None,*,service='api'):
        if service not in ('api','collector'):raise ValueError('Invalid database service')
        self.db = connection or psycopg.connect(connection_string(service=service), autocommit=True)
        if connection is None and os.environ.get('RADAR_DB_SERVICE_CREDENTIALS')=='1':
            self.db.execute('set role '+{'api':'radar_api','collector':'radar_collector'}[service])
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
        from radar.profiles import profile_context
        with profile_context(self.db):
            return self._write_records_with_profiles(records)

    def _write_records_with_profiles(self, records):
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
                    'content_hash':r[7],'classification_version':r[8],'object_hash':r[9]} for record,r in best.values()]
        previous={identifier:(payload,updated_at) for identifier,payload,updated_at in self.db.execute(
            'select id,payload,updated_at from radar_opportunities where id=any(%s) for update',
            ([r['id'] for r in documents],)).fetchall()}
        updated=self.db.execute('''insert into radar_opportunities(id,payload,product_scores,rule_version,score,card,source_updated_at,content_hash,classification_version,object_hash,catalog_seen_at)
                select id,payload,product_scores,rule_version,score,card,source_updated_at,content_hash,classification_version,object_hash,now()
                from jsonb_to_recordset(%s::jsonb) as r(id text,payload jsonb,product_scores jsonb,rule_version text,
                    score integer,card jsonb,source_updated_at timestamptz,content_hash text,classification_version text,object_hash text)
                on conflict(id) do update set payload=excluded.payload,
                product_scores=excluded.product_scores,rule_version=excluded.rule_version,score=excluded.score,
                card=excluded.card,source_updated_at=excluded.source_updated_at,content_hash=excluded.content_hash,updated_at=now(),
                classification_version=excluded.classification_version,object_hash=excluded.object_hash,catalog_seen_at=now(),
                catalog_archived_at=null,catalog_archive_reason=null
                where (radar_opportunities.source_updated_at is null
                   or excluded.source_updated_at >= radar_opportunities.source_updated_at)
                  and (radar_opportunities.content_hash is distinct from excluded.content_hash
                       or radar_opportunities.classification_version is distinct from excluded.classification_version)
                returning id''', (Jsonb(documents),)).fetchall()
        updated={r[0] for r in updated}
        from radar.procurement_events import source_changes,write_events
        events=[]
        for doc in documents:
            if doc['id'] in updated:
                old,revision=previous.get(doc['id'],(None,None))
                events.extend(source_changes(doc['id'],old,doc['payload'],transition_id=revision.isoformat() if revision else None))
        write_events(self.db,events)
        self.db.execute('update radar_opportunities set catalog_seen_at=now() where id=any(%s)',([r[0] for r in rows],))

    def capture_page(self,execution_id,pass_number,page,payload,*,mode='proposta',modality=0,wire=None,transport_status=200,truncated=False):
        """Commit the bounded original response BEFORE interpreting any row."""
        raw=wire if wire is not None else json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()
        if len(raw)>4_000_001:raise ValueError('Capture budget exceeded')
        digest=hashlib.sha256(raw).hexdigest()
        total=payload.get('totalRegistros') if isinstance(payload,dict) else None
        pages=payload.get('totalPaginas') if isinstance(payload,dict) else None
        total=total if type(total) is int and total>=0 else None
        pages=pages if type(pages) is int and pages>=0 else None
        return self.db.execute('''insert into radar_source_pages(execution_id,pass_number,page_number,source_mode,modality,
            content_hash,payload_gzip,source_total,source_pages,transport_status,truncated)
            values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            on conflict(execution_id,pass_number,page_number,source_mode,modality,content_hash)
            do update set transport_status=excluded.transport_status returning id''',
            (execution_id,pass_number,page,mode,modality,digest,gzip.compress(raw,mtime=0),total,pages,transport_status,truncated)).fetchone()[0]

    def quarantine_page(self,capture_id,reason):
        self.db.execute('''insert into radar_quarantine(capture_id,ordinal,reason) values(%s,-1,%s)
            on conflict(capture_id,ordinal) do update set attempts=radar_quarantine.attempts+1''',(capture_id,reason))

    def ingest_capture(self,capture_id,records):
        """Batch the normal path; isolate bad records only when a row fails."""
        from radar.profiles import profile_context
        with profile_context(self.db):return self._ingest_capture_with_profiles(capture_id,records)

    def _ingest_capture_with_profiles(self,capture_id,records):
        observations,valid=capture_observations(records)
        with self.db.transaction():
            try:
                with self.db.transaction():self._write_records_with_profiles([row for _,row in valid])
            except (psycopg.DataError,psycopg.IntegrityError):
                # A constraint/data anomaly must not hold back the remaining rows.
                for ordinal,row in valid:
                    try:
                        with self.db.transaction():self._write_records_with_profiles([row])
                    except (psycopg.DataError,psycopg.IntegrityError):
                        observations[ordinal].update(parse_state='quarantined',reason='record_storage_failed')
            self.db.execute('''insert into radar_source_observations(capture_id,ordinal,opportunity_id,content_hash,parse_state)
                select %s,ordinal,opportunity_id,content_hash,parse_state from jsonb_to_recordset(%s::jsonb)
                as r(ordinal integer,opportunity_id text,content_hash text,parse_state text)
                on conflict(capture_id,ordinal) do update set opportunity_id=excluded.opportunity_id,
                content_hash=excluded.content_hash,parse_state=excluded.parse_state''',(capture_id,Jsonb(observations)))
            self.db.execute('''insert into radar_quarantine(capture_id,ordinal,reason)
                select %s,ordinal,reason from jsonb_to_recordset(%s::jsonb) as r(ordinal integer,reason text)
                where reason is not null on conflict(capture_id,ordinal) do update set
                reason=excluded.reason,attempts=radar_quarantine.attempts+1,resolved_at=null''',(capture_id,Jsonb(observations)))
            self.db.execute('''update radar_quarantine set resolved_at=now() where capture_id=%s
                and ordinal=any(%s)''',(capture_id,[r['ordinal'] for r in observations if not r['reason']]+[-1]))
            # A complete valid retry supersedes a malformed transport/envelope
            # for this page. Preserve its bytes and error history, close only the
            # page-level failure; row-level anomalies remain independently queued.
            self.db.execute('''update radar_quarantine q set resolved_at=now()
                from radar_source_pages prior,radar_source_pages current
                where current.id=%s and prior.execution_id=current.execution_id
                and prior.pass_number=current.pass_number and prior.page_number=current.page_number
                and prior.source_mode=current.source_mode and prior.modality=current.modality
                and q.capture_id=prior.id and q.ordinal=-1 and q.resolved_at is null''',(capture_id,))
        return [r['opportunity_id'] for r in observations if not r['reason']]

    def reprocess_quarantine(self,*,limit=5):
        import io
        if not 1<=limit<=20:raise ValueError('Invalid quarantine batch')
        captures=self.db.execute('''select distinct p.id,p.payload_gzip,p.page_number,p.source_mode from radar_source_pages p
            join radar_quarantine q on q.capture_id=p.id where q.resolved_at is null and q.attempts<5
            order by p.id limit %s''',(limit,)).fetchall()
        processed=0
        for capture_id,compressed,page,mode in captures:
            try:
                with gzip.GzipFile(fileobj=io.BytesIO(bytes(compressed))) as stream:raw=stream.read(4_000_002)
                if len(raw)>4_000_001:raise ValueError('Capture budget exceeded')
                payload=json.loads(raw)
                if not isinstance(payload,dict) or not isinstance(payload.get('data'),list):raise ValueError('Invalid page')
                if mode=='proposta':
                    from radar.national_collection import validate_payload
                    validate_payload(payload,page,strict_records=False)
                else:
                    from radar.incremental_collection import validate_incremental
                    validate_incremental(payload,page)
                self.ingest_capture(capture_id,payload['data'])
            except (ValueError,TypeError,OSError):
                self.db.execute('update radar_quarantine set attempts=attempts+1 where capture_id=%s and resolved_at is null',(capture_id,))
            processed+=1
        pending=self.db.execute('select count(*) from radar_quarantine where resolved_at is null').fetchone()[0]
        return {'done':pending==0,'processed':processed,'remaining':pending}

    def pass_evidence(self,execution_id,pass_number):
        pages=self.db.execute('''select min(page_number),max(page_number),count(*),min(source_total),max(source_total),max(source_pages)
            from radar_national_pages where execution_id=%s and pass_number=%s''',(execution_id,pass_number)).fetchone()
        membership=self.db.execute('''select o.opportunity_id,min(o.content_hash),max(o.content_hash)
            from radar_source_observations o join radar_national_pages p on p.capture_id=o.capture_id
            where p.execution_id=%s and p.pass_number=%s and o.opportunity_id is not null
            group by o.opportunity_id order by o.opportunity_id''',(execution_id,pass_number)).fetchall()
        pending=self.db.execute('''select count(*) from radar_quarantine q join radar_national_pages p on p.capture_id=q.capture_id
            where p.execution_id=%s and p.pass_number=%s and q.resolved_at is null''',(execution_id,pass_number)).fetchone()[0]
        fingerprint=hashlib.sha256(json.dumps(membership,separators=(',',':')).encode()).hexdigest()
        count=len(membership)
        complete=pages[0]==1 and pages[1]==pages[2]==max(1,pages[5] or 0)
        return {'complete':complete,'count':count,'fingerprint':fingerprint,'quarantined':pending,
                'stableWithinPass':complete and pages[3]==pages[4]==count and all(a==b for _,a,b in membership)}

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

    def commit_national_page(self,execution_id,records,cursor,page,digest,total,pages,*,capture_id=None):
        if self.db.execute('select pg_database_size(current_database())').fetchone()[0]>450*1024*1024:raise ValueError('storage_guard')
        with self.db.transaction():
            capture_id=capture_id or self.capture_page(execution_id,cursor.get('passNumber',1),page,
                {'data':records,'totalRegistros':total,'totalPaginas':pages,'numeroPagina':page})
            identifiers=self.ingest_capture(capture_id,records)
            self.db.execute('update radar_opportunities set national_execution_id=%s,national_pass=%s,catalog_archived_at=null,catalog_archive_reason=null where id=any(%s)',
                             (execution_id,cursor.get('passNumber',1),identifiers))
            self.db.execute('insert into radar_national_pages(execution_id,pass_number,page_number,content_hash,record_count,source_total,source_pages,capture_id) values(%s,%s,%s,%s,%s,%s,%s,%s)',
                             (execution_id,cursor.get('passNumber',1),page,digest,len(records),total,pages,capture_id))
            self._checkpoint('national_open',cursor)
            self.db.execute("update radar_executions set status='running',metrics=%s where id=%s",(Jsonb(public_progress(cursor,execution_id)),execution_id))

    def commit_page(self, execution_id, kind, records, cursor, *, source_page=None,capture_id=None):
        if self.db.execute('select pg_database_size(current_database())').fetchone()[0]>450*1024*1024:
            raise ValueError('storage_guard')
        with self.db.transaction():
            # Incremental responses have their own immutable source receipt.
            source=source_page or {}
            capture_id=capture_id or self.capture_page(execution_id,1,source.get('page',cursor['pages']),
                source.get('payload',{'data':records}),mode=source.get('mode','publicacao'),modality=source.get('modality',0))
            identifiers=self.ingest_capture(capture_id,records)
            cursor['quarantinedRecords']=cursor.get('quarantinedRecords',0)+len(records)-len(identifiers)
            cursor['indexingComplete']=cursor['quarantinedRecords']==0
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
            cursor['completedAt']=datetime.now(timezone.utc).isoformat()
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
            content = {**public_progress(cursor, execution_id), 'completedAt': cursor['completedAt'],
                       **({'minimumPass':cursor.get('minimumPass',1),'basePagesComplete':True} if kind=='national_open' else {}),
                       'catalogWindow':{'scope':'all_open_brazil','publicationDateFilter':None} if kind=='national_open' else {'start':cutoff,'end':cursor['end']},
                       'metrics': {'unique': total, 'candidates': candidates, 'discarded': total - candidates}}
            self._checkpoint(kind, cursor)
            self.db.execute("update radar_executions set status='ok',metrics=%s,finished_at=now() where id=%s",
                            (Jsonb(content), execution_id))
            self.db.execute('''insert into radar_catalog_state(id,content) values(%s,%s)
                on conflict(id) do update set content=excluded.content,updated_at=now()''',
                            ('open' if kind in ('open','national_open') else 'publications', Jsonb(content)))
