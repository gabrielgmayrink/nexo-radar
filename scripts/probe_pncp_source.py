"""Read-only transport diagnostic; no credentials or procurement objects are logged."""
import json
import time
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError

started=time.monotonic()
url='https://pncp.gov.br/api/consulta/v1/contratacoes/proposta?dataFinal=99991231&pagina=1&tamanhoPagina=50'
try:
    with urlopen(Request(url,headers={'Accept':'application/json','User-Agent':'NexoRadar/1.0 (public procurement collection)'}),timeout=60) as response:
        data=json.load(response)
    print(json.dumps({'directSource':True,'http':200,'records':len(data['data']),'total':data.get('totalRegistros'),'pages':data.get('totalPaginas'),'elapsedSeconds':round(time.monotonic()-started,2)}))
except (HTTPError,URLError,TimeoutError) as exc:
    print(json.dumps({'directSource':False,'http':getattr(exc,'code',None),'errorType':type(exc).__name__,'elapsedSeconds':round(time.monotonic()-started,2)}))
    raise SystemExit(1)
