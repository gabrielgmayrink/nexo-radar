"""Explicit production read-only backup; restoration remains loopback-only."""
import json
import os
from verify_staging_backup import main


if __name__=='__main__':
    try:
        if os.environ.get('RADAR_PRODUCTION_BACKUP_ALLOWED')!='1':raise ValueError('Production backup authorization required')
        main(production=True)
    except Exception as exc:
        print(json.dumps({'event':'production_backup_validation_failed','errorType':type(exc).__name__}))
        raise SystemExit(1)
