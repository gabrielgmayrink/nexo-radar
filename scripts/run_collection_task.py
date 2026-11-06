"""Run maintenance or a post-collection digest with the existing scoped job identity."""
import json
import os
import time
from run_national_collection import Receiver


def run():
    action=os.environ.get('RADAR_COLLECTION_TASK')
    if action not in ('cleanup','weekly_summary'):raise ValueError('Invalid task')
    receiver=Receiver(timeout_seconds=235 if action=='weekly_summary' else 90)
    started=time.monotonic()
    while True:
        result=receiver.post({'action':action,'dryRun':os.environ.get('RADAR_TASK_DRY_RUN')=='1'})
        print(json.dumps({'task':action,**result}),flush=True)
        if result.get('done'):return
        if action!='cleanup' or not result.get('continue'):raise ValueError('Task prerequisites not met')
        if time.monotonic()-started>240:raise ValueError('Task progress saved; continuation required')


if __name__=='__main__':
    try:run()
    except Exception as exc:
        print(json.dumps({'event':'collection_task_failed','errorType':type(exc).__name__,
                          **({'httpStatus':exc.code} if hasattr(exc,'code') else {})}),flush=True)
        raise SystemExit(1)
