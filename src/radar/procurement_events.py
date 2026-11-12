"""Official source changes; private team notes live in separate company tables."""
import hashlib
import json
from psycopg.types.json import Jsonb

FIELDS={
    'objetoCompra':'object_changed','dataAberturaProposta':'opening_changed',
    'dataEncerramentoProposta':'deadline_changed','situacaoCompraId':'status_changed',
    'valorTotalEstimado':'estimated_value_changed','modalidadeId':'modality_changed',
    'linkSistemaOrigem':'origin_link_changed',
}


def source_changes(identifier,before,after,*,source='pncp',transition_id=None):
    changes=[]
    for field,kind in FIELDS.items():
        old=before.get(field) if before else None
        new=after.get(field)
        if before is None or old==new:continue
        revision=after.get('dataAtualizacaoGlobal') or after.get('dataAtualizacao') or hashlib.sha256(json.dumps(after,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        evidence=json.dumps([identifier,field,old,new,source,revision,transition_id],sort_keys=True,ensure_ascii=False)
        changes.append({'opportunity_id':identifier,'event_key':hashlib.sha256(evidence.encode()).hexdigest(),
                        'kind':kind,'old_value':old,'new_value':new,'source':source})
    return changes


def write_events(db,events):
    if not events:return
    db.execute('''insert into radar_procurement_events(opportunity_id,event_key,kind,old_value,new_value,source)
        select opportunity_id,event_key,kind,old_value,new_value,source from jsonb_to_recordset(%s::jsonb)
        as e(opportunity_id text,event_key text,kind text,old_value jsonb,new_value jsonb,source text)
        on conflict(event_key) do nothing''',(Jsonb(events),))


def list_events(db,identifier,*,limit=100):
    if not 1<=limit<=200:raise ValueError('Invalid event limit')
    rows=db.execute('''select id,kind,old_value,new_value,source,detected_at from radar_procurement_events
        where opportunity_id=%s order by detected_at desc,id desc limit %s''',(identifier,limit)).fetchall()
    return [{'id':row[0],'kind':row[1],'oldValue':row[2],'newValue':row[3],
             'source':row[4],'detectedAt':row[5].isoformat()} for row in rows]
