"""Apply the owner-approved account mapping in the Nexo database only."""
import json
import os
from runtime_env import load

load()
os.environ['RADAR_SUPABASE_PROJECT_REF']='hxngkmrsthyjycxaellk'
from radar.postgres_store import PostgresStore

store=PostgresStore()
try:
    members=[('publicgerencia9@gmail.com','public'),('gericomayrink@gmail.com','gerico'),
             ('gabrielmayrink07@gmail.com','public'),('gabrielmayrink07@gmail.com','gerico')]
    with store.db.transaction(),store.db.cursor() as cursor:
        cursor.executemany('insert into radar_memberships(email,company_id) values(%s,%s) on conflict do nothing',members)
    print(json.dumps({'companyMembershipsConfigured':len(members)}))
finally:store.close()
