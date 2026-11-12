"""Read public procurement cards through the server-only Supabase connection."""
import json
import os
from datetime import datetime,timezone
from urllib.parse import urlparse
from urllib.request import Request,urlopen
from radar.canonical import to_card
from radar.relevance import TZ,procurement_state,VERSION,classify
from radar.learning import apply_examples
from radar.company_access import visible_card,COMPANIES


def database_headers():
    base=os.environ.get('SUPABASE_URL','').rstrip('/')
    parsed=urlparse(base)
    if parsed.scheme!='https' or not parsed.hostname or not parsed.hostname.endswith('.supabase.co') or parsed.path or parsed.query or parsed.username:
        raise ValueError('Invalid database destination')
    key=os.environ.get('SUPABASE_SECRET_KEY') or os.environ.get('SUPABASE_SERVICE_ROLE_KEY')
    if not key:raise ValueError('Database is not configured')
    headers={'apikey':key,'Accept':'application/json'}
    if key.startswith('eyJ'):headers['Authorization']='Bearer '+key
    return base,headers


def database_get(path, *, opener=urlopen):
    base,headers=database_headers()
    with opener(Request(base+'/rest/v1/'+path,headers=headers),timeout=20) as response:
        body=response.read(4_000_001)
    if len(body)>4_000_000:raise ValueError('Database response too large')
    data=json.loads(body)
    if not isinstance(data,list):raise ValueError('Invalid database response')
    return data


def load_collection_status(*, opener=urlopen,db=None):
    if db is None:
        states=database_get('radar_catalog_state?select=id,content',opener=opener)
        executions=database_get('radar_executions?select=id,task,status,metrics,started_at,finished_at&task=like.sync%3A%25&order=started_at.desc&limit=6',opener=opener)
        checkpoints=database_get('radar_checkpoints?select=key,updated_at&key=like.sync%3A%25',opener=opener)
    else:
        states=[dict(zip(('id','content'),row)) for row in db.execute('select id,content from radar_catalog_state').fetchall()]
        executions=[dict(zip(('id','task','status','metrics','started_at','finished_at'),row)) for row in db.execute("select id,task,status,metrics,started_at,finished_at from radar_executions where task like 'sync:%' order by started_at desc limit 6").fetchall()]
        checkpoints=[dict(zip(('key','updated_at'),row)) for row in db.execute("select key,updated_at from radar_checkpoints where key like 'sync:%'").fetchall()]
        for row in executions:
            for key in ('started_at','finished_at'):
                if row[key] is not None:row[key]=row[key].isoformat()
        for row in checkpoints:row['updated_at']=row['updated_at'].isoformat()
    activity={row['key'][5:]:row['updated_at'] for row in checkpoints if str(row.get('key','')).startswith('sync:')}
    collections={}
    for row in states:
        if row.get('id') not in ('publications','open') or not isinstance(row.get('content'),dict):continue
        content=row['content']
        # Coverage is public-source metadata; company selection totals are private.
        collections[row['id']]={key:content[key] for key in ('completedAt','source','window','scope','coverageComplete','captureComplete','indexingComplete','consistency','quarantinedRecords','executionId','passNumber','expectedRecords','expectedPages') if key in content}
        collections[row['id']]['metrics']={'unique':content.get('metrics',{}).get('unique',0)}
    jobs=[]
    for row in executions:
        if row.get('task')!='sync:national_open':continue
        metrics=row.get('metrics') or {}
        error=metrics.get('error')
        if error not in ('http_429','timeout','erro_transporte','resposta_html_waf','storage_guard','invalid_page','coverage_gap','source_contract','source_5xx'):error=None
        jobs.append({'id':row['id'],'kind':row['task'][5:],'status':row['status'],
                     'startedAt':row['started_at'],'finishedAt':row.get('finished_at'),
                     'lastActivityAt':activity.get(row['task'][5:],row['started_at']),
                     'error':error,
                     'pages':metrics.get('pages',0),'recordsReceived':metrics.get('recordsReceived',0),
                     'completedPartitions':metrics.get('completedPartitions',0),
                     'totalPartitions':metrics.get('totalPartitions',0),
                     **{key:metrics.get(key) for key in ('scope','expectedRecords','expectedPages','passPages','uniqueRecords','coverageComplete','captureComplete','indexingComplete','consistency','quarantinedRecords','passNumber')}})
    return {'enabled':os.environ.get('RADAR_COLLECTION_ENABLED')=='1',
            'scope':'all_open_brazil','collections':collections,'executions':jobs}


def load_database_catalog(snapshot: dict, *, opener=urlopen,company=None) -> dict:
    if company is not None and company not in COMPANIES:raise ValueError('Invalid company')
    cards=[]
    for offset in range(0,10000,500):
        scope='&product_scores->>'+COMPANIES[company]+'=gte.40' if company else ''
        data=database_get('radar_national_candidates?select=card&score=gte.40'+scope+'&order=id.asc&offset='+str(offset)+'&limit=500',opener=opener)
        for item in data:
            if not isinstance(item,dict):raise ValueError('Invalid procurement record')
            card=item.get('card')
            if not card and isinstance(item.get('payload'),dict):card=to_card(item['payload'])
            if not isinstance(card,dict) or not card.get('id'):
                raise ValueError('Invalid procurement record')
            if card.get('ruleVersion') != VERSION:
                card={**card,**classify(card.get('object',''),card.get('additionalInfo',''))}
            if company:
                card=visible_card(card,company)
                if card is None:continue
            still_open=procurement_state({'situacaoCompraId':card.get('statusId'),'tipoInstrumentoConvocatorioCodigo':card.get('instrumentId'),
                                         'dataEncerramentoProposta':card.get('proposalDeadline'),'dataAberturaProposta':card.get('proposalStart')}) in ('Recebendo propostas','A receber propostas')
            if card['score']>=40 and still_open:cards.append(card)
        if len(data)<500:break
    else:raise ValueError('Database page budget exceeded')
    if os.environ.get('RADAR_TEAM_ENABLED')=='1':
        examples=database_get('radar_learning_examples?select=opportunity_id,offer,reason_code,object_hash,example_object,example_additional'+('&company_id=eq.'+company if company else '')+'&order=opportunity_id.asc&limit=1001',opener=opener)
        if len(examples)>1000:raise ValueError('Learning example budget exceeded')
        cards=apply_examples(cards,examples)
    cards.sort(key=lambda r:(-r['score'],r['proposalDeadline']))
    sync=load_collection_status(opener=opener)
    published=sync['collections'].get('open',{})
    metrics={**snapshot.get('metrics',{}),**published.get('metrics',{}),'candidates':len(cards)}
    metrics['discarded']=max(0,metrics.get('unique',0)-len(cards))
    return {**snapshot,'rulesVersion':VERSION,'dataSource':'supabase','databaseCheckedAt':datetime.now(timezone.utc).isoformat(),
            'collectionDate':published.get('window',{}).get('end',snapshot.get('collectionDate')),
            'collectionCompletedAt':published.get('completedAt'),
            'historical':False,'scope':'all_open_brazil','coverageComplete':published.get('coverageComplete',False),'sync':sync,
            'metrics':metrics,'opportunities':cards}
