"""Initialize an empty disposable test database; never accepts remote or existing app data."""
import os
from pathlib import Path
import psycopg


def main():
    dsn=os.environ.get('RADAR_TEST_POSTGRES_DSN','')
    options=psycopg.conninfo.conninfo_to_dict(dsn)
    if options.get('host') not in ('localhost','127.0.0.1') or not options.get('dbname','').startswith('radar_restore_test_'):
        raise ValueError('Disposable loopback database required')
    with psycopg.connect(dsn,autocommit=True,connect_timeout=5) as db:
        if db.execute("select to_regclass('public.radar_opportunities')").fetchone()[0]:raise ValueError('Test database must be empty')
        for name in ('anon','authenticated','service_role'):
            if not db.execute('select 1 from pg_roles where rolname=%s',(name,)).fetchone():db.execute('create role '+name+' nologin')
        db.execute('create schema auth;create table auth.users(id uuid primary key,email text,encrypted_password text,banned_until timestamptz);create table auth.mfa_factors(user_id uuid,status text)',prepare=False)
        for file in sorted(Path(__file__).resolve().parents[1].joinpath('migrations').glob('*.sql')):
            db.execute(file.read_text(encoding='utf-8-sig'),prepare=False)
    print('Disposable PostgreSQL initialized; all migrations applied')


if __name__=='__main__':main()
