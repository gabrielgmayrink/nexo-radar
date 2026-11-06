"""Run maintenance or a post-collection digest with the existing scoped job identity."""
import json
import os
from run_national_collection import Receiver


def run():
    action=os.environ.get('RADAR_COLLECTION_TASK')
    if action not in ('cleanup','weekly_summary'):raise ValueError('Invalid task')
    result=Receiver(timeout_seconds=235 if action=='weekly_summary' else 90).post({'action':action,'dryRun':os.environ.get('RADAR_TASK_DRY_RUN')=='1'})
    print(json.dumps({'task':action,**result}),flush=True)
    if not result.get('done'):raise ValueError('Task prerequisites not met')


if __name__=='__main__':
    try:run()
    except Exception as exc:
        print(json.dumps({'event':'collection_task_failed','errorType':type(exc).__name__}),flush=True)
        raise SystemExit(1)
