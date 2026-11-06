"""Run a bounded first PNCP batch using only the new project's database."""
import json
import os
import uuid
from runtime_env import load
load()
os.environ['RADAR_SUPABASE_PROJECT_REF']='hxngkmrsthyjycxaellk'
from radar.postgres_store import PostgresStore
from radar.pncp import PNCPClient
from radar.sync import run_chunk

store=PostgresStore()
try:
    result=run_chunk(store,'incremental',run_key='initial:'+uuid.uuid4().hex,
                     client=PNCPClient(timeout_seconds=20,retries=0,pause_seconds=.6),max_pages=40,budget_seconds=90)
    count=store.db.execute('select count(*) from radar_opportunities where score>=40').fetchone()[0]
    print(json.dumps({**result,'storedCandidates':count}))
finally:store.close()
