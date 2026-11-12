"""Read-only cloud snapshot -> encrypted private upload -> empty local restore.

Production additionally requires the explicit production wrapper and dedicated
read-only login. Hashes
are computed under the same exported snapshot used by pg_dump, so a collector may
continue writing without invalidating the comparison. No source rows are changed.
"""
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import urlparse
import psycopg
from psycopg import sql
from radar.backup import backup_key,encrypt_archive,decrypt_archive
from radar.postgres_store import connection_string
from backup_database import pg_environment,run_pg
from backup_blob import PrivateBlob,upload_archive


def validate_source(reference,url,*,production=False):
    if not re.fullmatch(r'[a-z0-9]{20}',reference or '') or reference=='hxngkmrsthyjycxaellk' and not production:
        raise ValueError('Non-production project required')
    parsed=urlparse(url)
    if production and (reference!='hxngkmrsthyjycxaellk' or (parsed.username or '').split('.')[0]!='nexo_backup_login'):
        raise ValueError('Dedicated production backup login required')
    if reference not in (parsed.username or '') and reference not in (parsed.hostname or ''):
        raise ValueError('Backup source project mismatch')


def fingerprints(db,tables):
    result={}
    db.execute("set timezone='UTC'")
    for schema,table in tables:
        # Aggregate fixed-size row digests instead of materializing all row text.
        result[schema+'.'+table]=db.execute(sql.SQL('''select count(*),
          md5(coalesce(string_agg(row_hash,'' order by row_hash),'')) from
          (select md5(to_jsonb(t)::text) as row_hash from {}.{} t) rows''').format(
              sql.Identifier(schema),sql.Identifier(table))).fetchone()
    return result


def main(*,production=False):
    reference=os.environ.get('RADAR_SUPABASE_PROJECT_REF','')
    source_url=os.environ.get('POSTGRES_URL_NON_POOLING','')
    validate_source(reference,source_url,production=production)
    restore_url=os.environ.get('RADAR_RESTORE_TEST_URL','')
    parsed=urlparse(restore_url)
    if parsed.hostname not in ('localhost','127.0.0.1') or not parsed.path[1:].startswith('radar_restore_test_'):
        raise ValueError('Disposable local restore target required')
    key=backup_key(os.environ.get('RADAR_BACKUP_ENCRYPTION_KEY',''))
    storage=PrivateBlob()
    root=Path(os.environ.get('RADAR_BACKUP_WORK_ROOT',tempfile.gettempdir())).resolve()
    print(json.dumps({'event':'staging_backup_snapshot_started'}),flush=True)
    with tempfile.TemporaryDirectory(prefix='nexo-stage-backup-',dir=root) as temporary:
        folder=Path(temporary);plain=folder/'source.dump';archive=folder/'database.nexo-backup'
        downloaded=folder/'download.nexo-backup';restored=folder/'restore.dump'
        with psycopg.connect(connection_string(),autocommit=True) as source:
            source.execute("set statement_timeout='120s'")
            tables=source.execute("""select schemaname,tablename from pg_tables where
              schemaname not in ('pg_catalog','information_schema') and schemaname not like 'pg_toast%%'
              order by 1,2""").fetchall()
            roles=[r[0] for r in source.execute("select rolname from pg_roles where rolname not like 'pg_%%'").fetchall()]
            with source.transaction():
                source.execute('set transaction isolation level repeatable read read only')
                snapshot=source.execute('select pg_export_snapshot()').fetchone()[0]
                expected=fingerprints(source,tables)
                print(json.dumps({'event':'staging_backup_dump_started','tables':len(tables)}),flush=True)
                run_pg(['pg_dump','--format=custom','--no-owner','--no-acl','--snapshot',snapshot,'--file',str(plain)],pg_environment(source_url))
        encrypt_archive(plain,archive,key);plain.unlink()
        print(json.dumps({'event':'staging_backup_encrypted','bytes':archive.stat().st_size}),flush=True)
        uploaded=upload_archive(archive,storage=storage,retention_days=7)
        print(json.dumps({'event':'staging_backup_private_upload_verified'}),flush=True)
        storage.download(uploaded['url'],downloaded)
        decrypt_archive(downloaded,restored,key)
        local_options=pg_environment(restore_url,local=True)
        with psycopg.connect(restore_url,autocommit=True) as destination:
            if not destination.execute('select rolsuper from pg_roles where rolname=current_user').fetchone()[0]:
                raise ValueError('Compatible local restore administrator required')
            existing=destination.execute("""select count(*) from pg_tables where
              schemaname not in ('pg_catalog','information_schema')""").fetchone()[0]
            if existing:raise ValueError('Restore target is not empty')
            # Policy names may reference provider roles; these never receive passwords.
            for role in roles:
                if not destination.execute('select 1 from pg_roles where rolname=%s',(role,)).fetchone():
                    destination.execute(sql.SQL('create role {} nologin').format(sql.Identifier(role)))
        print(json.dumps({'event':'staging_backup_restore_started'}),flush=True)
        run_pg(['pg_restore','--exit-on-error','--no-owner','--no-acl','--dbname',local_options['PGDATABASE'],str(restored)],local_options)
        with psycopg.connect(restore_url,autocommit=True) as destination:actual=fingerprints(destination,tables)
        if actual!=expected:raise ValueError('Restored table fingerprints differ')
        result={'checkedAt':datetime.now(timezone.utc).isoformat(),'sourceProject':reference,
                'readOnlySource':True,'tables':len(expected),'rows':sum(v[0] for v in expected.values()),
                'privateExternalUpload':True,'downloadVerified':True,'restoreValidated':True,
                'archiveSha256':uploaded['sha256'],'archiveBytes':uploaded['bytes'],
                'sourceSnapshotConsistent':True,'productionChanges':0}
        report=Path(os.environ.get('RADAR_BACKUP_PROOF_PATH','backup-proof.json'))
        report.write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(result))


if __name__=='__main__':
    try:main()
    except Exception as exc:
        print(json.dumps({'event':'staging_backup_validation_failed','errorType':type(exc).__name__}));raise SystemExit(1)
