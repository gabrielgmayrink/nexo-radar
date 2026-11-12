"""Private server-side catalog pages. No score gate hides the review queue."""
from datetime import datetime,timezone
from radar.canonical import to_card
from radar.company_access import COMPANIES
from radar.profiles import load_profiles,profile_context
from radar.relevance import VERSION,classify,classification_version,normalize
from radar.search import ALIASES,parse_query
from radar.catalog_storage import load_collection_status

VIEWS=('all','matches','review','open','tracked','dismissed','discover','learning')
SORTS={'deadline':'deadline asc nulls last,id asc','published':'published desc nulls last,id asc',
       'score':'effective_score desc,id asc','value':'estimated desc nulls last,id asc'}


def options(query):
    def value(name,default=''):return query.get(name,[default])[0]
    page=int(value('page','1'));limit=int(value('limit','24'))
    if page<1 or not 1<=limit<=100:raise ValueError('Invalid page')
    view=value('view','all');sort=value('sort','deadline')
    if view not in VIEWS or sort not in SORTS:raise ValueError('Invalid catalog selection')
    uf=value('uf','Todas')
    if uf!='Todas' and uf not in 'AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO'.split():raise ValueError('Invalid state')
    deadline=value('deadline','any');assessment=value('assessment','any')
    if deadline not in ('any','unknown','7','15','30') or assessment not in ('any','reviewed','unreviewed'):raise ValueError('Invalid filter')
    result={'page':page,'limit':limit,'view':view,'sort':sort,'uf':uf,'deadline':deadline,
            'assessment':assessment,'q':value('q')[:240],'modality':value('modality','Todas')[:180],
            'city':value('city')[:160],'organization':value('organization')[:160],
            'publishedFrom':value('publishedFrom'),'publishedTo':value('publishedTo')}
    for key in ('publishedFrom','publishedTo'):
        if result[key]:datetime.strptime(result[key],'%Y-%m-%d')
    for key in ('minValue','maxValue'):
        raw=value(key);amount=float(raw) if raw else None
        if amount is not None and not 0<=amount<=10**15:raise ValueError('Invalid amount')
        result[key]=amount
    if result['minValue'] is not None and result['maxValue'] is not None and result['minValue']>result['maxValue']:raise ValueError('Invalid amount range')
    return result


BASE='''with records as (
 select n.id,n.payload,n.card,n.rule_version,n.classification_version,
 coalesce((n.product_scores->>%s)::integer,0) as rule_score,
 case when r.opportunity_id<>n.id and (r.offer='Nenhuma' and r.reason_code not in ('produto_diferente','nao_contrata_sistema','mencao_incidental')
 or exists(select 1 from public.radar_review_state x where x.company_id=r.company_id and x.object_hash=n.object_hash
   and ((x.offer='Nenhuma' and r.offer in ('Public','Gerico')) or (r.offer='Nenhuma' and x.offer in ('Public','Gerico')))))
 then 'Revisar' else r.offer end as review_offer,
 case when r.opportunity_id=n.id then r.status else null end as review_status,r.reason as review_reason,r.reason_code,
 r.expected_scope,r.actor,r.version,r.updated_at,r.opportunity_id as review_source_id,
 public.radar_safe_timestamp(n.payload->>'dataEncerramentoProposta') as deadline,
 public.radar_safe_timestamp(n.payload->>'dataPublicacaoPncp') as published,
 case when jsonb_typeof(n.payload->'valorTotalEstimado')='number' then (n.payload->>'valorTotalEstimado')::numeric else null end as estimated,
 public.radar_search_normalize(coalesce(n.payload->>'objetoCompra','')||' '||coalesce(n.payload->>'informacaoComplementar','')||' '||
 coalesce(n.payload->'orgaoEntidade'->>'razaoSocial','')||' '||coalesce(n.payload->'unidadeOrgao'->>'municipioNome','')||' '||
 coalesce(n.payload->'unidadeOrgao'->>'ufSigla','')||' '||n.id) as search_text,
 n.payload->'unidadeOrgao'->>'ufSigla' as uf,n.payload->>'modalidadeNome' as modality,
 public.radar_search_normalize(n.payload->'unidadeOrgao'->>'municipioNome') as city,
 public.radar_search_normalize(n.payload->'orgaoEntidade'->>'razaoSocial') as organization
 from public.radar_catalog_source n left join lateral (
 select r.* from public.radar_review_state r where r.company_id=%s and
 ((r.opportunity_id=n.id and r.example_object=n.payload->>'objetoCompra'
 and r.example_additional=coalesce(n.payload->>'informacaoComplementar',''))
 or (n.object_hash is not null and r.object_hash=n.object_hash and length(public.radar_search_normalize(n.payload->>'objetoCompra'))>=80))
 order by (r.opportunity_id=n.id) desc,r.updated_at desc,r.opportunity_id limit 1
 ) r on true
 where n.payload->>'situacaoCompraId'='1' and n.payload->>'tipoInstrumentoConvocatorioCodigo' in ('1','2','4')
), classified as (
 select *, coalesce(rule_score>=40 or review_offer=%s or review_offer='Revisar' or review_status='Vou participar',false) as selected,
 coalesce(review_offer='Nenhuma' or review_status='Descartada',false) as dismissed,
 case when review_offer=%s then greatest(rule_score,70) else rule_score end as effective_score
 from records where deadline is null or deadline>%s
)'''


def view_condition(view):
    return {
        'all':'selected and not dismissed',
        'matches':"selected and not dismissed and effective_score>=60 and coalesce(review_offer,'')<>'Revisar' and deadline is not null",
        'review':"selected and not dismissed and (effective_score<60 or review_offer='Revisar' or deadline is null)",
        'open':'selected and not dismissed and deadline is not null',
        'tracked':"review_status='Vou participar' and not dismissed",
        'dismissed':'dismissed',
        'discover':'not selected and not dismissed',
        'learning':'false',
    }[view]


def filter_sql(config,profile=None):
    clauses=[];params=[]
    for word,excluded,phrase in parse_query(config['q']):
        alternatives=(word,) if phrase else ALIASES.get(word,(word,))
        tests=[]
        for term in alternatives:
            padded=phrase or ' ' in term or len(term)<=2
            tests.append("position(%s in (' '||search_text||' '))>0" if padded else 'position(%s in search_text)>0')
            params.append(' '+term+' ' if padded else term)
        clauses.append(('not ' if excluded else '')+'('+' or '.join(tests)+')')
    if config['uf']!='Todas':clauses.append('uf=%s');params.append(config['uf'])
    if config['modality']!='Todas':clauses.append('modality=%s');params.append(config['modality'])
    for field in ('city','organization'):
        if config.get(field):clauses.append('position(%s in '+field+')>0');params.append(normalize(config[field]))
    for field,operator in (('minValue','>='),('maxValue','<=')):
        if config.get(field) is not None:clauses.append('estimated'+operator+'%s');params.append(config[field])
    if config.get('publishedFrom'):clauses.append("published>=%s::date at time zone 'America/Sao_Paulo'");params.append(config['publishedFrom'])
    if config.get('publishedTo'):clauses.append("published<(%s::date+1) at time zone 'America/Sao_Paulo'");params.append(config['publishedTo'])
    if profile:
        for field,column in (('states','uf'),('modalities','modality')):
            if profile.get(field):clauses.append(column+'=any(%s)');params.append(profile[field])
        if profile.get('cities'):clauses.append('city=any(%s)');params.append([normalize(city) for city in profile['cities']])
        for field,operator in (('minValue','>='),('maxValue','<=')):
            if profile.get(field) is not None:clauses.append('estimated'+operator+'%s');params.append(profile[field])
    if config['assessment']!='any':clauses.append("coalesce(review_offer,'')"+('=' if config['assessment']=='unreviewed' else '<>')+"''")
    if config['deadline']=='unknown':clauses.append('deadline is null')
    elif config['deadline']!='any':
        clauses.append("deadline<=%s+%s*interval '1 day'");params.extend((datetime.now(timezone.utc),int(config['deadline'])))
    return (' and '.join(clauses) or 'true'),params


def private_card(payload,stored,company,*,review_candidate=False,profiles=None):
    name=COMPANIES[company]
    card=stored or to_card(payload)
    if card.get('classificationVersion')!=classification_version(profiles):card={**card,**classify(payload.get('objetoCompra') or '',payload.get('informacaoComplementar') or '',profiles=profiles)}
    decision=card.get('decisionByCompany',{}).get(name)
    return {**card,'scores':{name:card.get('scores',{}).get(name,0)},'score':card.get('scores',{}).get(name,0),
            'suggestedOffer':name if card.get('scores',{}).get(name,0)>=60 else 'Revisar',
            'evidence':[reason for reason in card.get('evidence',[]) if reason.startswith(name+':')],
            'decisionByCompany':{name:decision} if decision else {},'reviewCandidate':review_candidate or card.get('scores',{}).get(name,0)<40}


def load_catalog_page(snapshot,company,query,db,*,status_loader=None):
    if company not in COMPANIES:raise ValueError('Invalid company')
    config=options(query);name=COMPANIES[company]
    profiles=load_profiles(db);profile=next(p for p in profiles if p['id']==company);active=profile['enabled']
    version=classification_version(profiles)
    now=datetime.now(timezone.utc)
    base_params=[name,company,name,name,now]
    where,params=filter_sql(config,profile)
    if not active:where='false'
    counts=db.execute(BASE+' select '+','.join('count(*) filter(where '+view_condition(view)+')' for view in VIEWS)+' from classified where '+where,base_params+params).fetchone()
    counts=dict(zip(VIEWS,counts));total=counts[config['view']]
    pages=max(1,(total+config['limit']-1)//config['limit']);page=min(config['page'],pages)
    data=db.execute(BASE+''' select payload,card,review_offer,review_status,review_reason,reason_code,expected_scope,actor,version,updated_at
       ,review_source_id from classified where '''+where+' and ('+view_condition(config['view'])+') order by '+SORTS[config['sort']]+' limit %s offset %s',base_params+params+[config['limit'],(page-1)*config['limit']]).fetchall()
    cards=[];reviews={}
    for payload,stored,offer,status,reason,reason_code,expected_scope,actor,review_version,updated,review_source_id in data:
        card=private_card(payload,stored,company,review_candidate=config['view']=='discover',profiles=profiles)
        if offer is not None and review_source_id==card['id']:
            reviews[card['id']]={'id':card['id'],'offer':offer,'status':status,'reason':reason,'reasonCode':reason_code,
                'expectedScope':expected_scope,'actor':actor,'version':review_version,'sourceCurrent':True,'updatedAt':updated.isoformat()}
        elif offer:
            card['learning']={'label':'irrelevante' if offer=='Nenhuma' else 'relevante' if offer==name else 'revisar',
                             'match':'exact','reasonCode':reason_code,'examples':1,'offer':offer}
        cards.append(card)
    facet_condition='not selected and not dismissed' if config['view']=='discover' else 'selected and not dismissed'
    profile_where,profile_params=filter_sql(options({}),profile)
    facet_where='('+facet_condition+') and '+profile_where if active else 'false'
    facets=db.execute(BASE+' select uf,modality,count(*) from classified where '+facet_where+' group by uf,modality',base_params+profile_params).fetchall()
    states={};modalities=set()
    for uf,modality,count in facets:
        if uf:states[uf]=states.get(uf,0)+count
        if modality:modalities.add(modality)
    sync=status_loader() if status_loader is not None else load_collection_status(db=db)
    published=sync.get('collections',{}).get('open',{})
    metrics={'unique':published.get('metrics',{}).get('unique',snapshot.get('metrics',{}).get('unique',0)),
             'candidates':counts['all'],'discarded':counts['dismissed']}
    pending=db.execute('select count(*) from radar_catalog_source where classification_version is distinct from %s',(version,)).fetchone()[0]
    return {**snapshot,'dataSource':'supabase','rulesVersion':VERSION,'collectionDate':published.get('window',{}).get('end',snapshot.get('collectionDate')),
       'collectionCompletedAt':published.get('completedAt'),'coverageComplete':published.get('coverageComplete',False),
       'sync':sync,'metrics':metrics,'opportunities':cards,'total':total,'page':page,'limit':config['limit'],'pages':pages,
       'profile':profile,'classification':{'version':version,'pendingRecords':pending,'complete':pending==0},
       'counts':counts,'facets':{'states':states,'modalities':sorted(modalities)},'pageReviews':reviews,'paginated':True,
       'databaseCheckedAt':now.isoformat()}
