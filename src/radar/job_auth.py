"""Short-lived GitHub Actions identities; no database credential leaves Vercel."""
import jwt
import os
from radar.settings import app_url

ISSUER = 'https://token.actions.githubusercontent.com'
AUDIENCE = app_url() + '/api/collect'
REPOSITORY = 'gabrielgmayrink/radar-daltton-gerico'
REPOSITORY_ID = os.environ.get('RADAR_GITHUB_REPOSITORY_ID', '')
OWNER_ID = '169843370'
WORKFLOW = REPOSITORY + '/.github/workflows/collect.yml@refs/heads/main'
SUBJECTS = {
    'repo:' + REPOSITORY + ':ref:refs/heads/main',
    'repo:gabrielgmayrink@' + OWNER_ID + '/radar-daltton-gerico@' + REPOSITORY_ID + ':ref:refs/heads/main',
}
_keys = jwt.PyJWKClient(ISSUER + '/.well-known/jwks', cache_keys=True, lifespan=300, timeout=10)


def verify_claims(claims,*,purpose='collect'):
    workflow=WORKFLOW if purpose=='collect' else REPOSITORY+'/.github/workflows/notify.yml@refs/heads/main'
    if (not REPOSITORY_ID or claims.get('repository_id') != REPOSITORY_ID or claims.get('repository_owner_id') != OWNER_ID
            or claims.get('repository') != REPOSITORY or claims.get('ref') != 'refs/heads/main'
            or purpose not in ('collect','notify') or claims.get('workflow_ref') != workflow or claims.get('sub') not in SUBJECTS
            or claims.get('event_name') not in ('schedule', 'workflow_dispatch')
            or claims.get('repository_visibility') != 'private'):
        raise ValueError('Untrusted job identity')
    run_id, attempt = claims.get('run_id', ''), claims.get('run_attempt', '')
    if not isinstance(run_id, str) or not run_id.isdigit() or not isinstance(attempt, str) or not attempt.isdigit():
        raise ValueError('Invalid job identity')
    return run_id + ':' + attempt


def authenticate(header, *, key_client=None,purpose='collect'):
    if not header.startswith('Bearer ') or len(header) > 20000:
        raise ValueError('Job authentication required')
    token = header[7:]
    key = (key_client or _keys).get_signing_key_from_jwt(token).key
    if purpose not in ('collect','notify'):raise ValueError('Invalid job purpose')
    audience=AUDIENCE if purpose=='collect' else AUDIENCE.rsplit('/',1)[0]+'/notify'
    claims = jwt.decode(token, key, algorithms=['RS256'], issuer=ISSUER, audience=audience, leeway=15,
                        options={'require': ['exp', 'iat', 'nbf', 'iss', 'aud', 'sub', 'repository_id',
                                             'repository_owner_id', 'ref', 'workflow_ref', 'event_name']})
    return verify_claims(claims,purpose=purpose)
