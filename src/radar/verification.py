"""Confirm shortlisted procurement records directly with PNCP before notifying."""
import json
import re
import time
from urllib.request import Request,build_opener,HTTPRedirectHandler
from radar.canonical import to_card
from radar.pncp import BASE_URL,USER_AGENT
from radar.identifiers import parse_pncp_id


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise ValueError('Unexpected PNCP redirect')


def fetch_record(identifier,*,opener=None,timeout=8):
    parsed=parse_pncp_id(identifier)
    cnpj,sequence,year=parsed.cnpj,parsed.sequence,parsed.year
    request=Request(f'{BASE_URL}/v1/orgaos/{cnpj}/compras/{year}/{int(sequence)}',
                    headers={'User-Agent':USER_AGENT,'Accept':'application/json'})
    with (opener or build_opener(NoRedirect())).open(request,timeout=timeout) as response:
        body=response.read(2_000_001)
    if len(body)>2_000_000:raise ValueError('Procurement response is too large')
    row=json.loads(body)
    if not isinstance(row,dict) or parse_pncp_id(row.get('numeroControlePNCP')).canonical!=parsed.canonical:
        raise ValueError('PNCP returned a different procurement')
    return row


def verify_shortlist(cards,review_by_id,*,fetcher=fetch_record,writer,now,clock=time.monotonic,sleeper=time.sleep):
    result=[];changed=set();failures=0;previous=None
    for index,old in enumerate(cards):
        if previous is not None:
            remaining=1.5-(clock()-previous)
            if remaining>0:sleeper(remaining)
        previous=clock()
        try:
            raw=fetcher(old['id'])
            if not isinstance(raw,dict) or raw.get('numeroControlePNCP')!=old['id']:
                raise ValueError('PNCP returned a different procurement')
        except (OSError,ValueError,TimeoutError) as exc:
            if getattr(exc,'code',None)==429:
                failures+=len(cards)-index;break
            failures+=1;continue
        fresh=to_card(raw)
        # Preserve all returned originals, with the same version/hash protections as collection.
        writer([raw])
        fresh['checkedAt']=now.isoformat()
        offer,status=review_by_id.get(old['id'],(None,None))
        if fresh['object']!=old['object'] or fresh['additionalInfo']!=old.get('additionalInfo',''):
            changed.add(old['id']);offer,status=None,None
        result.append((fresh,offer,status))
    if cards and not result:raise ValueError('PNCP verification unavailable')
    return result,changed,failures
