"""Run the same durable batches locally for a supervised initial catch-up."""
import json
import os
import time
from datetime import datetime,timezone
from radar.postgres_store import PostgresStore
from radar.pncp import PNCPClient
from radar.sync import run_chunk


def run():
    kind=os.environ.get('RADAR_LOCAL_KIND','incremental')
    if kind not in ('incremental','backfill','open'):raise ValueError('Invalid collection kind')
    store=PostgresStore()
    client=PNCPClient(timeout_seconds=45,retries=0,pause_seconds=1.5)
    run_key='supervised:'+datetime.now(timezone.utc).isoformat()
    started,execution_id,failures=time.monotonic(),None,0
    previous_errors=None
    try:
        while time.monotonic()-started<1200:
            result=run_chunk(store,kind,run_key=run_key,execution_id=execution_id,client=client,max_pages=40)
            print(json.dumps(result),flush=True)
            if result.get('done'):return 0
            if result.get('busy'):
                time.sleep(5);continue
            execution_id=result['executionId']
            errors=result.get('requestErrors',0)
            if errors>(previous_errors if previous_errors is not None else errors-int(result['status']=='partial')):
                failures+=1
            elif result['status']!='partial':failures=0
            previous_errors=errors
            if failures>=3:return 1
            if result.get('retryAfterSeconds',0)>0:
                time.sleep(min(result['retryAfterSeconds']+1,30));continue
            if failures:time.sleep(10)
        print(json.dumps({'event':'supervised_budget_reached','executionId':execution_id}),flush=True)
        return 0
    finally:store.close()


if __name__=='__main__':
    try:raise SystemExit(run())
    except Exception as exc:
        print(json.dumps({'status':'failed','errorType':type(exc).__name__}),flush=True)
        raise SystemExit(1)
