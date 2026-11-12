"""Company authorization comes from server-managed memberships, never the client."""
from radar.team_auth import session_user,session_token

COMPANIES = {'public':'Public', 'gerico':'Gerico'}


class AccessDenied(Exception):
    def __init__(self, status=403):
        self.status=status
        super().__init__('Entre na conta autorizada para acessar esta empresa.' if status==401 else 'Esta conta não tem acesso a esta empresa.')


def memberships(db,email):
    return [row[0] for row in db.execute('select company_id from radar_memberships where email=%s order by company_id',(email,)).fetchall() if row[0] in COMPANIES]


def can_manage_company(db,email,company):
    if company not in COMPANIES:return False
    row=db.execute('select role from radar_memberships where email=%s and company_id=%s',(email,company)).fetchone()
    return bool(row and row[0] in ('owner','admin'))


def resolve_access(db,cookie,requested=None):
    email=session_user(db,cookie)
    if not email:raise AccessDenied(401)
    allowed=memberships(db,email)
    company=requested or ('public' if 'public' in allowed else next(iter(allowed),None))
    if company not in allowed:raise AccessDenied()
    return email,company,allowed


def request_access(cookie,requested=None):
    if not session_token(cookie):raise AccessDenied(401)
    from radar.postgres_store import PostgresStore
    store=PostgresStore()
    try:return resolve_access(store.db,cookie,requested)
    finally:store.close()


def visible_card(card,company):
    name=COMPANIES[company]
    score=card.get('scores',{}).get(name,0)
    if score<40:return None
    return {**card,'scores':{name:score},'score':score,'suggestedOffer':name if score>=60 else 'Revisar',
            'evidence':[value for value in card.get('evidence',[]) if value.startswith(name+':')],
            'decisionByCompany':{name:card.get('decisionByCompany',{}).get(name,{})}}


def review_card(card,company):
    """A source-backed rescue candidate exposes only this company's decision."""
    name=COMPANIES[company];score=card.get('scores',{}).get(name,0)
    return {**card,'scores':{name:score},'score':score,'suggestedOffer':'Revisar','reviewCandidate':True,
            'evidence':[value for value in card.get('evidence',[]) if value.startswith(name+':')],
            'decisionByCompany':{name:card.get('decisionByCompany',{}).get(name,{})}}
