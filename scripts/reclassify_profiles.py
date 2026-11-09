"""Recalculate derived matches only, preserving the original public records."""
import json
import os
import sys
from runtime_env import load

load()
os.environ['RADAR_SUPABASE_PROJECT_REF']='hxngkmrsthyjycxaellk'
from psycopg.types.json import Jsonb
from radar.postgres_store import PostgresStore,LOCK_ID
from radar.canonical import to_card
from radar.relevance import VERSION


def derived_update(identifier, payload, content_hash):
    card=to_card(payload)
    return {'id':identifier,'content_hash':content_hash,'product_scores':card['scores'],
            'rule_version':card['ruleVersion'],'score':card['score'],
            'card':card if card['score']>=40 else None}


UPDATE_DERIVED='''update radar_opportunities as o set
    product_scores=r.product_scores,rule_version=r.rule_version,score=r.score,
    card=r.card,updated_at=now(),
    catalog_archived_at=case when o.catalog_archive_reason='outside_profile' and r.score>=40
        then null else o.catalog_archived_at end,
    catalog_archive_reason=case when o.catalog_archive_reason='outside_profile' and r.score>=40
        then null else o.catalog_archive_reason end
    from jsonb_to_recordset(%s::jsonb) as r(id text,content_hash text,product_scores jsonb,
        rule_version text,score integer,card jsonb)
    where o.id=r.id and o.content_hash is not distinct from r.content_hash'''


def run():
    store=PostgresStore()
    try:
        if '--wait' in sys.argv:
            store.db.execute("set statement_timeout='220s'")
            store.db.execute("set lock_timeout='210s'")
            store.db.execute('select pg_advisory_lock(%s)',(LOCK_ID,))
        elif not store.acquire():return {'busy':True}
        updated=0;last=''
        while True:
            rows=store.db.execute('''select id,payload,content_hash from radar_opportunities
                where id>%s and rule_version is distinct from %s order by id limit 500''',(last,VERSION)).fetchall()
            if not rows:break
            values=[derived_update(*row) for row in rows]
            with store.db.transaction():
                updated+=store.db.execute(UPDATE_DERIVED,(Jsonb(values),)).rowcount
            last=rows[-1][0]
        return {'reclassified':updated,'ruleVersion':VERSION,
                'remaining':store.db.execute('select count(*) from radar_opportunities where rule_version is distinct from %s',(VERSION,)).fetchone()[0],
                'candidates':store.db.execute('select count(*) from radar_national_candidates where score>=40').fetchone()[0]}
    finally:store.release();store.close()


if __name__=='__main__':
    try:print(json.dumps(run()))
    except Exception as exc:
        print(json.dumps({'errorType':type(exc).__name__}));raise SystemExit(1)
