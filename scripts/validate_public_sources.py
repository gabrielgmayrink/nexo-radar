"""Bounded live acceptance checks. Never loads credentials or writes the app database."""
import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

from radar.canonical import to_card
from radar.identifiers import parse_pncp_id
from radar.sources.http import PublicHTTP, SourceError
from radar.sources import PNCPDetailsConnector, ComprasGovConnector
from radar.verification import fetch_record


def run(output):
    http=PublicHTTP(pause=1)
    evidence=[]; samples=[]
    def check(name, action):
        started=time.monotonic()
        try:
            detail=action()
            result={'name':name,'ok':True,'detail':detail}
        except Exception as exc:
            result={'name':name,'ok':False,'error':getattr(exc,'code',type(exc).__name__)}
        result['elapsedMs']=round((time.monotonic()-started)*1000)
        evidence.append(result);print(json.dumps(result,ensure_ascii=True),flush=True)
    def listing(mode,page=1,**params):
        url='https://pncp.gov.br/api/consulta/v1/contratacoes/'+mode+'?'+urlencode({'pagina':page,'tamanhoPagina':50,**params})
        data=http.json(url,max_bytes=4_000_000,timeout=15,attempts=1)
        assert isinstance(data,dict) and isinstance(data.get('data'),list)
        rows=data['data'];ids=[parse_pncp_id(row['numeroControlePNCP']).canonical for row in rows]
        assert len(ids)==len(set(ids))
        for row in rows:
            if len(samples)<6 and row.get('unidadeOrgao',{}).get('ufSigla') not in [s.get('unidadeOrgao',{}).get('ufSigla') for s in samples]:samples.append(row)
        return {'url':url,'received':len(rows),'sourceTotal':data.get('totalRegistros'),'sourcePages':data.get('totalPaginas'),
                'idsHash':hashlib.sha256(json.dumps(ids).encode()).hexdigest(),'ids':ids[:3]}
    check('pncp_open_page_1',lambda:listing('proposta',dataFinal='99991231'))
    check('pncp_open_page_2',lambda:listing('proposta',page=2,dataFinal='99991231'))
    for mode in ('publicacao','atualizacao'):
        check('pncp_'+mode,lambda mode=mode:listing(mode,dataInicial='20251101',dataFinal='20251107',codigoModalidadeContratacao=6))
    check('modalities',lambda:{'ids':[r['id'] for r in http.json('https://pncp.gov.br/api/pncp/v1/modalidades')]})
    for sample in samples[:4]:
        identifier=sample['numeroControlePNCP']
        def compare(sample=sample,identifier=identifier):
            fresh=fetch_record(identifier,timeout=12)
            card=to_card(fresh)
            assert card['id']==identifier and card['object']==fresh['objetoCompra']
            assert card['state']==fresh.get('unidadeOrgao',{}).get('ufSigla','')
            assert card['organization']==fresh.get('orgaoEntidade',{}).get('razaoSocial','')
            return {'id':identifier,'uf':card['state'],'city':card['city'],'officialUrl':card['pncpUrl'],
                    'valueMissing':fresh.get('valorTotalEstimado') is None,'deadlineMissing':not card['proposalDeadline'],
                    'status':fresh.get('situacaoCompraId'),'listVersionChanged':sample.get('dataAtualizacaoGlobal')!=fresh.get('dataAtualizacaoGlobal')}
        check('pncp_detail_'+identifier,compare)
    historical='00394502000144-1-010615/2025'
    details=PNCPDetailsConnector(http)
    for kind in ('itens','arquivos'):
        check('pncp_'+kind,lambda kind=kind:{'received':len(details.page(historical,kind)['rows'])})
    compras=ComprasGovConnector(http)
    for name,fn in (('compras_detail',compras.details),('compras_items',compras.items)):
        check(name,lambda fn=fn:{'received':len(fn(historical)[0]),'identity':historical})
    # Results are read from the same documented exact-ID route contract.
    check('compras_results',lambda:{'received':len(compras._by_id('3.1_consultarResultadoItensContratacoes_PNCP_14133_Id',historical)[0])})
    report={'checkedAt':datetime.now(timezone.utc).isoformat(),'scope':'bounded_live_samples_not_full_coverage',
            'checks':evidence,'passed':sum(c['ok'] for c in evidence),'failed':sum(not c['ok'] for c in evidence),
            'notObserved':['actual_source_timeout','actual_rate_limiting','suspension_or_deadline_change_not_guaranteed_in_sample']}
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf8')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=Path('.local/live-sources.json'))
    args=p.parse_args();result=run(args.output)
    raise SystemExit(1 if result['failed'] else 0)
