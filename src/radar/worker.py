"""Resumable incremental collector with durable local SQLite state.

Run with an external scheduler; never use local SQLite inside a serverless function.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from radar.pncp import PNCPClient, CollectionMetrics, PUBLICATION_MODALITIES, PAGE_SIZE, page_count
from radar.build_catalog import build
from radar.relevance import TZ


def connect(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.executescript('''
      CREATE TABLE IF NOT EXISTS raw(id TEXT, hash TEXT, payload TEXT NOT NULL, collected TEXT NOT NULL, PRIMARY KEY(id,hash));
      CREATE TABLE IF NOT EXISTS opportunity(id TEXT PRIMARY KEY, payload TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS checkpoint(key TEXT PRIMARY KEY, day TEXT NOT NULL, page INTEGER NOT NULL, window_end TEXT);
      CREATE TABLE IF NOT EXISTS execution(id INTEGER PRIMARY KEY, started TEXT, finished TEXT, status TEXT, metrics TEXT);
    ''')
    return db


def run(database=Path('work/radar.sqlite'), output=Path('web/public/catalog.json'), days=2, max_pages=10000, client=None):
    client = client or PNCPClient()
    db, metrics, failures = connect(database), CollectionMetrics(), []
    completed = 0
    if days < 1 or days > 365 or max_pages < 1:
        db.close()
        raise ValueError('days must be 1..365 and max_pages must be positive')
    today = datetime.now(TZ).date()
    now = datetime.now(timezone.utc).isoformat()
    execution = db.execute('INSERT INTO execution(started,status) VALUES (?,?)', (now,'running')).lastrowid
    db.commit()
    for mode in ('publicacao','atualizacao'):
        for modality in PUBLICATION_MODALITIES:
            key = f'{mode}:{modality}'
            checkpoint = db.execute('SELECT day,page,window_end FROM checkpoint WHERE key=?',(key,)).fetchone()
            start = date.fromisoformat(checkpoint[0])-timedelta(days=1) if checkpoint else today-timedelta(days=days-1)
            # Resume the same window after failure; final checkpoints store page=0.
            page = checkpoint[1] if checkpoint and checkpoint[1] and checkpoint[2] == today.isoformat() else 1
            if (today-start).days > 364:
                failures.append({'partition':key,'error':'Checkpoint older than 365 days; backfill required'})
                continue
            try:
                seen = set()
                while page <= max_pages:
                    params = {'dataInicial':start.strftime('%Y%m%d'),'dataFinal':today.strftime('%Y%m%d'),'codigoModalidadeContratacao':modality,'pagina':page,'tamanhoPagina':PAGE_SIZE}
                    payload = client.get_page(f'/v1/contratacoes/{mode}',params,modality=modality,page=page,metrics=metrics)
                    records=payload['data']
                    total=page_count(payload,len(records),PAGE_SIZE)
                    if not records and total and page < total:
                        raise RuntimeError('Empty intermediate page')
                    fingerprint=hashlib.sha256(json.dumps(records,sort_keys=True).encode()).hexdigest()
                    if records and fingerprint in seen:
                        raise RuntimeError('Repeated page')
                    seen.add(fingerprint)
                    for record in records:
                        identifier=record.get('numeroControlePNCP')
                        if not identifier:
                            raise RuntimeError('Missing numeroControlePNCP')
                        raw=json.dumps(record,ensure_ascii=False,sort_keys=True)
                        digest=hashlib.sha256(raw.encode()).hexdigest()
                        db.execute('INSERT OR IGNORE INTO raw VALUES (?,?,?,?)',(identifier,digest,raw,now))
                        old = db.execute('SELECT payload FROM opportunity WHERE id=?',(identifier,)).fetchone()
                        old_version = json.loads(old[0]).get('dataAtualizacaoGlobal') or '' if old else ''
                        if not old or (record.get('dataAtualizacaoGlobal') or '') >= old_version:
                            db.execute('INSERT OR REPLACE INTO opportunity VALUES (?,?)',(identifier,raw))
                    done = not records or (total is not None and page>=total)
                    # Keep the original start on a partial partition so pagination is stable.
                    db.execute('INSERT OR REPLACE INTO checkpoint VALUES (?,?,?,?)',(key,today.isoformat() if done else (start+timedelta(days=1)).isoformat(),0 if done else page+1,today.isoformat()))
                    db.commit()
                    if done:
                        completed += 1
                        break
                    page+=1
                else:
                    raise RuntimeError('Page budget exhausted')
            except Exception as exc:
                db.rollback()
                failures.append({'partition':key,'error':str(exc)})
    if not completed:
        result={**metrics.summary(),'failures':failures}
        db.execute('UPDATE execution SET finished=?,status=?,metrics=? WHERE id=?',(datetime.now(timezone.utc).isoformat(),'failed',json.dumps(result),execution))
        db.commit(); db.close()
        return result
    # Replay from canonical rows, so website generation is independent of API availability.
    replay=database.parent/'catalog-replay.jsonl'
    with replay.open('w',encoding='utf-8') as stream:
        for payload, in db.execute('SELECT payload FROM opportunity'):
            stream.write(payload+'\n')
    temp=output.with_suffix('.tmp.json')
    build(replay,temp,collection_date=today.isoformat())
    catalog=json.loads(temp.read_text(encoding='utf-8'))
    catalog.update(collectionDate=today.isoformat(), historical=False)
    catalog['collectionFailures']=failures
    temp.write_text(json.dumps(catalog,ensure_ascii=False),encoding='utf-8')
    output.parent.mkdir(parents=True,exist_ok=True)
    temp.replace(output)
    result={**metrics.summary(),'failures':failures}
    db.execute('UPDATE execution SET finished=?,status=?,metrics=? WHERE id=?',(datetime.now(timezone.utc).isoformat(),'partial' if failures else 'ok',json.dumps(result),execution))
    db.commit();db.close()
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--database',type=Path,default=Path('work/radar.sqlite'))
    parser.add_argument('--output',type=Path,default=Path('web/public/catalog.json'))
    parser.add_argument('--days',type=int,default=2)
    args=parser.parse_args()
    result=run(args.database,args.output,args.days)
    print(json.dumps(result))
    raise SystemExit(1 if result['failures'] else 0)
