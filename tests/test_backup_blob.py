import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock
from datetime import datetime,timezone
from radar.backup import MAGIC
from scripts.backup_blob import PrivateBlob,upload_archive,eligible_expired,PREFIX

TEMP_ROOT=Path(__file__).resolve().parents[1]/'.local'
TEMP_ROOT.mkdir(exist_ok=True)


class FakeStorage:
    def __init__(self,*,size=0,corrupt=False):
        self.blobs=([{'pathname':'foreign-file','size':size}] if size else [])
        self.content=b'';self.calls=[];self.corrupt=corrupt
    def listing(self):return self.blobs
    def execute(self,args):
        self.calls.append(args)
        if args[0]=='put':
            self.content=Path(args[1]).read_bytes();key=args[args.index('--pathname')+1]
            self.blobs.append({'pathname':key,'size':len(self.content),'url':'https://fixture.private.blob.vercel-storage.com/'+key,'uploadedAt':'2026-11-12T00:00:00Z'})
    def download(self,url,target):target.write_bytes(self.content+(b'tampered' if self.corrupt else b''))


class BlobBackupTests(unittest.TestCase):
    def test_plaintext_and_byte_budget_are_rejected_before_upload(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as root:
            path=Path(root)/'backup.nexo-backup';storage=FakeStorage(size=1024)
            path.write_bytes(b'plaintext')
            with self.assertRaises(ValueError):upload_archive(path,storage=storage)
            path.write_bytes(MAGIC+b'ciphertext')
            with self.assertRaisesRegex(ValueError,'budget'):upload_archive(path,storage=storage,max_stored_bytes=1024)
            self.assertEqual(storage.calls,[])

    def test_uploaded_archive_is_downloaded_and_checksum_verified(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as root:
            path=Path(root)/'backup.nexo-backup';path.write_bytes(MAGIC+b'ciphertext')
            result=upload_archive(path,storage=FakeStorage())
            self.assertTrue(result['downloadVerified']);self.assertEqual(result['pruned'],0)
            with self.assertRaisesRegex(ValueError,'checksum'):
                upload_archive(path,storage=FakeStorage(corrupt=True))

    def test_retention_keeps_two_newest_and_never_claims_foreign_files(self):
        rows=[{'pathname':PREFIX+str(i)*64+'.nexo-backup','uploadedAt':'2026-10-0'+str(i)+'T00:00:00Z'} for i in range(1,5)]
        rows.append({'pathname':'other-system.nexo-backup','uploadedAt':'2020-01-01T00:00:00Z'})
        result=eligible_expired(rows,7,now=datetime(2026,11,12,tzinfo=timezone.utc))
        self.assertEqual({b['pathname'] for b in result},{rows[0]['pathname'],rows[1]['pathname']})
        with self.assertRaises(ValueError):eligible_expired(rows,0)

    def test_destination_must_be_the_dedicated_private_store(self):
        store=PrivateBlob(environ={'RADAR_BACKUP_BLOB_STORE_ID':'store_fixture','BLOB_READ_WRITE_TOKEN':'test-only'})
        for url in ('http://fixture.private.blob.vercel-storage.com/x','https://fixture.public.blob.vercel-storage.com/x',
                    'https://fixture.private.blob.vercel-storage.com:8443/x','https://elsewhere.example/x'):
            with self.subTest(url=url),self.assertRaises(ValueError):store.url(url)

    def test_repeated_cursor_cannot_silently_truncate_storage_inventory(self):
        runner=Mock(return_value=subprocess.CompletedProcess([],0,json.dumps({'blobs':[],'hasMore':True,'cursor':'repeat'}),''))
        store=PrivateBlob(runner=runner,environ={'RADAR_BACKUP_BLOB_STORE_ID':'store_fixture','BLOB_READ_WRITE_TOKEN':'test-only'})
        with self.assertRaisesRegex(ValueError,'Incomplete'):store.listing()


if __name__=='__main__':unittest.main()
