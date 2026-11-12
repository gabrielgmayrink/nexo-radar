"""Upload an already encrypted backup to the owner's configured private S3 destination.

Requires AWS CLI and externally provisioned credentials. No new account or cost is created.
Retention is configured with a bucket lifecycle policy; this script never deletes backups.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from urllib.parse import urlparse
from radar.backup import MAGIC


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--archive',required=True,type=Path)
    parser.add_argument('--verify-download',action='store_true');args=parser.parse_args()
    path=args.archive.resolve();bucket=os.environ.get('RADAR_BACKUP_S3_BUCKET','')
    prefix=os.environ.get('RADAR_BACKUP_S3_PREFIX','nexo-backups').strip('/')
    if not re.fullmatch(r'[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]',bucket) or not re.fullmatch(r'[A-Za-z0-9/_-]{1,150}',prefix):
        raise ValueError('Configure a private bucket and scoped prefix')
    if not path.is_file() or path.suffix!='.nexo-backup':raise ValueError('An encrypted archive is required')
    with path.open('rb') as f:
        if f.read(len(MAGIC))!=MAGIC:raise ValueError('Refusing a plaintext backup')
    with path.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
    key=prefix+'/'+digest+'.nexo-backup'
    base=['aws','--no-cli-pager']
    endpoint=os.environ.get('RADAR_BACKUP_S3_ENDPOINT','')
    if endpoint:
        parsed=urlparse(endpoint)
        if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:raise ValueError('HTTPS endpoint required')
        base+=['--endpoint-url',endpoint]
    def execute(arguments):
        result=subprocess.run(base+arguments,capture_output=True,text=True,timeout=600)
        if result.returncode:raise RuntimeError('Private storage operation failed')
        return json.loads(result.stdout or '{}')
    execute(['s3api','put-object','--bucket',bucket,'--key',key,'--body',str(path),
             '--metadata','sha256='+digest,'--server-side-encryption','AES256'])
    head=execute(['s3api','head-object','--bucket',bucket,'--key',key])
    if head.get('ContentLength')!=path.stat().st_size or head.get('Metadata',{}).get('sha256')!=digest:
        raise ValueError('Remote backup metadata mismatch')
    if args.verify_download:
        with tempfile.TemporaryDirectory(prefix='nexo-storage-verify-') as temporary:
            target=Path(temporary)/'download.nexo-backup'
            execute(['s3api','get-object','--bucket',bucket,'--key',key,str(target)])
            with target.open('rb') as f:
                if hashlib.file_digest(f,'sha256').hexdigest()!=digest:raise ValueError('Remote checksum mismatch')
    print(json.dumps({'event':'encrypted_backup_uploaded','sha256':digest,'bytes':path.stat().st_size,'downloadVerified':args.verify_download}))


if __name__=='__main__':
    try:main()
    except Exception as exc:
        print(json.dumps({'event':'backup_upload_failed','errorType':type(exc).__name__}));raise SystemExit(1)
