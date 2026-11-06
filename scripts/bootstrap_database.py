"""Initialize only the newly provisioned Nexo Radar database."""
import json
import os
from pathlib import Path
from urllib.parse import urlparse
from runtime_env import load

load()
EXPECTED='hxngkmrsthyjycxaellk'
if urlparse(os.environ.get('SUPABASE_URL','')).hostname!=EXPECTED+'.supabase.co':raise SystemExit('Unexpected database; no changes made')
os.environ['RADAR_SUPABASE_PROJECT_REF']=EXPECTED

import psycopg
from radar.postgres_store import connection_string


def initialize():
    root=Path(__file__).resolve().parents[1]
    versions=[path for path in sorted((root/'migrations').glob('*.sql'))]
    applied=[]
    with psycopg.connect(connection_string(),autocommit=True) as db:
        with db.transaction():
            db.execute('select pg_advisory_xact_lock(%s)',(739241663,))
            db.execute('create table if not exists public.radar_schema_migrations(version text primary key, applied_at timestamptz not null default now())')
            for path in versions:
                if db.execute('select 1 from public.radar_schema_migrations where version=%s',(path.stem,)).fetchone():continue
                if path.stem.startswith('001') and db.execute("select to_regclass('public.radar_opportunities')").fetchone()[0]:
                    raise ValueError('Existing application tables without migration history')
                sql='\n'.join(line for line in path.read_text(encoding='utf-8').splitlines() if line.strip().lower() not in ('begin;','commit;'))
                db.execute(sql,prepare=False)
                db.execute('insert into public.radar_schema_migrations(version) values(%s)',(path.stem,))
                applied.append(path.stem)
            db.execute('alter table public.radar_schema_migrations enable row level security')
            db.execute('revoke all on public.radar_schema_migrations from anon,authenticated')
    return {'projectRef':EXPECTED,'applied':applied}

if __name__=='__main__':
    try:print(json.dumps(initialize()))
    except Exception as exc:
        print(json.dumps({'status':'failed','errorType':type(exc).__name__}))
        raise SystemExit(1)
