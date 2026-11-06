"""Lossless JSON archives, with the original content hash checked on read."""
import gzip
import hashlib
import io
import json


def encode_raw(payload):
    raw=json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()
    if len(raw)>2_000_000:raise ValueError('Raw record budget exceeded')
    return gzip.compress(raw,compresslevel=6,mtime=0)


def decode_raw(payload,compressed,content_hash):
    if (payload is None)==(compressed is None):raise ValueError('Exactly one raw representation is required')
    if compressed is not None:
        with gzip.GzipFile(fileobj=io.BytesIO(bytes(compressed))) as stream:raw=stream.read(2_000_001)
        if len(raw)>2_000_000:raise ValueError('Raw record budget exceeded')
        result=json.loads(raw)
    else:result=payload
    canonical=json.dumps(result,sort_keys=True,ensure_ascii=False).encode()
    if hashlib.sha256(canonical).hexdigest()!=content_hash:raise ValueError('Raw content hash mismatch')
    return result
