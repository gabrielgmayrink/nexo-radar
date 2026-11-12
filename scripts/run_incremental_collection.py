"""Daily, bounded official publication/update catch-up; no national full scan."""
import json
import os
import time
from datetime import datetime
from radar.pncp import PUBLICATION_MODALITIES,PNCPError
from radar.incremental_collection import validate_incremental
from run_national_collection import Receiver,Source,capture_failure,wire_fields


def validate_plan(plan):
    if not isinstance(plan,dict) or plan.get('mode') not in ('publicacao','atualizacao'):raise ValueError('Invalid incremental source')
    mode=plan['mode'];modality=plan.get('modality');page=plan.get('page');query=plan.get('query')
    if modality not in PUBLICATION_MODALITIES or type(page) is not int or page<1:raise ValueError('Invalid incremental partition')
    if plan.get('path')!='/v1/contratacoes/'+mode or not isinstance(query,dict):raise ValueError('Invalid source plan')
    if set(query)!={'pagina','tamanhoPagina','dataInicial','dataFinal','codigoModalidadeContratacao'}:raise ValueError('Unexpected filters')
    if query['pagina']!=page or query['tamanhoPagina']!=50 or query['codigoModalidadeContratacao']!=modality:raise ValueError('Invalid pagination')
    start=datetime.strptime(query['dataInicial'],'%Y%m%d');end=datetime.strptime(query['dataFinal'],'%Y%m%d')
    if start>end:raise ValueError('Invalid source window')
    return plan


def run(*,budget_seconds=1200,receiver=None,source=None):
    if type(budget_seconds) is not int or not 120<=budget_seconds<=7200:raise ValueError('Invalid incremental budget')
    receiver=receiver or Receiver();source=source or Source();started=time.monotonic()
    progress=receiver.post({'action':'incremental_plan'})
    try:
        while time.monotonic()-started<budget_seconds-75:
            if progress.get('done'):return 0
            delay=progress.get('retryAfterSeconds',0)
            if progress.get('busy') or delay:
                time.sleep(min(60,max(5,delay)));progress=receiver.post({'action':'incremental_plan'});continue
            plan=validate_plan(progress.get('plan'))
            ref={key:plan[key] for key in ('executionId','mode','modality','page')}
            try:
                payload=source.fetch_query(plan['path'],plan['query'],plan['modality'])
                validate_incremental(payload,plan['page'])
            except (PNCPError,ValueError) as error:
                capture_failure(receiver,source,plan,action='incremental_capture')
                raw=str(error) if isinstance(error,PNCPError) else 'source_contract'
                reason='source_5xx' if raw.startswith('http_5') else raw
                if reason not in ('timeout','erro_transporte','http_429','resposta_html_waf','source_5xx'):reason='source_contract'
                progress=receiver.post({'action':'incremental_failure',**ref,'reason':reason,
                    'retryAfterSeconds':min(86400,max(60,int(getattr(error,'retry_after_seconds',None) or 60)))})
                continue
            progress=receiver.post({'action':'incremental_commit',**ref,'payload':payload,**wire_fields(source,plan['page'])})
            print(json.dumps({'event':'incremental_progress',**{key:progress.get(key) for key in ('executionId','done','pages','recordsReceived','completedPartitions','totalPartitions')}}),flush=True)
        print('::warning title=Atualização incremental pendente::O progresso está salvo; a próxima execução retomará todas as páginas pendentes.',flush=True)
        return 2
    finally:
        if hasattr(receiver,'close'):receiver.close()


if __name__=='__main__':
    try:raise SystemExit(run(budget_seconds=int(os.environ.get('RADAR_INCREMENTAL_BUDGET_SECONDS','1200'))))
    except Exception as error:
        print(json.dumps({'event':'incremental_worker_failed','errorType':type(error).__name__}),flush=True)
        raise SystemExit(1)
