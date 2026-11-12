"""Owner-run encrypted backup/isolated restore. Never loads dotenv or prints URLs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from urllib.parse import parse_qs,urlparse,unquote
from radar.backup import backup_key,encrypt_archive,decrypt_archive
from radar.database_tls import tls_parameters

ROOT=Path(__file__).resolve().parents[1]


def pg_environment(value,*,local=False):
    parsed=urlparse(value)
    if parsed.scheme not in ('postgres','postgresql') or not parsed.hostname or not parsed.path.strip('/'):
        raise ValueError('A database URL is required through the named environment variable')
    if local and (parsed.hostname not in ('localhost','127.0.0.1','::1') or not parsed.path[1:].startswith('radar_restore_test_')):
        raise ValueError('Restore is restricted to a local radar_restore_test_* database')
    env=os.environ.copy()
    env.update(PGHOST=parsed.hostname,PGPORT=str(parsed.port or 5432),PGDATABASE=unquote(parsed.path[1:]),
               PGUSER=unquote(parsed.username or ''),PGPASSWORD=unquote(parsed.password or ''))
    if local:env['PGSSLMODE']='disable'
    else:
        query={key:values[0] for key,values in parse_qs(parsed.query).items()}
        secure=tls_parameters(query)
        env.update(PGSSLMODE=secure['sslmode'],PGSSLROOTCERT=secure['sslrootcert'])
    return env


def run_pg(command,env):
    # Suppress provider diagnostics that may contain connection details. An
    # owner can reproduce locally using their protected terminal if necessary.
    result=subprocess.run(command,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=3600)
    if result.returncode:raise RuntimeError('PostgreSQL utility failed (exit '+str(result.returncode)+')')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('backup','validate','restore-test'))
    parser.add_argument('--archive',required=True,type=Path)
    parser.add_argument('--database-url-env',default='POSTGRES_URL_NON_POOLING')
    parser.add_argument('--allow-test-restore',action='store_true')
    args=parser.parse_args()
    archive=args.archive.resolve()
    if not args.archive.is_absolute() or archive.is_relative_to(ROOT):
        raise ValueError('Use an absolute archive path outside the Git checkout')
    key=backup_key(os.environ.get('RADAR_BACKUP_ENCRYPTION_KEY',''))
    archive.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='nexo-backup-',dir=archive.parent) as temporary:
        plain=Path(temporary)/'database.dump'
        if args.action=='backup':
            env=pg_environment(os.environ.get(args.database_url_env,''))
            run_pg(['pg_dump','--format=custom','--no-owner','--no-acl','--file',str(plain)],env)
            encrypt_archive(plain,archive,key)
        else:
            decrypt_archive(archive,plain,key)
            run_pg(['pg_restore','--list',str(plain)],os.environ.copy())
            if args.action=='restore-test':
                if not args.allow_test_restore:raise ValueError('Explicit --allow-test-restore is required')
                env=pg_environment(os.environ.get(args.database_url_env,''),local=True)
                run_pg(['pg_restore','--exit-on-error','--no-owner','--no-acl','--dbname',env['PGDATABASE'],str(plain)],env)
                run_pg(['psql','--no-psqlrc','--set','ON_ERROR_STOP=1','--command',
                        'select count(*) from public.radar_opportunities; select count(*) from public.radar_review_state;'],env)
    with open(archive,'rb') as encrypted:checksum=hashlib.file_digest(encrypted,'sha256').hexdigest()
    print(json.dumps({'event':'backup_'+args.action+'_complete','sha256':checksum,'bytes':archive.stat().st_size}))


if __name__=='__main__':
    try:main()
    except (ValueError,RuntimeError,OSError,subprocess.TimeoutExpired) as exc:
        print(json.dumps({'event':'backup_failed','errorType':type(exc).__name__}))
        raise SystemExit(1)
