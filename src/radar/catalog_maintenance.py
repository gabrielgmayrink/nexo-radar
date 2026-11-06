"""Remove expired/unrelated entries from the active catalog, retaining source and reviews."""
from datetime import datetime,timezone
from collections import Counter
from radar.relevance import TZ


def archive_reason(status,deadline,score,now):
    if status!=1:return 'inactive'
    if deadline:
        try:
            end=datetime.fromisoformat(deadline.replace('Z','+00:00'))
            if end.tzinfo is None:end=end.replace(tzinfo=TZ)
            if end<=now:return 'expired'
        except (ValueError,TypeError):pass  # Unknown dates are not guessed.
    if score<40:return 'outside_profile'
    return None


def cleanup(store,*,dry_run=False,now=None):
    now=now or datetime.now(timezone.utc)
    if not store.acquire():return {'done':False,'reason':'collection_busy'}
    try:
        checkpoint=store.db.execute("select cursor from radar_checkpoints where key='sync:national_open'").fetchone()
        if checkpoint and checkpoint[0].get('status')!='ok':
            return {'done':False,'reason':'collection_incomplete'}
        targets=[];last=''
        while True:
            rows=store.db.execute('''select id,payload->>'situacaoCompraId',payload->>'dataEncerramentoProposta',score
                from radar_opportunities where catalog_archived_at is null and id>%s order by id limit 1000''',(last,)).fetchall()
            if not rows:break
            for identifier,status,deadline,score in rows:
                reason=archive_reason(1 if status=='1' else 0,deadline,score,now)
                if reason:targets.append((identifier,reason))
            last=rows[-1][0]
        counts=dict(Counter(reason for _,reason in targets))
        result={'done':True,'dryRun':dry_run,'removedFromActive':len(targets),'reasons':counts,'historyPreserved':True}
        if not dry_run:
            from psycopg.types.json import Jsonb
            with store.db.transaction():
                if targets:
                    store.db.execute('''update radar_opportunities o set catalog_archived_at=%s,catalog_archive_reason=t.reason
                        from unnest(%s::text[],%s::text[]) as t(id,reason) where o.id=t.id''',
                        (now,[identifier for identifier,_ in targets],[reason for _,reason in targets]))
                store.db.execute('''insert into radar_catalog_state(id,content) values('maintenance',%s)
                    on conflict(id) do update set content=excluded.content,updated_at=now()''',
                    (Jsonb({**result,'completedAt':now.isoformat()}),))
        return result
    finally:store.release()


def weekly_ready(cursor,run_key,now):
    local=now.astimezone(TZ)
    source_run=str(cursor.get('last_run_key') or cursor.get('run_key','')).split(':')[0]
    return (local.weekday()==0 and local.hour>=7 and cursor.get('end')==local.date().isoformat()
            and cursor.get('status')=='ok' and cursor.get('coverageComplete') is True
            and source_run==run_key.split(':')[0])


def weekly_summary(store,run_key,*,dry_run=False,now=None):
    now=now or datetime.now(timezone.utc)
    if not store.acquire():return {'done':False,'reason':'collection_busy','sent':0}
    try:
        row=store.db.execute("select cursor from radar_checkpoints where key='sync:national_open'").fetchone()
        if not row or not weekly_ready(row[0],run_key,now):
            return {'done':False,'reason':'current_weekly_collection_required','sent':0}
        from radar.notifications import notify
        return {'done':True,**notify(store.db,'weekly',writer=store.write_records,dry_run=dry_run)}
    finally:store.release()
