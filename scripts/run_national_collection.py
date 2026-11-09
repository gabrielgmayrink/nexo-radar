"""Fetch every national PNCP page on the runner; checkpoint each page through OIDC."""
import concurrent.futures
import gzip
import http.client
import io
import json
import os
import ssl
import threading
import time
from urllib.error import HTTPError,URLError
from urllib.request import Request,build_opener
from urllib.parse import urlsplit
from radar.pncp import PNCPClient,PNCPError,CollectionMetrics
from radar.national_collection import validate_payload
from run_scheduled_collection import identity,NoRedirect,AUDIENCE

SOURCE_PATH='/v1/contratacoes/proposta'
SOURCE_CONCURRENCY=5
SOURCE_START_INTERVAL=2.0


class BufferedResponse(io.BytesIO):
    def __init__(self,body,status,headers):
        super().__init__(body);self.status=status;self.headers=headers


def validate_plan(plan):
    if not isinstance(plan,dict) or plan.get('path')!=SOURCE_PATH:raise ValueError('Unexpected source plan')
    expected={'dataFinal':'99991231','pagina':plan.get('page'),'tamanhoPagina':50}
    if plan.get('query')!=expected or type(plan.get('page')) is not int or plan['page']<1:
        raise ValueError('Restricted national source plan')
    return plan


class Receiver:
    def __init__(self,*,timeout_seconds=90):
        if not 20<=timeout_seconds<=235:raise ValueError('Invalid receiver timeout')
        self.opener=build_opener(NoRedirect());self.timeout_seconds=timeout_seconds
        self._token=None;self._token_until=0
        self.connection=None
    def open(self,request,timeout):
        if os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy'):
            return self.opener.open(request,timeout=timeout)
        parsed=urlsplit(request.full_url)
        if parsed.scheme!='https' or request.full_url!=AUDIENCE:
            raise ValueError('Unexpected receiver destination')
        if self.connection is None:
            self.connection=http.client.HTTPSConnection(parsed.netloc,timeout=timeout,context=ssl.create_default_context())
        try:
            self.connection.request('POST',parsed.path,body=request.data,headers=dict(request.header_items()))
            response=self.connection.getresponse()
            body=response.read(4_000_001);status=response.status;headers=response.headers
            response.close()
            if len(body)>4_000_000:raise ValueError('Receiver response exceeds transport budget')
            if status>=300:raise HTTPError(request.full_url,status,'Receiver response',headers,io.BytesIO(body))
            return BufferedResponse(body,status,headers)
        except HTTPError:
            raise
        except (http.client.HTTPException,OSError):
            self.close()
            raise URLError('Receiver connection interrupted') from None
    def close(self):
        if self.connection is not None:
            self.connection.close();self.connection=None
    def post(self,body):
        refreshed=False
        for attempt in range(4):
            started=time.monotonic();identity_ms=0
            if not self._token or time.monotonic()>=self._token_until:
                self._token=identity(self.opener)
                self._token_until=time.monotonic()+60
                identity_ms=round((time.monotonic()-started)*1000)
            request=Request(AUDIENCE,data=json.dumps(body,ensure_ascii=False).encode(),method='POST',
                            headers={'Authorization':'Bearer '+self._token,'Content-Type':'application/json'})
            try:
                upload_started=time.monotonic()
                with self.open(request,timeout=self.timeout_seconds) as response:result=json.load(response)
                request_ms=round((time.monotonic()-upload_started)*1000)
                if identity_ms+request_ms>=3000:
                    print(json.dumps({'event':'national_transport_timing','page':body.get('page'),
                                      'identityMs':identity_ms,'requestMs':request_ms,
                                      'proxyConfigured':bool(os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy'))}),flush=True)
                return result
            except HTTPError as exc:
                if exc.code in (401,403) and not refreshed:
                    self._token=None;refreshed=True;continue
                if exc.code==409:return self.post({'action':'national_plan','executionId':body.get('executionId')})
                if exc.code not in (429,500,502,503,504):raise
                if attempt==3:raise
            except (URLError,TimeoutError):
                if attempt==3:raise
            time.sleep(min(2**(attempt+1),15))
        raise ValueError('National receiver unavailable')


class Source:
    def __init__(self):
        self.lock=threading.Lock();self.last_started=0;self.local=threading.local()
        self.context=ssl.create_default_context();self.timings={}
    def open(self,request,timeout):
        parsed=urlsplit(request.full_url)
        if parsed.scheme!='https' or parsed.netloc!='pncp.gov.br' or parsed.path!='/api/consulta'+SOURCE_PATH:
            raise ValueError('Unexpected source destination')
        # Honour a configured proxy instead of bypassing the runner's network policy.
        if os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy'):
            from urllib.request import urlopen
            return urlopen(request,timeout=timeout)
        connection=getattr(self.local,'connection',None)
        if connection is None:
            connection=http.client.HTTPSConnection('pncp.gov.br',timeout=timeout,context=self.context)
            self.local.connection=connection
        try:
            connection.request('GET',parsed.path+'?'+parsed.query,headers={
                'Accept':'application/json','Accept-Encoding':'gzip','Connection':'keep-alive',
                'User-Agent':'NexoRadar/1.0 (public procurement collection)'})
            response=connection.getresponse();headers=response.headers;status=response.status
            body=response.read(4_000_001)
            if len(body)>4_000_000:raise ValueError('Source page exceeds transport budget')
            if headers.get('Content-Encoding','').lower()=='gzip':
                with gzip.GzipFile(fileobj=io.BytesIO(body)) as stream:body=stream.read(4_000_001)
                if len(body)>4_000_000:raise ValueError('Source page exceeds transport budget')
            response.close()
            if status>=400:raise HTTPError(request.full_url,status,'PNCP response',headers,io.BytesIO(body))
            return BufferedResponse(body,status,headers)
        except http.client.HTTPException:
            connection.close();self.local.connection=None
            raise URLError('PNCP connection interrupted') from None
        except Exception:
            connection.close();self.local.connection=None
            raise
    def fetch(self,page):
        with self.lock:
            delay=SOURCE_START_INTERVAL-(time.monotonic()-self.last_started)
            if delay>0:time.sleep(delay)
            self.last_started=time.monotonic()
        metrics=CollectionMetrics()
        started=time.monotonic()
        result=PNCPClient(timeout_seconds=60,retries=0,pause_seconds=0,opener=self.open).get_page(SOURCE_PATH,
                    {'dataFinal':'99991231','pagina':page,'tamanhoPagina':50},modality=0,page=page,metrics=metrics)
        self.timings[page]=round((time.monotonic()-started)*1000)
        return result


def write_summary(progress,complete):
    data={'event':'national_complete' if complete else 'national_incomplete','coverageComplete':complete,
          **{key:progress.get(key) for key in ('executionId','recordsReceived','uniqueRecords','expectedRecords','expectedPages','pages','passNumber','error')}}
    print(json.dumps(data),flush=True)
    if not complete:print('::warning title=Varredura nacional incompleta::Todas as páginas ainda não foram confirmadas. O progresso está salvo e será retomado.',flush=True)
    path=os.environ.get('GITHUB_STEP_SUMMARY')
    if path:
        from pathlib import Path
        with Path(path).open('a',encoding='utf-8') as stream:
            stream.write('\n### '+('Varredura nacional concluída' if complete else 'Varredura nacional incompleta')+'\n\n')
            stream.write(f"Registros recebidos: {progress.get('recordsReceived',0)}. Total informado pelo PNCP: {progress.get('expectedRecords','a consultar')}. Páginas previstas: {progress.get('expectedPages','a consultar')}.\n\n")
            if not complete:stream.write('A cobertura não foi marcada como concluída. A próxima execução retoma o progresso salvo.\n')


def run(*,budget_seconds=3600,receiver=None,source=None):
    if type(budget_seconds) is not int or not 120<=budget_seconds<=7200:raise ValueError('Invalid national budget')
    receiver=receiver or Receiver();source=source or Source()
    started=time.monotonic();progress=receiver.post({'action':'national_plan'})
    futures={};generation=None;last_log=0
    with concurrent.futures.ThreadPoolExecutor(max_workers=SOURCE_CONCURRENCY) as pool:
        try:
            while time.monotonic()-started<budget_seconds-100:
                if progress.get('done'):
                    write_summary(progress,True);return 0
                if progress.get('busy'):
                    time.sleep(5);progress=receiver.post({'action':'national_plan'});continue
                wait_seconds=progress.get('retryAfterSeconds',0)
                if wait_seconds>0:
                    if time.monotonic()-started+wait_seconds>=budget_seconds-100:
                        write_summary(progress,False);return 2
                    time.sleep(min(wait_seconds,60))
                    progress=receiver.post({'action':'national_plan'});continue
                plan=validate_plan(progress.get('plan'))
                key=(plan['executionId'],plan['passNumber'])
                if key!=generation:
                    for future in futures.values():future.cancel()
                    futures={};generation=key
                page=plan['page']
                maximum=progress.get('expectedPages') or page
                for candidate in range(page,min(page+SOURCE_CONCURRENCY-1,max(page,maximum))+1):
                    if candidate not in futures:futures[candidate]=pool.submit(source.fetch,candidate)
                payload=None;replanned=False
                for attempt in range(5):
                    try:
                        payload=futures.pop(page).result() if page in futures else source.fetch(page)
                        validate_payload(payload,page)
                        break
                    except (PNCPError,ValueError) as exc:
                        raw_reason=str(exc) if isinstance(exc,PNCPError) else 'source_contract'
                        reason='source_5xx' if raw_reason.startswith('http_5') else 'source_contract' if raw_reason in ('resposta_nao_json','contrato_resposta_sem_lista_data') else raw_reason
                        if page>1 and reason in ('source_contract','http_400'):
                            try:
                                fresh=source.fetch(1)
                                _,_,fresh_pages=validate_payload(fresh,1)
                            except (PNCPError,ValueError):fresh_pages=None
                            if fresh_pages is not None and fresh_pages<page:
                                progress=receiver.post({'action':'national_reconcile','executionId':plan['executionId'],
                                         'passNumber':plan['passNumber'],'page':page,'payload':fresh})
                                replanned=True;break
                        if reason not in ('timeout','erro_transporte','http_429','resposta_html_waf','source_contract','source_5xx'):
                            raise
                        delay=max(60 if reason=='http_429' else min(10*2**attempt,120),getattr(exc,'retry_after_seconds',None) or 0)
                        failure={'action':'national_failure','executionId':plan['executionId'],
                                 'passNumber':plan['passNumber'],'page':page,'reason':reason,
                                 'retryAfterSeconds':min(86400,max(0,int(delay)))}
                        if reason=='http_429':
                            # Do not replay prefetched rate-limit failures one
                            # by one after the same source-wide cooldown.
                            for future in futures.values():future.cancel()
                            futures={}
                            progress=receiver.post(failure)
                        if attempt==4 or time.monotonic()-started>=budget_seconds-180:
                            if reason!='http_429':progress=receiver.post(failure)
                            write_summary(progress,False);return 2
                        print(json.dumps({'event':'national_source_retry','page':page,'reason':reason,'waitSeconds':delay}),flush=True)
                        time.sleep(delay)
                if replanned:continue
                progress=receiver.post({'action':'national_commit','executionId':plan['executionId'],
                          'passNumber':plan['passNumber'],'page':page,'payload':payload,
                          'sourceMs':getattr(source,'timings',{}).get(page)})
                if progress.get('done') or time.monotonic()-last_log>=30:
                    print(json.dumps({key:value for key,value in progress.items() if key!='plan'}),flush=True);last_log=time.monotonic()
            write_summary(progress,False)
            return 2
        finally:
            for future in futures.values():future.cancel()
            if hasattr(receiver,'close'):receiver.close()


def run_with_resume(*, budget_seconds=5400):
    """Resume bounded incomplete attempts in the same authenticated job."""
    attempts = 1 if budget_seconds == 120 else 3
    for attempt in range(1, attempts + 1):
        result = run(budget_seconds=budget_seconds)
        if result != 2:
            return result
        if attempt < attempts:
            print(json.dumps({'event':'national_resume_pending','attempt':attempt,
                              'nextAttempt':attempt+1,'waitSeconds':60}),flush=True)
            time.sleep(60)
    return 2


if __name__=='__main__':
    try:raise SystemExit(run_with_resume(budget_seconds=int(os.environ.get('RADAR_NATIONAL_BUDGET_SECONDS','5400'))))
    except Exception as exc:
        print(json.dumps({'event':'national_worker_failed','errorType':type(exc).__name__,
                          **({'sourceError':str(exc)} if isinstance(exc,PNCPError) else {})}),flush=True)
        raise SystemExit(1)
