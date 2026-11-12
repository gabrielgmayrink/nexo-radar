"""Versioned company preferences; only server-authorized managers can modify them."""
from copy import deepcopy
from psycopg.types.json import Jsonb
from radar.company_access import COMPANIES,AccessDenied,can_manage_company
from radar.profiles import load_profiles,validate_profiles
from radar.relevance import classification_version

FIELDS={'enabled','products','services','terms','excludeTerms','synonyms','states','cities','organizations','modalities','minValue','maxValue','notificationPreferences'}
STATES=set('AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO'.split())

class ProfileConflict(ValueError):pass

def validate_configuration(configuration,current):
    if not isinstance(configuration,dict) or set(configuration)-FIELDS:raise ValueError('Invalid profile fields')
    result=deepcopy(current)
    for key,value in configuration.items():
        if key=='enabled':
            if type(value) is not bool:raise ValueError('Invalid profile state')
        elif key in ('minValue','maxValue'):
            if value is not None and (type(value) not in (int,float) or not 0<=value<=10**15):raise ValueError('Invalid amount')
        elif key=='notificationPreferences':
            if not isinstance(value,dict) or set(value)-{'weeklyEmail','urgentEmail'} or any(type(v) is not bool for v in value.values()):raise ValueError('Invalid notification preferences')
        elif key=='synonyms':
            if not isinstance(value,dict) or len(value)>60:raise ValueError('Invalid synonyms')
            for term,alternatives in value.items():
                if not isinstance(term,str) or not 1<=len(term.strip())<=160:raise ValueError('Invalid synonym')
                validate_strings(alternatives,20)
        else:
            validate_strings(value,200 if key in ('terms','excludeTerms') else 80)
            if key=='states' and any(state not in STATES for state in value):raise ValueError('Invalid state')
        result[key]=deepcopy(value)
    if result.get('minValue') is not None and result.get('maxValue') is not None and result['minValue']>result['maxValue']:raise ValueError('Invalid amount range')
    # Identity and confirmed company intent policy cannot be overwritten from the browser.
    return result

def validate_strings(value,limit):
    if not isinstance(value,list) or len(value)>limit or any(not isinstance(item,str) or not item.strip() or len(item)>500 for item in value):raise ValueError('Invalid profile list')

def get_profile(db,company,email):
    profiles=load_profiles(db)
    current=next(profile for profile in profiles if profile['id']==company)
    row=db.execute('select version,updated_at from radar_company_profiles where company_id=%s',(company,)).fetchone()
    return {'profile':current,'version':row[0] if row else 0,'updatedAt':row[1].isoformat() if row else None,
            'canManage':can_manage_company(db,email,company),'classificationVersion':classification_version(profiles)}

def save_profile(db,company,email,data):
    if company not in COMPANIES or not can_manage_company(db,email,company):raise AccessDenied()
    if not isinstance(data,dict) or type(data.get('version')) is not int or data['version']<0:raise ValueError('Invalid profile version')
    with db.transaction():
        db.execute('select pg_advisory_xact_lock(hashtextextended(%s,0))',('profile:'+company,))
        current=get_profile(db,company,email)
        if data['version']!=current['version']:raise ProfileConflict('Profile changed')
        profile=validate_configuration(data.get('configuration'),current['profile'])
        profiles=[profile if item['id']==company else item for item in load_profiles(db)]
        validate_profiles(profiles)
        stored={key:profile[key] for key in FIELDS if key in profile}
        version=current['version']+1
        db.execute('''insert into radar_company_profiles(company_id,configuration,version,actor) values(%s,%s,%s,%s)
          on conflict(company_id) do update set configuration=excluded.configuration,version=excluded.version,actor=excluded.actor,updated_at=now()''',
          (company,Jsonb(stored),version,email))
        db.execute('insert into radar_profile_history(company_id,configuration,version,actor) values(%s,%s,%s,%s)',(company,Jsonb(stored),version,email))
        result=get_profile(db,company,email)
        result['reclassificationPending']=True
        return result
