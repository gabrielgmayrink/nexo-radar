"""Invoke bounded Vercel batches using the runner's short-lived OIDC identity."""
import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

BASE = os.environ.get('RADAR_APP_URL', 'https://nexo-radar.example.invalid').rstrip('/')
AUDIENCE = BASE + '/api/collect'
MIN_BATCH_SECONDS = 10
REQUEST_MARGIN_SECONDS = 90


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Unexpected authentication redirect')


def identity(opener):
    parts = urlsplit(os.environ['ACTIONS_ID_TOKEN_REQUEST_URL'])
    query = dict(parse_qsl(parts.query))
    query['audience'] = AUDIENCE
    url = urlunsplit(parts._replace(query=urlencode(query)))
    request = Request(url, headers={'Authorization': 'Bearer ' + os.environ['ACTIONS_ID_TOKEN_REQUEST_TOKEN']})
    with opener.open(request, timeout=20) as response:
        return json.load(response)['value']


def run(kind, *, budget_seconds=480, opener=None, clock=time.monotonic, sleeper=time.sleep):
    if kind not in ('incremental', 'backfill', 'open'):
        raise ValueError('Invalid collection kind')
    if type(budget_seconds) is not int or not 120 <= budget_seconds <= 1440:
        raise ValueError('Invalid runner budget')
    opener = opener or build_opener(NoRedirect())
    started, execution_id, failures, last = clock(), None, 0, {}
    previous_errors=None
    while budget_seconds - (clock() - started) > REQUEST_MARGIN_SECONDS + MIN_BATCH_SECONDS:
        try:
            token = identity(opener)
            # Fit the final batch into the remaining budget instead of leaving
            # four minutes unused. The margin covers setup and the last page.
            remaining = budget_seconds - (clock() - started)
            batch_seconds = min(140, int(remaining - REQUEST_MARGIN_SECONDS))
            if batch_seconds < MIN_BATCH_SECONDS:
                break
            body = {'kind': kind, 'budgetSeconds': batch_seconds}
            if execution_id:
                body['executionId'] = execution_id
            request = Request(AUDIENCE, data=json.dumps(body).encode(),
                              headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'}, method='POST')
            with opener.open(request, timeout=min(235, max(1, remaining - 10))) as response:
                last = json.load(response)
            if last.get('busy'):
                sleeper(15)
                continue
            execution_id = last['executionId']
            print(json.dumps(last), flush=True)
            if last.get('done'):
                return 0
            errors=last.get('requestErrors',0)
            if errors>(previous_errors if previous_errors is not None else errors-int(last.get('status')=='partial')):
                failures+=1
            elif last.get('status')!='partial':failures=0
            previous_errors=errors
            if failures>=3:return 1
            if last.get('retryAfterSeconds',0)>0:
                sleeper(min(last['retryAfterSeconds']+1,60))
                continue
        except (HTTPError, URLError, TimeoutError) as exc:
            # Never print the request, token or an exception that may echo headers.
            print(json.dumps({'event': 'batch_request_failed', 'status': getattr(exc, 'code', None)}), flush=True)
            failures += 1
        if failures >= 3:
            return 1
        if failures:
            sleeper(min(10 * 2 ** failures, 30))
    print(json.dumps({'event': 'budget_reached', 'executionId': execution_id,
                      'resume': 'Próxima execução retomará o progresso salvo.'}), flush=True)
    return 1 if failures or last.get('status')=='partial' else 0


if __name__ == '__main__':
    raise SystemExit(run(os.environ.get('RADAR_SYNC_KIND', 'incremental'),
                         budget_seconds=int(os.environ.get('RADAR_SYNC_BUDGET_SECONDS', '480'))))
