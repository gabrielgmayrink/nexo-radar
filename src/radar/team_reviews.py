"""Audited reviews with optimistic concurrency; browser-supplied actors are ignored."""
import re
from psycopg.types.json import Jsonb
from radar.learning import REASONS,object_hash
from radar.company_access import COMPANIES,AccessDenied
from radar.identifiers import parse_pncp_id

OFFERS=('', 'Public','Gerico','Ambas','Nenhuma','Revisar')
STATUSES=('Nova','Em avaliação','Vou participar','Descartada','Ganhou','Perdeu')


class ReviewConflict(ValueError):pass


def validate_review(data):
    if not isinstance(data,dict):raise ValueError('Invalid review')
    identifier=data.get('id','')
    parse_pncp_id(identifier)
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
    if not isinstance(data.get('owner',''),str) or len(data.get('owner',''))>254:raise ValueError('Invalid owner')
    checklist=data.get('checklist',[])
    if not isinstance(checklist,list) or len(checklist)>30:raise ValueError('Invalid checklist')
    ids=set()
    for item in checklist:
        if (not isinstance(item,dict) or not re.fullmatch(r'[A-Za-z0-9_-]{1,60}',str(item.get('id','')))
            or not isinstance(item.get('label'),str) or not 1<=len(item['label'])<=200 or type(item.get('done')) is not bool
            or item['id'] in ids):raise ValueError('Invalid checklist item')
        ids.add(item['id'])
    return identifier


def to_review(row):
    keys=('id','offer','status','reason','actor','version','reasonCode','expectedScope','exampleObject','sourceCurrent')
    if len(row)==13:keys+=('owner','checklist')
    return dict(zip((*keys,'updatedAt'),
                    (*row[:-1],row[-1].isoformat())))


def list_reviews(db,company='public',*,limit=200,offset=0):
    if company not in COMPANIES:raise AccessDenied()
    if type(limit) is not int or not 1<=limit<=501 or type(offset) is not int or offset<0:raise ValueError('Invalid review page')
    rows=db.execute('''select r.opportunity_id,r.offer,r.status,r.reason,r.actor,r.version,r.reason_code,r.expected_scope,r.example_object,
        coalesce((r.example_object=o.payload->>'objetoCompra' and r.example_additional=coalesce(o.payload->>'informacaoComplementar','')),false),r.owner,r.checklist,r.updated_at
        from radar_review_state r join radar_opportunities o on o.id=r.opportunity_id where r.company_id=%s
        order by r.updated_at desc,r.opportunity_id limit %s offset %s''',(company,limit,offset)).fetchall()
    return [to_review(row) for row in rows]


def save_review(db,data,actor,company='public'):
    if company not in COMPANIES:raise AccessDenied()
    identifier=validate_review(data)
    if data['offer'] not in ('',COMPANIES[company],'Nenhuma','Revisar'):raise AccessDenied()
    with db.transaction():
        # Review queues may rescue a score-zero procurement from the official
        # national collection. A browser cannot create arbitrary source rows.
        source=db.execute('select payload,content_hash from public.radar_lock_review_source(%s,%s)',
                          (identifier,COMPANIES[company])).fetchone()
        if not source:
            raise ValueError('Unknown opportunity')
        # Lock per opportunity, including the first review where no row exists yet.
        db.execute('select pg_advisory_xact_lock(hashtextextended(%s,0))',('review:'+company+':'+identifier,))
        row=db.execute('select version from radar_review_state where opportunity_id=%s and company_id=%s',(identifier,company)).fetchone()
        if (row[0] if row else 0)!=data['version']:raise ReviewConflict('Review changed')
        obj=source[0].get('objetoCompra') or ''
        additional=source[0].get('informacaoComplementar') or ''
        if data.get('sourceObject')!=obj or data.get('sourceAdditional')!=additional:
            raise ReviewConflict('Procurement object changed')
        saved=db.execute('''insert into radar_review_state(opportunity_id,offer,status,reason,actor,reason_code,expected_scope,source_content_hash,object_hash,example_object,example_additional,company_id,owner,checklist)
            values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) on conflict(opportunity_id,company_id) do update set
            offer=excluded.offer,status=excluded.status,reason=excluded.reason,actor=excluded.actor,
            version=radar_review_state.version+1,updated_at=now()
            ,reason_code=excluded.reason_code,expected_scope=excluded.expected_scope,
            source_content_hash=excluded.source_content_hash,object_hash=excluded.object_hash,
            example_object=excluded.example_object,example_additional=excluded.example_additional,
            owner=excluded.owner,checklist=excluded.checklist
            returning opportunity_id,offer,status,reason,actor,version,reason_code,expected_scope,example_object,true,owner,checklist,updated_at''',
            (identifier,data['offer'],data['status'],data['reason'],actor,data.get('reasonCode',''),data.get('expectedScope',''),
             source[1],object_hash(obj,additional),obj,additional,company,data.get('owner',''),Jsonb(data.get('checklist',[])))).fetchone()
        result=to_review(saved)
        db.execute('insert into radar_review_history(opportunity_id,actor,payload,company_id) values(%s,%s,%s,%s)',
                   (identifier,actor,Jsonb(result),company))
        return result
