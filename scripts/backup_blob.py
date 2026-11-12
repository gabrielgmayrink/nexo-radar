"""Encrypted archives in a dedicated private Blob store, with a hard byte budget.

The CLI receives its token through the environment, never process arguments.
Pruning is opt-in, limited to this script's immutable archive paths, and retains
at least two newer copies. Production scheduling remains a separate owner action.
"""
import argparse
from datetime import datetime,timedelta,timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from urllib.parse import urlparse
from radar.backup import MAGIC

PREFIX='nexo-encrypted-backups/'
PATH_PATTERN=re.compile(re.escape(PREFIX)+r'[0-9a-f]{64}\.nexo-backup')


def eligible_expired(blobs,retention_days,*,now=None):
    if type(retention_days) is not int or not 7<=retention_days<=365:raise ValueError('Retention must be 7–365 days')
    cutoff=(now or datetime.now(timezone.utc))-timedelta(days=retention_days)
    owned=[]
    for blob in blobs:
        if not PATH_PATTERN.fullmatch(blob.get('pathname','')):continue
        date=datetime.fromisoformat(blob['uploadedAt'].replace('Z','+00:00'))
        if date.tzinfo is None:raise ValueError('Invalid archive timestamp')
        owned.append((date,blob))
    owned.sort(key=lambda item:item[0],reverse=True)
    return [blob for date,blob in owned[2:] if date<cutoff]


class PrivateBlob:
    def __init__(self,*,runner=subprocess.run,environ=None):
        self.env=dict(os.environ if environ is None else environ)
        store=self.env.get('RADAR_BACKUP_BLOB_STORE_ID','')
        if not re.fullmatch(r'store_[A-Za-z0-9]+',store) or not self.env.get('BLOB_READ_WRITE_TOKEN'):
            raise ValueError('Dedicated private store credentials required')
        self.hostname=store.removeprefix('store_').lower()+'.private.blob.vercel-storage.com'
        # The desktop/CI may provide an unrelated deployment OIDC identity.
        self.env.pop('VERCEL_OIDC_TOKEN',None);self.env.pop('BLOB_STORE_ID',None)
        self.cli=shutil.which('vercel.cmd') or shutil.which('vercel') or 'vercel'
        self.runner=runner

    def execute(self,args):
        result=self.runner([self.cli,'blob',*args],env=self.env,capture_output=True,text=True,timeout=600)
        if result.returncode:raise RuntimeError('Private Blob operation failed')
        return result.stdout

    def url(self,value):
        parsed=urlparse(value)
        if parsed.scheme!='https' or parsed.hostname!=self.hostname or parsed.port not in (None,443) or parsed.username or parsed.query or parsed.fragment:
            raise ValueError('Unexpected private storage destination')
        return value

    def listing(self):
        blobs=[];cursor=None;seen=set()
        for _ in range(10):
            args=['list','--json','--limit','1000']+(['--next',cursor] if cursor else [])
            data=json.loads(self.execute(args))
            if not isinstance(data,dict) or not isinstance(data.get('blobs'),list):raise ValueError('Invalid storage listing')
            for blob in data['blobs']:
                self.url(blob['url'])
                if type(blob.get('size')) is not int or blob['size']<0:raise ValueError('Invalid storage size')
                blobs.append(blob)
            if not data.get('hasMore'):return blobs
            cursor=data.get('cursor')
            if not isinstance(cursor,str) or not cursor or cursor in seen:raise ValueError('Incomplete storage listing')
            seen.add(cursor)
        raise ValueError('Storage listing budget exceeded')

    def download(self,url,destination):
        self.execute(['get',self.url(url),'--access','private','--output',str(destination)])


def upload_archive(path,*,storage=None,max_stored_bytes=512*1024*1024,retention_days=7,prune=False):
    path=Path(path).resolve()
    if path.suffix!='.nexo-backup' or not path.is_file():raise ValueError('Encrypted archive required')
    with path.open('rb') as stream:
        if stream.read(len(MAGIC))!=MAGIC:raise ValueError('Plaintext upload refused')
    if not 1024<=max_stored_bytes<=512*1024*1024:raise ValueError('Invalid storage budget')
    with path.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
    key=PREFIX+digest+'.nexo-backup';storage=storage or PrivateBlob()
    blobs=storage.listing();existing=next((b for b in blobs if b['pathname']==key),None)
    if not existing:
        if sum(blob['size'] for blob in blobs)+path.stat().st_size>max_stored_bytes:
            raise ValueError('Backup storage budget exceeded; older copies preserved')
        storage.execute(['put',str(path),'--access','private','--pathname',key,'--no-multipart',
                         '--content-type','application/octet-stream','--cache-control-max-age','60'])
        blobs=storage.listing();existing=next((b for b in blobs if b['pathname']==key),None)
    if not existing or existing['size']!=path.stat().st_size:raise ValueError('Remote archive size mismatch')
    with tempfile.TemporaryDirectory(prefix='nexo-private-backup-verify-',dir=path.parent) as temporary:
        downloaded=Path(temporary)/'download.nexo-backup'
        storage.download(existing['url'],downloaded)
        with downloaded.open('rb') as stream:
            if hashlib.file_digest(stream,'sha256').hexdigest()!=digest:raise ValueError('Remote archive checksum mismatch')
    expired=eligible_expired(blobs,retention_days)
    if prune:
        for blob in expired:storage.execute(['delete',storage.url(blob['url'])])
    return {'sha256':digest,'bytes':path.stat().st_size,'downloadVerified':True,
            'url':existing['url'],'expiredCopies':len(expired),'pruned':len(expired) if prune else 0}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--archive',required=True,type=Path)
    parser.add_argument('--retention-days',type=int,default=7)
    parser.add_argument('--prune-expired',action='store_true')
    args=parser.parse_args()
    report=upload_archive(args.archive,retention_days=args.retention_days,prune=args.prune_expired)
    report.pop('url');print(json.dumps({'event':'private_blob_backup_verified',**report}))


if __name__=='__main__':
    try:main()
    except Exception as exc:
        print(json.dumps({'event':'private_blob_backup_failed','errorType':type(exc).__name__}));raise SystemExit(1)
