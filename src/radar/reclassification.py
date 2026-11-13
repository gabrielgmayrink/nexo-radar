"""Bounded, repeatable classification updates, including prior zero-score rows."""
from datetime import datetime,timezone
import time
from psycopg.types.json import Jsonb
from radar.canonical import to_card
from radar.learning import object_hash
from radar.profiles import profile_context
from radar.relevance import classification_version


def reclassify_batch(store,*,limit=200,deadline_seconds=30):
    if not 1<=limit<=1000 or not 1<=deadline_seconds<=120:raise ValueError('Invalid classification budget')
    if not store.acquire():return {'done':False,'reason':'collection_busy','updated':0}
    started=time.monotonic()
    try:
        with profile_context(store.db):
            version=classification_version()
            rows=store.db.execute('''select id,payload,content_hash from radar_opportunities
                where classification_version is distinct from %s order by id limit %s''',(version,limit)).fetchall()
            values=[]
            for identifier,payload,content_hash in rows:
                if values and time.monotonic()-started>=deadline_seconds:break
                card=to_card(payload)
                values.append({'id':identifier,'hash':content_hash,'card':card if card['score']>=40 else None,'scores':card['scores'],'score':card['score'],
                               'rule_version':card['ruleVersion'],'classification_version':version,
                               'object_hash':object_hash(card['object'],card['additionalInfo'])})
            with store.db.transaction():
                updated=store.db.execute('''update radar_opportunities o set card=r.card,product_scores=r.scores,
                    score=r.score,rule_version=r.rule_version,classification_version=r.classification_version,
                    object_hash=r.object_hash,updated_at=now(),
                    catalog_archived_at=case when catalog_archive_reason='outside_profile' then null else catalog_archived_at end,
                    catalog_archive_reason=case when catalog_archive_reason='outside_profile' then null else catalog_archive_reason end
                    from jsonb_to_recordset(%s::jsonb) r(id text,hash text,card jsonb,scores jsonb,score integer,
                        rule_version text,classification_version text,object_hash text)
                    where o.id=r.id and o.content_hash is not distinct from r.hash''',(Jsonb(values),)).rowcount if values else 0
                remaining=store.db.execute('select count(*) from radar_opportunities where classification_version is distinct from %s',(version,)).fetchone()[0]
                store.db.execute('''insert into radar_checkpoints(key,cursor) values('classification',%s)
                    on conflict(key) do update set cursor=excluded.cursor,updated_at=now()''',
                    (Jsonb({'version':version,'remaining':remaining,'updated':updated,'done':remaining==0,'checkedAt':datetime.now(timezone.utc).isoformat()}),))
            return {'done':remaining==0,'updated':updated,'remaining':remaining,'version':version}
    finally:store.release()
