"""Read public procurement cards through the server-only Supabase connection."""
import json
import os
from datetime import datetime,timezone,timedelta
from urllib.parse import urlparse
from urllib.request import Request,urlopen
from radar.canonical import to_card
from radar.relevance import TZ,procurement_state
from radar.learning import apply_examples


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


def load_collection_status(*, opener=urlopen):
    states=database_get('radar_catalog_state?select=id,content',opener=opener)
    executions=database_get('radar_executions?select=id,task,status,metrics,started_at,finished_at&task=like.sync%3A%25&order=started_at.desc&limit=6',opener=opener)
    checkpoints=database_get('radar_checkpoints?select=key,updated_at&key=like.sync%3A%25',opener=opener)
    activity={row['key'][5:]:row['updated_at'] for row in checkpoints if str(row.get('key','')).startswith('sync:')}
    collections={row['id']:row['content'] for row in states
                 if row.get('id') in ('publications','open') and isinstance(row.get('content'),dict)}
    jobs=[]
    for row in executions:
        if not str(row.get('task','')).startswith('sync:'):continue
        metrics=row.get('metrics') or {}
        error=metrics.get('error')
        if error not in ('http_429','timeout','erro_transporte','resposta_html_waf','storage_guard','invalid_page'):error=None
        jobs.append({'id':row['id'],'kind':row['task'][5:],'status':row['status'],
                     'startedAt':row['started_at'],'finishedAt':row.get('finished_at'),
                     'lastActivityAt':activity.get(row['task'][5:],row['started_at']),
                     'error':error,
                     'pages':metrics.get('pages',0),'recordsReceived':metrics.get('recordsReceived',0),
                     'completedPartitions':metrics.get('completedPartitions',0),
                     'totalPartitions':metrics.get('totalPartitions',0)})
    return {'enabled':os.environ.get('RADAR_COLLECTION_ENABLED')=='1',
            'collections':collections,'executions':jobs}


def load_database_catalog(snapshot: dict, *, opener=urlopen) -> dict:
    cards=[]
    cutoff=(datetime.now(TZ).date()-timedelta(days=29)).isoformat()
    for offset in range(0,10000,500):
        data=database_get('radar_opportunities?select=payload,card&score=gte.40&order=id.asc&offset='+str(offset)+'&limit=500',opener=opener)
        for item in data:
            if not isinstance(item,dict) or not isinstance(item.get('payload'),dict) or not item['payload'].get('numeroControlePNCP'):
                raise ValueError('Invalid procurement record')
            card=item.get('card') or to_card(item['payload'])
            in_window=not card.get('publishedAt') or card['publishedAt'][:10]>=cutoff
            still_open=procurement_state(item['payload']) in ('Recebendo propostas','A receber propostas')
            if card['score']>=40 and (in_window or still_open):cards.append(card)
        if len(data)<500:break
    else:raise ValueError('Database page budget exceeded')
    if os.environ.get('RADAR_TEAM_ENABLED')=='1':
        examples=database_get('radar_learning_examples?select=opportunity_id,offer,reason_code,object_hash,example_object,example_additional&order=opportunity_id.asc&limit=1001',opener=opener)
        if len(examples)>1000:raise ValueError('Learning example budget exceeded')
        cards=apply_examples(cards,examples)
    cards.sort(key=lambda r:(-r['score'],r['proposalDeadline']))
    sync=load_collection_status(opener=opener)
    published=sync['collections'].get('publications',{})
    return {**snapshot,'dataSource':'supabase','databaseCheckedAt':datetime.now(timezone.utc).isoformat(),
            'collectionDate':published.get('window',{}).get('end',snapshot.get('collectionDate')),
            'collectionCompletedAt':published.get('completedAt'),
            'historical':not bool(published) or published.get('source')=='historical-import','sync':sync,
            'metrics':{**snapshot.get('metrics',{}),**published.get('metrics',{}),'candidates':len(cards)},'opportunities':cards}
