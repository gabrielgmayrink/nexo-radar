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
            rows=store.db.execute('select id,payload from radar_opportunities where id>%s order by id limit 200',(last,)).fetchall()
            if not rows:break
            values=[]
            for identifier,payload in rows:
                card=to_card(payload)
                values.append((Jsonb(card['scores']),card['ruleVersion'],card['score'],Jsonb(card) if card['score']>=40 else None,identifier))
            with store.db.transaction(),store.db.cursor() as cursor:
                cursor.executemany('update radar_opportunities set product_scores=%s,rule_version=%s,score=%s,card=%s,updated_at=now() where id=%s',values)
            updated+=len(rows);last=rows[-1][0]
        return {'reclassified':updated,'candidates':store.db.execute('select count(*) from radar_opportunities where score>=40').fetchone()[0]}
    finally:store.release();store.close()


if __name__=='__main__':
    try:print(json.dumps(run()))
    except Exception as exc:
        print(json.dumps({'errorType':type(exc).__name__}));raise SystemExit(1)
