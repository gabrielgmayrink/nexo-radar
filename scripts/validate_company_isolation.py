"""Verify real production boundaries without changing anyone's password or sending mail."""
import json
import os
import secrets
import uuid
from datetime import datetime,timedelta,timezone
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from runtime_env import load

load()
os.environ['RADAR_SUPABASE_PROJECT_REF']='hxngkmrsthyjycxaellk'
from radar.postgres_store import PostgresStore
from radar.team_auth import auth_request,digest
from radar.team_reviews import save_review,list_reviews
from psycopg.types.json import Jsonb

BASE='https://nexo-radar-taupe.vercel.app'


def request(path,token=None,body=None):
    headers={'Accept':'application/json'}
    if token:headers['Cookie']='__Host-radar_session='+token
    if body:headers.update({'Origin':BASE,'Content-Type':'application/json'})
    req=Request(BASE+path,headers=headers,data=json.dumps(body).encode() if body else None)
    try:
        with urlopen(req,timeout=60) as response:return response.status,json.load(response),response.headers
    except HTTPError as exc:return exc.code,json.load(exc),exc.headers


class RollbackFixture(Exception):pass


def run():
    store=PostgresStore();test_user=None
    try:
        status,_,_=request('/api/opportunities?bulk=1')
        assert status==401
        email='nexo-isolation-'+uuid.uuid4().hex+'@example.invalid'
        user=auth_request('admin/users',{'email':email,'password':secrets.token_urlsafe(30),'email_confirm':True})
        test_user=(user.get('user') or user)['id']
        tokens={}
        for company,email in (('public','publicgerencia9@gmail.com'),('gerico','gericomayrink@gmail.com')):
            token=secrets.token_urlsafe(32);tokens[company]=token
            store.db.execute('insert into radar_team_sessions(token_digest,user_id,email,expires_at) values(%s,%s,%s,%s)',
                             (digest(token),test_user,email,datetime.now(timezone.utc)+timedelta(minutes=10)))
        counts={}
        for company,token in tokens.items():
            other='gerico' if company=='public' else 'public'
            code,catalog,headers=request('/api/opportunities?bulk=1&company='+company,token)
            assert code==200 and catalog['total']==len(catalog['opportunities'])
            assert 'private' in headers['Cache-Control'] and 'no-store' in headers['Cache-Control']
            counts[company]=catalog['total']
            name=company.title()
            for card in catalog['opportunities']:
                assert set(card['scores'])=={name}
                assert all(item.startswith(name+':') for item in card['evidence'])
            code,team,_=request('/api/team?company='+company,token)
            assert code==200 and team['companies']==[company]
            for path in ('/api/opportunities?company=','/api/team?company=','/api/detail?id=12345678000100-1-000001%2F2026&company='):
                assert request(path+other,token)[0]==403
            review={'id':'12345678000100-1-000001/2026','offer':other.title(),'status':'Nova','reason':'','version':0}
            assert request('/api/team',token,{'action':'save_review','company':company,'review':review})[0]==403
        print(json.dumps({'productionHttpIsolation':True,'anonymousDenied':True,'crossCompanyDenied':True,'privateCacheHeaders':True,'companyCounts':counts,'emailSent':False}),flush=True)
        fixture_id='00000000000000-1-999999/2026'
        try:
            with store.db.transaction():
                raw={'numeroControlePNCP':fixture_id,'objetoCompra':'Serviços de apoio administrativo'}
                store.write_records([raw])
                store.db.execute('update radar_opportunities set product_scores=%s where id=%s',(Jsonb({'Public':70,'Gerico':70}),fixture_id))
                for company in ('public','gerico'):
                    data={'id':fixture_id,'offer':company.title(),'status':'Em avaliação','reason':'Fixture '+company,'version':0,'reasonCode':'aderente','sourceObject':raw['objetoCompra'],'sourceAdditional':''}
                    result=save_review(store.db,data,'isolation-fixture',company)
                    assert result['version']==1
                    own=[row for row in list_reviews(store.db,company) if row['id']==fixture_id]
                    assert len(own)==1 and own[0]['reason']=='Fixture '+company
                raise RollbackFixture()
        except RollbackFixture:pass
        assert not store.db.execute('select 1 from radar_opportunities where id=%s',(fixture_id,)).fetchone()
        print(json.dumps({'independentReviewVersions':True,'reviewScopeVerified':True,'fixtureRolledBack':True}),flush=True)
    finally:
        if test_user:auth_request('admin/users/'+str(test_user),{},method='DELETE')
        store.close()


if __name__=='__main__':
    try:run()
    except Exception as exc:
        print(json.dumps({'validationFailed':type(exc).__name__}));raise SystemExit(1)
