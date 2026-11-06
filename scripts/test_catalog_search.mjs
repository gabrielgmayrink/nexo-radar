import assert from 'node:assert/strict';
import { performance } from 'node:perf_hooks';
import { createSearchDocument,matchesSearch,parseSearchQuery } from '../web/src/search.ts';
import { createCatalogLoader } from '../web/src/catalog.ts';

const row={id:'12345678000100-1-000001/2026',object:'Serviços de tecnologia da informação e desenvolvimento de sistemas',additionalInfo:'Capacitação por ensino a distância',organization:'Prefeitura de São João',city:'Belo Horizonte',state:'MG',evidence:[]};
const document=createSearchDocument(row);
for (const query of ['SISTEMAS horizonte','MG','000001/2026','TI EAD','"desenvolvimento de sistemas" -equipamentos','-equipamentos']) assert.equal(matchesSearch(document,parseSearchQuery(query)),true,query);
for (const query of ['sistemas -informação','"sistemas desenvolvimento"','-"desenvolvimento de sistemas"']) assert.equal(matchesSearch(document,parseSearchQuery(query)),false,query);
assert.equal(matchesSearch(createSearchDocument({object:'Atividades sociais'}),parseSearchQuery('TI')),false);

const fixture={collectionDate:'2026-11-06',metrics:{unique:125,candidates:125,discarded:0},total:125,opportunities:Array.from({length:125},(_,i)=>({...row,id:String(i)}))};
let calls=0,time=0,offline=false;
const load=createCatalogLoader(async url=>{
  calls++;
  assert.equal(url,'/api/opportunities?bulk=1');
  return new Response(JSON.stringify(offline?{error:'offline'}:fixture),{status:offline?503:200});
},()=>time);
assert.equal((await load(new AbortController().signal)).opportunities.length,125);
assert.equal(calls,1);
await load(new AbortController().signal);assert.equal(calls,1);
await load(new AbortController().signal,true);assert.equal(calls,2);
offline=true;time=25000;
const previous=await load(new AbortController().signal);
assert.equal(previous.opportunities.length,125);assert.equal(previous.stale,true);assert.equal(calls,3);
const aborted=new AbortController();aborted.abort();
await assert.rejects(load(aborted.signal),{name:'AbortError'});assert.equal(calls,3);
let fallbackCalls=0;
const fallback=createCatalogLoader(async url=>{
  fallbackCalls++;
  return new Response(JSON.stringify(url.startsWith('/api/')?{...fixture,total:999}:{...fixture,total:125}));
});
assert.equal((await fallback(new AbortController().signal)).fallback,true);
assert.equal(fallbackCalls,2);
console.log(JSON.stringify({searchPhrases:true,exclusions:true,acronyms:true,oneCatalogRequest:true,memoryCache:true,failedRefreshKeepsResults:true,abortDoesNotFetch:true,incompleteCatalogDetected:true}));

if (process.argv.includes('--benchmark')) {
  const rows=Array.from({length:10000},(_,i)=>({...row,id:String(i)}));
  const queries=['sistemas horizonte','prefeitura informação','MG capacitação','TI -equipamentos'].map(parseSearchQuery);
  let start=performance.now(),baselineCount=0;
  for (const query of queries) baselineCount+=rows.filter(item=>matchesSearch(createSearchDocument(item),query)).length;
  const repeated=performance.now()-start;
  start=performance.now();const index=rows.map(createSearchDocument);const construction=performance.now()-start;
  start=performance.now();let indexedCount=0;
  for (const query of queries) indexedCount+=index.filter(item=>matchesSearch(item,query)).length;
  const indexed=performance.now()-start;
  assert.equal(indexedCount,baselineCount);
  console.log(JSON.stringify({benchmark:{records:rows.length,queries:queries.length,repeatedNormalizationMs:+repeated.toFixed(1),indexConstructionMs:+construction.toFixed(1),indexedQueriesMs:+indexed.toFixed(1)}}));
}
