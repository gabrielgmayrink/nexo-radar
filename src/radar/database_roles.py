"""Optional transaction-scoped RLS role; activate after owner role provisioning."""
from contextlib import contextmanager
import os
from radar.company_access import COMPANIES,AccessDenied,memberships


@contextmanager
def company_transaction(db,email,company):
    if company not in COMPANIES or company not in memberships(db,email):raise AccessDenied()
    with db.transaction():
        if os.environ.get('RADAR_DB_ENFORCE_ROLES')=='1':
            db.execute('set local role radar_web')
            db.execute("select set_config('radar.company_id',%s,true),set_config('radar.actor_email',%s,true)",(company,email))
        yield db
