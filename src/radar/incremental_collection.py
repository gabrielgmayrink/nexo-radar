"""Publication/update catch-up fetched by the runner, durably ingested via OIDC."""
from datetime import datetime,timedelta,timezone
from radar.relevance import TZ
from radar.sync import upgrade_cursor,ready_cursor,page_query,advance,public_progress
from radar.national_collection import StalePage,decode_wire,validate_payload,validate_wire_payload

KIND='incremental'


def plan(cursor,execution_id):
    result=public_progress(cursor,execution_id)
    if result['done']:return result
    cursor=ready_cursor(cursor)
    mode,modality,query=page_query(cursor)
    return {**public_progress(cursor,execution_id),'plan':{'executionId':execution_id,
            'page':query['pagina'],'mode':mode,'modality':modality,
            'path':'/v1/contratacoes/'+mode,'query':query}}


def validate_incremental(payload,page):
    # PNCP's documented 204 is normalized by the runner to this exact empty page.
    if payload=={'data':[]}:return []
    return validate_payload(payload,page,strict_records=False)[0]


def handle_incremental(store,action,body,run_key):
    if not store.acquire():return {'busy':True,'done':False}
    try:
        requested=body.get('executionId')
        if requested is not None and (type(requested) is not int or requested<1):raise ValueError('Invalid execution')
        execution_id,cursor=store.start_or_resume(KIND,run_key,requested,datetime.now(TZ).date())
        cursor=ready_cursor(upgrade_cursor(cursor))
        if cursor['status']=='ok':return plan(cursor,execution_id)
        if not cursor['pending_tasks']:
            cursor.update(status='ok');store.complete(execution_id,KIND,cursor)
            return plan(cursor,execution_id)
        if action=='incremental_plan':return plan(cursor,execution_id)
        mode,modality,query=page_query(cursor)
        if (body.get('page'),body.get('mode'),body.get('modality'))!=(query['pagina'],mode,modality):
            raise StalePage('Incremental page changed')
        if action=='incremental_capture':
            wire=decode_wire(body)
            status=body.get('transportStatus');truncated=body.get('truncated',False)
            if wire is None or type(truncated) is not bool:raise ValueError('Invalid capture')
            if status is not None and (type(status) is not int or not 100<=status<=599):raise ValueError('Invalid status')
            receipt=store.capture_page(execution_id,1,query['pagina'],None,mode=mode,modality=modality,
                                       wire=wire,transport_status=status,truncated=truncated)
            store.quarantine_page(receipt,'transport_or_page_contract')
            return {**plan(cursor,execution_id),'rawCaptured':True}
        if action=='incremental_commit':
            payload=body.get('payload')
            wire=decode_wire(body)
            receipt=store.capture_page(execution_id,1,query['pagina'],payload,mode=mode,modality=modality,wire=wire)
            try:
                validate_wire_payload(wire,payload)
                rows=validate_incremental(payload,query['pagina'])
            except ValueError:
                store.quarantine_page(receipt,'page_contract');raise
            pagination_rows=[r if isinstance(r,dict) and r.get('numeroControlePNCP') else
                             {'numeroControlePNCP':'quarantined-row-'+str(i)} for i,r in enumerate(rows)]
            try:next_cursor=advance(cursor,pagination_rows,payload)
            except ValueError:
                store.quarantine_page(receipt,'page_contract');raise
            next_cursor.update(status='running',request_count=cursor['request_count']+1)
            for key in ('error','next_attempt_at'):next_cursor.pop(key,None)
            store.commit_page(execution_id,KIND,rows,next_cursor,capture_id=receipt)
            cursor=next_cursor
            if not cursor['pending_tasks']:
                cursor.update(status='ok');store.complete(execution_id,KIND,cursor)
            return plan(cursor,execution_id)
        if action=='incremental_failure':
            reason=body.get('reason')
            if reason not in ('timeout','erro_transporte','http_429','resposta_html_waf','source_contract','source_5xx'):raise ValueError('Invalid error')
            delay=body.get('retryAfterSeconds',60)
            if type(delay) is not int or not 1<=delay<=86400:raise ValueError('Invalid retry delay')
            retry=(datetime.now(timezone.utc)+timedelta(seconds=delay)).isoformat()
            tasks=cursor['pending_tasks']
            failed={**tasks[0],'next_attempt_at':retry}
            # Source-wide rate limits pause the whole queue; isolated timeouts
            # allow other modalities to proceed while preserving the failed page.
            cursor.update(status='partial',error=reason,request_errors=cursor['request_errors']+1,
                          request_count=cursor['request_count']+1,pending_tasks=tasks[1:]+[failed])
            if reason=='http_429':
                cursor['pending_tasks']=[{**task,'next_attempt_at':retry} for task in cursor['pending_tasks']]
            cursor=ready_cursor(cursor)
            store.save_failure(execution_id,KIND,cursor)
            return plan(cursor,execution_id)
        raise ValueError('Invalid incremental operation')
    finally:store.release()
