"""Audited reviews with optimistic concurrency; browser-supplied actors are ignored."""
import re
from psycopg.types.json import Jsonb
from radar.learning import REASONS,object_hash

OFFERS=('', 'Public','Gerico','Ambas','Nenhuma','Revisar')
STATUSES=('Nova','Em avaliação','Vou participar','Descartada','Ganhou','Perdeu')


class ReviewConflict(ValueError):pass


def validate_review(data):
    if not isinstance(data,dict):raise ValueError('Invalid review')
    identifier=data.get('id','')
    if not isinstance(identifier,str) or not re.fullmatch(r'\d{14}-1-\d{6}/\d{4}',identifier):
        raise ValueError('Invalid opportunity')
    if data.get('offer') not in OFFERS or data.get('status') not in STATUSES:
        raise ValueError('Invalid review option')
    if not isinstance(data.get('reason'),str) or len(data['reason'])>2000:
        raise ValueError('Invalid reason')
    if type(data.get('version')) is not int or not 0<=data['version']<2**31-1:
        raise ValueError('Invalid version')
    if data.get('reasonCode','') not in REASONS or not isinstance(data.get('expectedScope',''),str) or len(data.get('expectedScope',''))>500:
        raise ValueError('Invalid learning context')
    if data.get('offer')=='Nenhuma' and (not data.get('reasonCode') or data['reasonCode']=='aderente'):
        raise ValueError('A rejection reason is required')
    return identifier


def to_review(row):
    return dict(zip(('id','offer','status','reason','actor','version','reasonCode','expectedScope','exampleObject','sourceCurrent','updatedAt'),
                    (*row[:-1],row[-1].isoformat())))


def list_reviews(db):
    rows=db.execute('''select r.opportunity_id,r.offer,r.status,r.reason,r.actor,r.version,r.reason_code,r.expected_scope,r.example_object,
        coalesce((r.example_object=o.payload->>'objetoCompra' and r.example_additional=coalesce(o.payload->>'informacaoComplementar','')),false),r.updated_at
        from radar_review_state r join radar_opportunities o on o.id=r.opportunity_id order by r.updated_at desc limit 1001''').fetchall()
    if len(rows)>1000:raise ValueError('Review export limit reached')
    return [to_review(row) for row in rows]


def save_review(db,data,actor):
    identifier=validate_review(data)
    with db.transaction():
        source=db.execute('select payload,content_hash from radar_opportunities where id=%s for share',(identifier,)).fetchone()
        if not source:
            raise ValueError('Unknown opportunity')
        # Lock per opportunity, including the first review where no row exists yet.
        db.execute('select pg_advisory_xact_lock(hashtextextended(%s,0))',('review:'+identifier,))
        row=db.execute('select version from radar_review_state where opportunity_id=%s',(identifier,)).fetchone()
        if (row[0] if row else 0)!=data['version']:raise ReviewConflict('Review changed')
        obj=source[0].get('objetoCompra') or ''
        additional=source[0].get('informacaoComplementar') or ''
        if data.get('sourceObject')!=obj or data.get('sourceAdditional')!=additional:
            raise ReviewConflict('Procurement object changed')
        saved=db.execute('''insert into radar_review_state(opportunity_id,offer,status,reason,actor,reason_code,expected_scope,source_content_hash,object_hash,example_object,example_additional)
            values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) on conflict(opportunity_id) do update set
            offer=excluded.offer,status=excluded.status,reason=excluded.reason,actor=excluded.actor,
            version=radar_review_state.version+1,updated_at=now()
            ,reason_code=excluded.reason_code,expected_scope=excluded.expected_scope,
            source_content_hash=excluded.source_content_hash,object_hash=excluded.object_hash,
            example_object=excluded.example_object,example_additional=excluded.example_additional
            returning opportunity_id,offer,status,reason,actor,version,reason_code,expected_scope,example_object,true,updated_at''',
            (identifier,data['offer'],data['status'],data['reason'],actor,data.get('reasonCode',''),data.get('expectedScope',''),
             source[1],object_hash(obj,additional),obj,additional)).fetchone()
        result=to_review(saved)
        db.execute('insert into radar_review_history(opportunity_id,actor,payload) values(%s,%s,%s)',
                   (identifier,actor,Jsonb(result)))
        return result
