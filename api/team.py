"""Private team access. All mutations require the production origin and JSON."""
import json
import os
from http.server import BaseHTTPRequestHandler
from radar.mail import APP_URL
from urllib.parse import urlparse,parse_qs


class handler(BaseHTTPRequestHandler):
    def respond(self,status,payload,cookie=None):
        body=json.dumps(payload,ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Cache-Control','no-store')
        self.send_header('Vary','Cookie')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Length',str(len(body)))
        self.send_header('X-Content-Type-Options','nosniff')
        if cookie:self.send_header('Set-Cookie',cookie)
        self.end_headers();self.wfile.write(body)

    def do_GET(self):self.handle_team()
    def do_POST(self):self.handle_team()

    def handle_team(self):
        if os.environ.get('RADAR_TEAM_ENABLED')!='1':
            self.respond(200,{'enabled':False,'authenticated':False});return
        data={}
        if self.command=='POST':
            if self.headers.get('Origin')!=APP_URL or self.headers.get('Content-Type','').split(';')[0]!='application/json':
                self.respond(403,{'error':'Origem não autorizada.'});return
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 1<=length<=64000:raise ValueError()
                data=json.loads(self.rfile.read(length))
                if not isinstance(data,dict):raise ValueError()
            except (ValueError,TypeError):
                self.respond(400,{'error':'Solicitação inválida.'});return
        from radar.postgres_store import PostgresStore
        from radar.team_auth import session_user,session_token,request_login,confirm_login,revoke_session,session_cookie
        from radar.team_reviews import list_reviews,save_review,ReviewConflict
        from radar.password_auth import password_login,setup_password,AuthenticationFailed,TooManyAttempts
        from radar.company_access import resolve_access,memberships,AccessDenied
        from radar.access_security import request_origin,throttle
        from radar.mfa import MFARequired,enroll,verify
        from radar.database_roles import company_transaction
        origin=request_origin(self.headers,getattr(self,'client_address',('unknown',))[0])
        if not session_token(self.headers.get('Cookie')):
            if self.command=='GET':
                self.respond(200,{'enabled':True,'authenticated':False,'reviews':[]});return
            if data.get('action') not in ('request_link','confirm_login','password_login','setup_password','mfa_enroll','mfa_verify'):
                self.respond(401,{'error':'Entre com o e-mail da equipe para continuar.'});return
        store=None
        try:
            store=PostgresStore();db=store.db
            if self.command=='GET':
                user=session_user(db,self.headers.get('Cookie'))
                query=parse_qs(urlparse(self.path).query)
                requested=query.get('company',[None])[0]
                page=max(0,min(100000,int(query.get('reviewsPage',['0'])[0])))
                limit=max(1,min(500,int(query.get('reviewsLimit',['200'])[0])))
                company=None;allowed=[]
                if user:_,company,allowed=resolve_access(db,self.headers.get('Cookie'),requested)
                if user:
                    with company_transaction(db,user,company):reviews=list_reviews(db,company,limit=limit+1,offset=page*limit)
                else:reviews=[]
                self.respond(200,{'enabled':True,'authenticated':bool(user),'email':user,
                                  'company':company,'companies':allowed,
                                  'reviews':reviews[:limit],'reviewsPage':page,'reviewsHasMore':len(reviews)>limit});return
            action=data.get('action')
            if action=='password_login':
                email,token=password_login(db,data.get('email'),data.get('password'),origin=origin)
                self.respond(200,{'authenticated':True,'email':email},session_cookie(token));return
            if action=='setup_password':
                email,token=setup_password(db,data.get('token'),data.get('password'),origin=origin)
                self.respond(200,{'authenticated':True,'email':email},session_cookie(token));return
            if action=='request_link':
                email=data.get('email','')
                if not isinstance(email,str) or len(email)>254:raise ValueError()
                request_login(db,email,origin=origin)
                self.respond(200,{'message':'Se este e-mail estiver autorizado, você receberá um link de acesso.'});return
            if action=='confirm_login':
                throttle(db,'link:'+str(data.get('token')),origin)
                email,token=confirm_login(db,data.get('token'))
                self.respond(200,{'authenticated':True,'email':email},session_cookie(token));return
            if action=='mfa_enroll':
                self.respond(200,enroll(db,data.get('pendingToken'),origin=origin));return
            if action=='mfa_verify':
                email,token=verify(db,data.get('pendingToken'),data.get('factorId'),data.get('code'),origin=origin)
                self.respond(200,{'authenticated':True,'email':email},session_cookie(token));return
            user=session_user(db,self.headers.get('Cookie'))
            if not user:
                self.respond(401,{'error':'Entre com o e-mail da equipe para continuar.'});return
            if action=='logout':
                revoke_session(db,self.headers.get('Cookie'))
                self.respond(200,{'authenticated':False},session_cookie('',clear=True));return
            if action=='save_review':
                _,company,_=resolve_access(db,self.headers.get('Cookie'),data.get('company'))
                role=db.execute('select role from radar_memberships where email=%s and company_id=%s',(user,company)).fetchone()
                if not role or role[0] not in ('owner','admin','analyst'):raise AccessDenied()
                with company_transaction(db,user,company):result=save_review(db,data.get('review'),user,company)
                self.respond(200,{'review':result});return
            raise ValueError()
        except MFARequired as exc:
            self.respond(200,exc.response)
        except AccessDenied as exc:
            self.respond(exc.status,{'error':str(exc)})
        except TooManyAttempts:
            self.respond(429,{'error':'Muitas tentativas. Aguarde 15 minutos para tentar novamente.'})
        except AuthenticationFailed:
            self.respond(401,{'error':'Não foi possível entrar. Confira o e-mail e a senha, ou solicite um convite válido à administração.'})
        except ReviewConflict:
            self.respond(409,{'error':'A avaliação ou o objeto mudou. Recarregue a avaliação da equipe e atualize a situação no PNCP antes de publicar novamente.'})
        except ValueError:
            self.respond(400,{'error':'Dados inválidos ou link expirado. Solicite um novo acesso.'})
        except Exception as exc:
            print(json.dumps({'event':'team_request_failed','errorType':type(exc).__name__}))
            self.respond(503,{'error':'A equipe está indisponível por alguns instantes. Tente novamente.'})
        finally:
            if store:store.close()
