"""Use a short-lived job identity; never copy the mail key into GitHub."""
import json
import os
from urllib.request import Request,build_opener
import run_scheduled_collection as jobs


def run():
    kind=os.environ.get('RADAR_NOTIFY_KIND','weekly')
    if kind not in ('weekly','urgent','test','verify','verify_smtp','delivery_test'):raise ValueError('Invalid notification')
    jobs.AUDIENCE=jobs.BASE+'/api/notify'
    opener=build_opener(jobs.NoRedirect())
    token=jobs.identity(opener)
    request=Request(jobs.AUDIENCE,data=json.dumps({'kind':kind}).encode(),method='POST',
                    headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
    with opener.open(request,timeout=235) as response:
        result=json.load(response)
    print(json.dumps(result))


if __name__=='__main__':
    try:run()
    except Exception as exc:
        print(json.dumps({'event':'notification_failed','errorType':type(exc).__name__,'status':getattr(exc,'code',None)}))
        raise SystemExit(1)
