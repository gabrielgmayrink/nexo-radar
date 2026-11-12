"""Bounded maintenance: reapply the current profiles without altering source records."""
import argparse
import json
from runtime_env import load

def run(*,batches=1,limit=200):
    from radar.postgres_store import PostgresStore
    from radar.reclassification import reclassify_batch
    if not 1<=batches<=100 or not 1<=limit<=1000:raise ValueError('Invalid batch budget')
    store=PostgresStore();updated=0
    try:
        for _ in range(batches):
            result=reclassify_batch(store,limit=limit,deadline_seconds=20)
            updated+=result.get('updated',0)
            if result.get('done') or result.get('reason'):break
        return {**result,'updatedThisRun':updated}
    finally:store.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--batches',type=int,default=1);parser.add_argument('--limit',type=int,default=200)
    args=parser.parse_args();load()
    try:print(json.dumps(run(batches=args.batches,limit=args.limit)))
    except Exception as exc:
        print(json.dumps({'errorType':type(exc).__name__}));raise SystemExit(1)
