"""Read-only operational monitor, independent from the collection workflow."""
import json
from urllib.request import Request,build_opener
from run_scheduled_collection import AUDIENCE,NoRedirect,identity


def main():
    opener=build_opener(NoRedirect())
    token=identity(opener)
    request=Request(AUDIENCE,data=json.dumps({'action':'health'}).encode(),method='POST',
                    headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
    with opener.open(request,timeout=45) as response:
        body=response.read(1_000_001)
    if len(body)>1_000_000:raise ValueError('Invalid monitor response')
    result=json.loads(body)
    health=result.get('health',result)
    print(json.dumps({'event':'independent_health_check','ok':health.get('ok',False),
                      'alerts':[check['id'] for check in health.get('checks',[]) if check.get('ok') is not True]}))
    if health.get('ok') is not True:raise SystemExit(1)


if __name__=='__main__':
    try:main()
    except Exception as exc:
        print(json.dumps({'event':'health_check_failed','errorType':type(exc).__name__}))
        raise SystemExit(1)
