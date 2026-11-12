"""Safe health metadata for authenticated operations, without credentials or raw objects."""
from datetime import datetime, timedelta, timezone


def health_report(store):
    db, now = store.db, datetime.now(timezone.utc)
    rows = db.execute('''select source_id,name,access_state,enabled,last_success_at,last_error_code
      from radar_data_sources order by source_id''').fetchall()
    sources = [{'id': key, 'name': name, 'state': state, 'enabled': enabled,
                'lastSuccessAt': success.isoformat() if success else None, 'lastErrorCode': error}
               for key, name, state, enabled, success, error in rows]
    queues = dict(db.execute('''select j.status,count(*) from radar_enrichment_jobs j join radar_opportunities o
      on o.id=j.opportunity_id and o.content_hash=j.source_hash group by j.status''').fetchall())
    quarantine = db.execute('select count(*) from radar_quarantine where resolved_at is null').fetchone()[0]
    database_bytes=db.execute('select pg_database_size(current_database())').fetchone()[0]
    # A completed historical pass does not prove that today's capture is current.
    incremental = db.execute("select max(finished_at) from radar_executions where task='sync:incremental' and status='ok'").fetchone()[0]
    checks = [{'id': 'incremental_freshness', 'ok': bool(incremental and now - incremental < timedelta(hours=30)),
               'state': 'current' if incremental and now - incremental < timedelta(hours=30) else 'stale_or_not_started'},
              {'id': 'quarantine', 'ok': quarantine == 0, 'state': 'clear' if quarantine == 0 else 'pending_records'},
              {'id': 'enrichment', 'ok': queues.get('blocked', 0) == 0,
               'state': 'clear' if not queues.get('blocked') else 'blocked_jobs'},
              {'id':'database_capacity','ok':database_bytes<400*1024*1024,
               'state':'headroom' if database_bytes<400*1024*1024 else 'capacity_action_required'}]
    return {'health': {'ok': all(c['ok'] for c in checks), 'checkedAt': now.isoformat(), 'checks': checks},
            'sources': sources, 'queue': {'pending': queues.get('pending', 0) + queues.get('processing', 0),
                                         'retry': queues.get('retry', 0), 'blocked': queues.get('blocked', 0)},
            'quarantinedRecords': quarantine,
            'storage':{'databaseBytes':database_bytes,'warningAtBytes':400*1024*1024,'collectionStopAtBytes':450*1024*1024}}
