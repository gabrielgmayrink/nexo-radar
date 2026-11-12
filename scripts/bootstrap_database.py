"""Apply versioned migrations only to an explicitly selected Nexo environment."""
import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlparse
from runtime_env import load

PRODUCTION_PROJECT='hxngkmrsthyjycxaellk'

def validate_target(project_ref,*,production=False):
    import re
    if not re.fullmatch(r'[a-z0-9]{20}',project_ref):raise ValueError('Invalid project reference')
    if project_ref==PRODUCTION_PROJECT and not production:raise ValueError('Production requires explicit --production authorization')
    if urlparse(os.environ.get('SUPABASE_URL','')).hostname!=project_ref+'.supabase.co':raise ValueError('Unexpected database; no changes made')
    os.environ['RADAR_SUPABASE_PROJECT_REF']=project_ref

def initialize(project_ref):
    import psycopg
    from radar.postgres_store import connection_string,PROJECT_REF
    if PROJECT_REF!=project_ref:raise ValueError('Database module target mismatch')
    root=Path(__file__).resolve().parents[1]
    versions=[path for path in sorted((root/'migrations').glob('*.sql'))]
    applied=[]
    with psycopg.connect(connection_string(),autocommit=True) as db:
        db.execute("set lock_timeout='5s'")
        db.execute("set statement_timeout='120s'")
        with db.transaction():
            if not db.execute('select pg_try_advisory_xact_lock(%s)',(739241663,)).fetchone()[0]:raise ValueError('Collection is running; migration not started')
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
    return {'projectRef':project_ref,'applied':applied}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file',required=True,type=Path)
    parser.add_argument('--project-ref',required=True)
    parser.add_argument('--production',action='store_true',help='Only after owner approval for the exact production release')
    args=parser.parse_args()
    try:
        load(args.env_file);validate_target(args.project_ref,production=args.production)
        print(json.dumps(initialize(args.project_ref)))
    except Exception as exc:
        print(json.dumps({'status':'failed','errorType':type(exc).__name__}))
        raise SystemExit(1)
