"""Authenticated streaming encryption for database archives; no key in files."""
import base64
import os
from pathlib import Path
from cryptography.hazmat.primitives.ciphers import Cipher,algorithms,modes

MAGIC=b'NEXO-BACKUP-1\n'
CHUNK=1024*1024


def backup_key(value):
    try:key=base64.b64decode(value+'='*(-len(value)%4),altchars=b'-_',validate=True)
    except (ValueError,TypeError):raise ValueError('Backup key must be base64 encoded') from None
    if len(key)!=32:raise ValueError('Backup key must contain 32 random bytes')
    return key


def encrypt_archive(source,destination,key):
    nonce=os.urandom(12)
    encryptor=Cipher(algorithms.AES(key),modes.GCM(nonce)).encryptor()
    encryptor.authenticate_additional_data(MAGIC)
    with open(source,'rb') as incoming,open(destination,'xb') as outgoing:
        outgoing.write(MAGIC+nonce)
        while chunk:=incoming.read(CHUNK):outgoing.write(encryptor.update(chunk))
        outgoing.write(encryptor.finalize());outgoing.write(encryptor.tag)


def decrypt_archive(source,destination,key):
    created=False
    try:
        with open(source,'rb') as incoming,open(destination,'xb') as outgoing:
            created=True
            if incoming.read(len(MAGIC))!=MAGIC:raise ValueError('Invalid backup format')
            nonce=incoming.read(12);incoming.seek(-16,2);tag=incoming.read(16)
            remaining=incoming.tell()-len(MAGIC)-12-16
            if remaining<0:raise ValueError('Invalid backup size')
            incoming.seek(len(MAGIC)+12)
            decryptor=Cipher(algorithms.AES(key),modes.GCM(nonce,tag)).decryptor()
            decryptor.authenticate_additional_data(MAGIC)
            while remaining:
                chunk=incoming.read(min(CHUNK,remaining))
                if not chunk:raise ValueError('Truncated backup')
                remaining-=len(chunk);outgoing.write(decryptor.update(chunk))
            outgoing.write(decryptor.finalize())
    except Exception:
        if created:Path(destination).unlink(missing_ok=True)
        raise
