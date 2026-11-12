"""Company-specific procurement phrases, kept empty until services are known."""
import json
from pathlib import Path
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy

_CURRENT=ContextVar('radar_profiles',default=None)

PROFILE_PATH = Path(__file__).with_name('companies.json')


def validate_profiles(companies):
    if [c.get('id') for c in companies] != ['public', 'gerico']:
        raise ValueError('Invalid company profiles')
    for company in companies:
        if type(company.get('enabled')) is not bool:
            raise ValueError('Invalid company status')
        if type(company.get('requireServiceIntent',False)) is not bool:
            raise ValueError('Invalid service intent policy')
        for field in ('services', 'terms', 'excludeTerms'):
            values = company.get(field)
            if not isinstance(values, list) or any(not isinstance(term, str) or not term.strip() for term in values):
                raise ValueError('Invalid company criteria')
        if company['enabled'] and (not (company['services'] or company.get('products')) or not (company['terms'] or company.get('products'))):
            raise ValueError('Enabled companies require services and search phrases')
        for group in company.get('reviewGroups',[]):
            if not isinstance(group,dict) or not isinstance(group.get('label'),str) or not group['label'].strip():
                raise ValueError('Invalid review group')
            for field in ('subjects','contexts'):
                if not isinstance(group.get(field),list) or not group[field] or any(not isinstance(term,str) or not term.strip() for term in group[field]):
                    raise ValueError('Invalid review group criteria')
    return companies


def load_profiles(db=None):
    if db is None and _CURRENT.get() is not None:return deepcopy(_CURRENT.get())
    companies = json.loads(PROFILE_PATH.read_text(encoding='utf-8'))['companies']
    if db is not None:
        rows=db.execute('select company_id,configuration from radar_company_profiles').fetchall()
        overrides=dict(rows)
        companies=[{**company,**overrides.get(company['id'],{}),'id':company['id'],'name':company['name']} for company in companies]
    return validate_profiles(companies)


@contextmanager
def profile_context(db):
    token=_CURRENT.set(load_profiles(db))
    try:yield _CURRENT.get()
    finally:_CURRENT.reset(token)
