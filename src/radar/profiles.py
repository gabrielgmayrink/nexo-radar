"""Company-specific procurement phrases, kept empty until services are known."""
import json
from pathlib import Path

PROFILE_PATH = Path(__file__).with_name('companies.json')


def load_profiles():
    companies = json.loads(PROFILE_PATH.read_text(encoding='utf-8'))['companies']
    if [c.get('id') for c in companies] != ['daltton', 'gerico']:
        raise ValueError('Invalid company profiles')
    for company in companies:
        if type(company.get('enabled')) is not bool:
            raise ValueError('Invalid company status')
        for field in ('services', 'terms', 'excludeTerms'):
            values = company.get(field)
            if not isinstance(values, list) or any(not isinstance(term, str) or not term.strip() for term in values):
                raise ValueError('Invalid company criteria')
        if company['enabled'] and (not company['services'] or not company['terms']):
            raise ValueError('Enabled companies require services and search phrases')
    return companies
