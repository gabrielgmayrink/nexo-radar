"""Account revocation and bounded abuse controls for opaque app sessions."""
import ipaddress
import os
from radar.team_auth import digest


class TooManyAttempts(ValueError):
    pass


def request_origin(headers,peer='unknown'):
    # Vercel replaces this header at its trusted ingress. A local server uses
    # its socket peer instead of trusting client-supplied forwarding headers.
    candidate=headers.get('X-Forwarded-For','').split(',')[0].strip() if os.environ.get('VERCEL')=='1' else peer
    try:
        address=ipaddress.ip_address(candidate)
        return str(ipaddress.ip_network(str(address)+'/64',strict=False)) if address.version==6 else str(address)
    except ValueError:
        return 'unknown'


def throttle(db,subject,origin='unknown'):
    keys=(('global',300),('origin:'+origin,40),('pair:'+origin+'|'+str(subject).strip().lower(),8))
    hashed=[(digest(key),limit) for key,limit in keys]
    with db.transaction():
        for key,limit in sorted(hashed):
            db.execute('select pg_advisory_xact_lock(%s)',(int(key[:15],16),))
            count=db.execute("select count(*) from radar_auth_attempts where subject_hash=%s and created_at>now()-interval '15 minutes'",(key,)).fetchone()[0]
            if count>=limit:raise TooManyAttempts('Login temporarily limited')
        db.execute('insert into radar_auth_attempts(subject_hash) select unnest(%s::text[])',([key for key,_ in hashed],))
        db.execute("delete from radar_auth_attempts where created_at<now()-interval '24 hours'")


def account_state(db,email,*,lock=False):
    row=db.execute('select generation,require_mfa,disabled_at from radar_account_security where email=%s'+(' for update' if lock else ''),(email,)).fetchone()
    return (row[0],bool(row[1]),row[2]) if row and type(row[0]) is int else (0,False,None)


def lock_account(db,email):
    db.execute('select pg_advisory_xact_lock(hashtextextended(%s,0))',('auth:'+email,))


def revoke_account(db,email):
    """Durably revoke before a remote password mutation; failures stay closed."""
    lock_account(db,email)
    row=db.execute('''insert into radar_account_security(email,generation) values(%s,1)
        on conflict(email) do update set generation=radar_account_security.generation+1,updated_at=now()
        returning generation''',(email,)).fetchone()
    db.execute('update radar_team_sessions set expires_at=least(expires_at,now()) where email=%s',(email,))
    db.execute('update radar_account_invites set consumed_at=coalesce(consumed_at,now()) where email=%s',(email,))
    db.execute('update radar_login_requests set consumed_at=coalesce(consumed_at,now()) where email=%s',(email,))
    db.execute('update radar_mfa_pending set consumed_at=coalesce(consumed_at,now()) where email=%s',(email,))
    return row[0] if row and type(row[0]) is int else 1
