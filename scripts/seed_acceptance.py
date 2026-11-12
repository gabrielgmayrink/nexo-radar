"""Seed explicit QA identities and public snapshots into a disposable local database only."""
import json
import os
from pathlib import Path
import uuid
import psycopg
from radar.postgres_store import PostgresStore


def main():
    dsn=os.environ.get('RADAR_TEST_POSTGRES_DSN','');options=psycopg.conninfo.conninfo_to_dict(dsn)
    if options.get('host') not in ('127.0.0.1','localhost') or not options.get('dbname','').startswith('radar_restore_test_'):raise ValueError('Disposable local database required')
    with psycopg.connect(dsn,autocommit=True,connect_timeout=5) as db:
        for email,company in [('public.qa@example.com','public'),('gerico.qa@example.com','gerico'),('admin.qa@example.com','public'),('admin.qa@example.com','gerico')]:
            identifier=str(uuid.uuid5(uuid.NAMESPACE_DNS,email))
            db.execute('insert into auth.users(id,email,encrypted_password) values(%s,%s,%s) on conflict do nothing',(identifier,email,'local-qa-only'))
            db.execute("insert into radar_memberships(email,company_id,role) values(%s,%s,'owner') on conflict do nothing",(email,company))
        rows=json.loads(Path(__file__).resolve().parents[1].joinpath('tests/fixtures/public_acceptance_samples.json').read_text(encoding='utf8'))['records']
        PostgresStore(db).write_records(rows)
    print(json.dumps({'environment':'disposable_local_only','publicSamples':len(rows),'syntheticAuth':True,'externalMessages':0}))


if __name__=='__main__':main()
