"""All open PNCP procurements: no company, UF, modality or publication-date filter."""
import hashlib
import json
import re
from datetime import datetime,timedelta,timezone
from radar.sync import upgrade_cursor,page_query,advance,public_progress
from radar.relevance import TZ

KIND='national_open'
SOURCE_PATH='/v1/contratacoes/proposta'


class StalePage(ValueError):pass


def validate_payload(payload,page):
    if not isinstance(payload,dict) or not isinstance(payload.get('data'),list) or len(payload['data'])>50:
        raise ValueError('Invalid national page')
    total, pages, number=(payload.get(key) for key in ('totalRegistros','totalPaginas','numeroPagina'))
    if any(type(value) is not int or value<0 for value in (total,pages,number)) or number!=page:
        raise ValueError('Missing national coverage metadata')
    if pages!=(total+49)//50 or (total and page>pages):raise ValueError('Inconsistent national pagination')
    rows=payload['data']
    expected=min(50,max(0,total-(page-1)*50))
    if len(rows)!=expected:raise ValueError('Incomplete national page')
    for row in rows:
        # Preserve source IDs verbatim, including a mistyped year observed in
        # PNCP (20226). One upstream anomaly cannot prevent the national scan.
        if not isinstance(row,dict) or not re.fullmatch(r'[0-9]{14}-1-[0-9]{1,10}/[0-9]{4,10}',str(row.get('numeroControlePNCP',''))):
            raise ValueError('Invalid national procurement')
    if len({row['numeroControlePNCP'] for row in rows})!=len(rows):raise ValueError('Duplicate IDs within national page')
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
    if cursor['pending_tasks'] and not cursor.get('basePagesComplete'):return cursor
    pass_number=cursor.get('passNumber',1)
    unique,covered=store.national_counts(execution_id,pass_number)
    complete_fresh_pass=covered==max(1,cursor['expectedPages'])
    if cursor.get('basePagesComplete') and complete_fresh_pass:
        unique,_=store.national_counts(execution_id,pass_number,True)
    cursor.update(uniqueRecords=unique)
    # Recheck the head, then the tail: proposals are returned oldest-first in
    # production, so new publications can arrive after the scanned tail. Keep
    # every ID and retain the count gate; a remaining gap still triggers a full
    # verification pass rather than being declared complete.
    if cursor.get('basePagesComplete') and cursor.get('passPages',0)>0 and unique>=cursor['expectedRecords']:
        cursor.update(status='ok',coverageComplete=True,pending_tasks=[],partition=1,
                      minimumPass=pass_number if complete_fresh_pass else 1)
        store.complete(execution_id,KIND,cursor)
    elif (cursor.get('basePagesComplete') and cursor.get('passPages',0)>0
          and not cursor.get('tailChecked') and cursor.get('expectedPages',0)>3):
        gap=max(0,cursor['expectedRecords']-unique)
        window=max(3,(gap+49)//50+2)
        first=max(1,cursor['expectedPages']-window+1)
        cursor.update(passNumber=pass_number+1,passPages=0,tailChecked=True,
                      pending_tasks=[{'mode':'proposta','modality':0,'page':first,'fingerprints':[]}],
                      partition=0,page=first,fingerprints=[],status='running',error='coverage_gap')
        store.save_failure(execution_id,KIND,cursor)
    elif not cursor['pending_tasks']:
        if not cursor.get('basePagesComplete') and covered!=max(1,cursor['expectedPages']):
            raise ValueError('National coverage ledger has missing pages')
        cursor.update(passNumber=pass_number+1,passPages=0,pending_tasks=[{'mode':'proposta','modality':0,'page':1,'fingerprints':[]}],
                      partition=0,page=1,fingerprints=[],status='running',basePagesComplete=True,
                      error='coverage_gap' if unique<cursor['expectedRecords'] else None)
        store.save_failure(execution_id,KIND,cursor)
    return cursor


def handle_national(store,action,body,run_key):
    if not store.acquire():return {'busy':True,'done':False}
    try:
        requested=body.get('executionId')
        if requested is not None and (type(requested) is not int or requested<1):raise ValueError('Invalid execution')
        execution_id,cursor=store.start_or_resume(KIND,run_key,requested,datetime.now(TZ).date())
        cursor=upgrade_cursor(cursor)
        cursor['last_run_key']=run_key
        cursor=finish_if_ready(store,cursor,execution_id)
        if action=='national_plan':return plan(cursor,execution_id)
        page=body.get('page');pass_number=body.get('passNumber')
        if type(page) is not int or page<1 or type(pass_number) is not int or pass_number<1:raise ValueError('Invalid page reference')
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
            rows,total,pages=validate_payload(body.get('payload'),page)
            digest=hashlib.sha256(json.dumps(body['payload'],sort_keys=True,ensure_ascii=False).encode()).hexdigest()
            previous=store.national_page(execution_id,pass_number,page)
            if previous:
                if previous!=digest:raise StalePage('Committed page has different content')
                return {**plan(cursor,execution_id),'alreadyCommitted':True}
            if cursor['status']=='ok' or pass_number!=cursor.get('passNumber',1) or page!=page_query(cursor)[2]['pagina']:
                raise StalePage('National page changed')
            cursor=advance(cursor,rows,body['payload'])
            cursor.update(expectedRecords=total,expectedPages=pages,passPages=page,status='running',coverageComplete=False)
            cursor.pop('error',None);cursor.pop('next_attempt_at',None)
            store.commit_national_page(execution_id,rows,cursor,page,digest,total,pages)
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
