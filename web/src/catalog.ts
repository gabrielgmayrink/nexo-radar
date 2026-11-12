import type { Review, Row } from './opportunities';
export type CompanyProfile = { id: string; name: string; enabled: boolean; services: string[]; terms: string[]; excludeTerms: string[]; synonyms?: Record<string,string[]>; states?: string[]; cities?: string[]; modalities?: string[]; minValue?: number|null; maxValue?: number|null };
export type Catalog = { collectionDate: string; metrics: { unique: number; candidates: number; discarded: number }; opportunities: Row[]; total?: number; page?: number; pages?: number; limit?: number; paginated?: boolean; counts?: Record<string,number>; facets?: {states:Record<string,number>;modalities:string[]}; pageReviews?: Record<string,Review>; profile?: CompanyProfile; classification?: {version:string;pendingRecords:number;complete:boolean}; fallback?: boolean; stale?: boolean };
export function createCatalogLoader(fetcher: typeof fetch = fetch,clock: () => number = Date.now) {
  const cached=new Map<string,{value:Catalog;time:number}>();
  function validate(value: Catalog) {
    if (!value || !Array.isArray(value.opportunities) || value.opportunities.length>100 || !value.metrics || !value.opportunities.every(row => row && typeof row.id==='string' && typeof row.object==='string' && Array.isArray(row.evidence))) throw Error('O servidor retornou uma página inválida.');
    if (new Set(value.opportunities.map(row => row.id)).size!==value.opportunities.length) throw Error('A página contém identificadores repetidos.');
    if (value.total!==undefined && (!Number.isSafeInteger(value.total) || value.total<value.opportunities.length)) throw Error('A contagem de resultados é inválida.');
    return value;
  }
  return async (signal: AbortSignal,force=false,company='public',parameters: Record<string,string>={}): Promise<Catalog> => {
    signal.throwIfAborted();
    const query=new URLSearchParams({page:'1',limit:'24',...parameters,company});query.sort();const key=query.toString();
    const previous=cached.get(key);
    if (!force && previous && clock()-previous.time<20000) return previous.value;
    try {
      const response=await fetcher('/api/opportunities?'+key,{signal,cache:'no-store'});
      if (response.status===401 || response.status===403) {cached.clear();if(typeof window!=='undefined')window.dispatchEvent(new Event('nexo:session'));throw Error('Entre na conta autorizada para acessar esta empresa.');}
      if (!response.ok) throw Error('Não foi possível atualizar as oportunidades.');
      const value=validate(await response.json());signal.throwIfAborted();
      if(cached.size>=8)cached.delete(cached.keys().next().value!);
      cached.set(key,{value,time:clock()});return value;
    } catch (error) {
      if(signal.aborted)throw error;
      const available=cached.get(key);
      if(available)return {...available.value,stale:true};
      throw error;
    }
  };
}
