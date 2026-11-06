"""Apply additive collection schema only to the approved Radar project."""
import json
from pathlib import Path
import psycopg
from radar.postgres_store import connection_string,prepared_record,PROJECT_REF


def migrate():
    versions=('002_durable_collection','003_compact_derived_cards','004_team_and_email','005_review_learning','006_compressed_raw')
    with psycopg.connect(connection_string(),autocommit=True) as db:
        with db.transaction():
            db.execute('select pg_advisory_xact_lock(%s)',(739241663,))
            for version in versions:
                exists=db.execute('select 1 from radar_schema_migrations where version=%s',(version,)).fetchone()
                if not exists:
                    path=Path(__file__).resolve().parents[1]/'migrations'/(version+'.sql')
                    sql='\n'.join(line for line in path.read_text(encoding='utf-8').splitlines() if line.strip().lower() not in ('begin;','commit;'))
                    db.execute(sql,prepare=False)
                    if version=='002_durable_collection':
                        rows=db.execute('select payload from radar_opportunities').fetchall()
                        for (row,) in rows:
                            values=prepared_record(row)
                            db.execute('update radar_opportunities set score=%s,card=%s,source_updated_at=%s where id=%s',
                                       (values[4],values[5],values[6],values[0]))
                    db.execute('insert into radar_schema_migrations(version) values(%s)',(version,))
            count=db.execute('select count(*) from radar_opportunities where score>=40').fetchone()[0]
            tables=('radar_catalog_state','radar_mail_outbox','radar_login_requests','radar_team_sessions','radar_review_state','radar_review_history')
            for table in tables:
                if not db.execute('select relrowsecurity from pg_class where oid=%s::regclass',(table,)).fetchone()[0]:
                    raise ValueError('RLS is required')
                for role in ('anon','authenticated'):
                    if db.execute('select has_table_privilege(%s,%s,%s)',(role,table,'SELECT')).fetchone()[0]:
                        raise ValueError('Public table access detected')
    return {'projectRef':PROJECT_REF,'migrations':versions,'candidates':count,'publicAccessDenied':True}


if __name__=='__main__':
    try:print(json.dumps(migrate()))
    except Exception as exc:
        print(json.dumps({'status':'failed','errorType':type(exc).__name__}))
        raise SystemExit(1)
