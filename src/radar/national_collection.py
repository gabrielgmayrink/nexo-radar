"""All open PNCP procurements: no company, UF, modality or publication-date filter."""
import hashlib
import json
import base64
import gzip
import io
from datetime import datetime,timedelta,timezone
from radar.sync import upgrade_cursor,page_query,advance,public_progress
from radar.relevance import TZ
from radar.identifiers import parse_pncp_id

KIND='national_open'
SOURCE_PATH='/v1/contratacoes/proposta'


class StalePage(ValueError):pass


def decode_wire(body):
    encoded=body.get('wireGzipBase64')
    if encoded is None:return None
    if not isinstance(encoded,str) or len(encoded)>2_800_000:raise ValueError('Invalid wire capture')
    compressed=base64.b64decode(encoded,validate=True)
    with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:wire=stream.read(4_000_002)
    if len(wire)>4_000_001:raise ValueError('Wire capture too large')
    return wire


def validate_wire_payload(wire,payload):
    if wire is None:return
    # A documented 204 has no bytes and is normalized to an empty data list.
    if not wire and payload=={'data':[]}:return
    try:original=json.loads(wire)
    except (ValueError,UnicodeError):raise ValueError('Invalid captured JSON') from None
    if original!=payload:raise ValueError('Captured response differs from supplied page')


def validate_payload(payload,page,*,strict_records=True):
    if not isinstance(payload,dict) or not isinstance(payload.get('data'),list) or len(payload['data'])>50:
        raise ValueError('Invalid national page')
    total, pages, number=(payload.get(key) for key in ('totalRegistros','totalPaginas','numeroPagina'))
    if any(type(value) is not int or value<0 for value in (total,pages,number)) or number!=page:
        raise ValueError('Missing national coverage metadata')
    if pages!=(total+49)//50 or (total and page>pages):raise ValueError('Inconsistent national pagination')
    rows=payload['data']
    expected=min(50,max(0,total-(page-1)*50))
    if len(rows)!=expected:raise ValueError('Incomplete national page')
    if strict_records:
        identifiers=[]
        for row in rows:
            identifiers.append(parse_pncp_id(row.get('numeroControlePNCP') if isinstance(row,dict) else None).canonical)
        if len(set(identifiers))!=len(identifiers):raise ValueError('Duplicate IDs within national page')
    return rows,total,pages


def plan(cursor,execution_id):
    progress=public_progress(cursor,execution_id)
    if progress['done']:return progress
    cursor=upgrade_cursor(cursor)
    if not cursor['pending_tasks']:raise ValueError('National cursor has no pending page')
    _,_,query=page_query(cursor)
    return {**progress,'plan':{'executionId':execution_id,'passNumber':cursor.get('passNumber',1),
                             'page':query['pagina'],'path':SOURCE_PATH,'query':query}}


def finish_if_ready(store,cursor,execution_id):
    if cursor['status']=='ok':return cursor
    if cursor['pending_tasks']:return cursor
    pass_number=cursor.get('passNumber',1)
    evidence=store.pass_evidence(execution_id,pass_number)
    if not evidence['complete']:
        raise ValueError('National coverage ledger has missing pages')
    previous=cursor.get('previousPassEvidence')
    consistent=bool(previous and previous.get('stableWithinPass') and evidence['stableWithinPass']
                    and previous['count']==evidence['count'] and previous['fingerprint']==evidence['fingerprint']
                    and previous.get('quarantined',0)==evidence['quarantined']==0)
    cursor.update(uniqueRecords=evidence['count'],captureComplete=True,basePagesComplete=True,
                  indexingComplete=evidence['quarantined']==0,quarantinedRecords=evidence['quarantined'],
                  verificationPolicy='stable_sets_v1',coverageComplete=consistent,
                  previousPassEvidence=evidence)
    # A complete capture and a stable source snapshot are different outcomes.
    # Stop after two bounded full observations; an unstable live source remains
    # explicitly pending instead of being called loss-free or replayed forever.
    completed=cursor.get('completedFullPasses',0)+1
    cursor['completedFullPasses']=completed
    if consistent or completed>=2:
        cursor.update(status='ok',consistency='stable_sets' if consistent else
                      'quarantine_pending' if evidence['quarantined'] else 'source_changed',
                      pending_tasks=[],partition=1,minimumPass=pass_number)
        store.complete(execution_id,KIND,cursor)
    else:
        cursor.update(passNumber=pass_number+1,passPages=0,pending_tasks=[{'mode':'proposta','modality':0,'page':1,'fingerprints':[]}],
                      partition=0,page=1,fingerprints=[],status='running',consistency='verifying',error=None)
        store.save_failure(execution_id,KIND,cursor)
    return cursor


def handle_national(store,action,body,run_key):
    if not store.acquire():return {'busy':True,'done':False}
    try:
        requested=body.get('executionId')
        if requested is not None and (type(requested) is not int or requested<1):raise ValueError('Invalid execution')
        execution_id,cursor=store.start_or_resume(KIND,run_key,requested,datetime.now(TZ).date())
        cursor=upgrade_cursor(cursor)
        # The proposal route is live and unbounded by publication date. This is
        # the observation day, including a resumed capture started on another day.
        cursor['end']=datetime.now(TZ).date().isoformat()
        cursor['last_run_key']=run_key
        cursor=finish_if_ready(store,cursor,execution_id)
        if action=='national_plan':return plan(cursor,execution_id)
        page=body.get('page');pass_number=body.get('passNumber')
        if type(page) is not int or page<1 or type(pass_number) is not int or pass_number<1:raise ValueError('Invalid page reference')
        if action=='national_capture':
            if cursor['status']=='ok':return plan(cursor,execution_id)
            if pass_number!=cursor.get('passNumber',1):raise StalePage('National pass changed')
            wire=decode_wire(body)
            if wire is None:raise ValueError('Missing wire capture')
            status=body.get('transportStatus');truncated=body.get('truncated',False)
            if status is not None and (type(status) is not int or not 100<=status<=599):raise ValueError('Invalid transport status')
            if type(truncated) is not bool:raise ValueError('Invalid truncation flag')
            capture_id=store.capture_page(execution_id,pass_number,page,None,wire=wire,
                transport_status=status,truncated=truncated)
            store.quarantine_page(capture_id,'transport_or_page_contract')
            return {**plan(cursor,execution_id),'rawCaptured':True}
        if action=='national_reconcile':
            if cursor['status']=='ok':return plan(cursor,execution_id)
            if page!=page_query(cursor)[2]['pagina'] or pass_number!=cursor.get('passNumber',1):raise StalePage('National page changed')
            _,total,pages=validate_payload(body.get('payload'),1)
            if pages>=page:raise ValueError('Source did not shorten its page list')
            if cursor.get('expectedRecords',0)>0 and total==0:raise ValueError('Unexpected empty national source')
            _,covered=store.national_counts(execution_id,pass_number)
            cursor.update(expectedRecords=total,expectedPages=pages,passNumber=pass_number+1,passPages=0,
                          pending_tasks=[{'mode':'proposta','modality':0,'page':1,'fingerprints':[]}],partition=0,page=1,
                          fingerprints=[],status='running',coverageComplete=False,error='coverage_gap',
                          basePagesComplete=cursor.get('basePagesComplete',False) or covered>=pages)
            store.save_failure(execution_id,KIND,cursor)
            return plan(cursor,execution_id)
        if action=='national_commit':
            # This durable capture survives row-level parser and transaction failures.
            wire=decode_wire(body)
            capture_id=store.capture_page(execution_id,pass_number,page,body.get('payload'),wire=wire)
            try:
                validate_wire_payload(wire,body.get('payload'))
                rows,total,pages=validate_payload(body.get('payload'),page,strict_records=False)
            except ValueError:
                store.quarantine_page(capture_id,'page_contract')
                raise
            digest=hashlib.sha256(json.dumps(body['payload'],sort_keys=True,ensure_ascii=False).encode()).hexdigest()
            previous=store.national_page(execution_id,pass_number,page)
            if previous:
                if previous!=digest:raise StalePage('Committed page has different content')
                return {**plan(cursor,execution_id),'alreadyCommitted':True}
            if cursor['status']=='ok' or pass_number!=cursor.get('passNumber',1) or page!=page_query(cursor)[2]['pagina']:
                raise StalePage('National page changed')
            # Metadata drives pagination; malformed rows are indexed independently.
            pagination_rows=[row if isinstance(row,dict) and row.get('numeroControlePNCP') else
                             {'numeroControlePNCP':'quarantined-row-'+str(index)} for index,row in enumerate(rows)]
            cursor=advance(cursor,pagination_rows,body['payload'])
            cursor.update(expectedRecords=total,expectedPages=pages,passPages=page,status='running',coverageComplete=False)
            cursor.pop('error',None);cursor.pop('next_attempt_at',None)
            store.commit_national_page(execution_id,rows,cursor,page,digest,total,pages,capture_id=capture_id)
            cursor=finish_if_ready(store,cursor,execution_id)
            return plan(cursor,execution_id)
        if action=='national_failure':
            if cursor['status']=='ok':return plan(cursor,execution_id)
            if page!=page_query(cursor)[2]['pagina'] or pass_number!=cursor.get('passNumber',1):raise StalePage('National page changed')
            reason=body.get('reason')
            if reason not in ('timeout','erro_transporte','http_429','resposta_html_waf','source_contract','source_5xx'):raise ValueError('Invalid source error')
            delay=body.get('retryAfterSeconds',0)
            if type(delay) is not int or not 0<=delay<=86400:raise ValueError('Invalid source retry delay')
            cursor.update(status='partial',error=reason,coverageComplete=False)
            if delay:
                cursor['next_attempt_at']=(datetime.now(timezone.utc)+timedelta(seconds=delay)).isoformat()
            store.save_failure(execution_id,KIND,cursor)
            return plan(cursor,execution_id)
        raise ValueError('Invalid national operation')
    finally:store.release()
