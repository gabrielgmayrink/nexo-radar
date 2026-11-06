import type { Row } from './opportunities';
export type Catalog = { collectionDate: string; metrics: { unique: number; candidates: number; discarded: number }; opportunities: Row[]; total?: number; fallback?: boolean; stale?: boolean };
export function createCatalogLoader(fetcher: typeof fetch = fetch,clock: () => number = Date.now) {
  let cached: { value: Catalog; time: number } | null=null;
  function validate(value: Catalog) {
    if (!value || !Array.isArray(value.opportunities) || value.opportunities.length>10000 || !value.metrics || !value.opportunities.every(row => row && typeof row.id==='string' && typeof row.object==='string' && Array.isArray(row.evidence))) throw Error('O servidor retornou um catálogo inválido.');
    if (new Set(value.opportunities.map(row => row.id)).size!==value.opportunities.length) throw Error('O catálogo contém identificadores repetidos.');
    if (value.total!==undefined && value.total!==value.opportunities.length) throw Error('O catálogo não foi recebido por completo.');
    return value;
  }
  return async (signal: AbortSignal,force=false): Promise<Catalog> => {
    signal.throwIfAborted();
    if (!force && cached && clock()-cached.time<20000) return cached.value;
    try {
      const response=await fetcher('/api/opportunities?bulk=1',{signal,cache:'no-store'});
      if (!response.ok) throw Error('Não foi possível atualizar as oportunidades.');
      const value=validate(await response.json());
      signal.throwIfAborted();
      cached={value,time:clock()};
      return value;
    } catch (error) {
      if (signal.aborted) throw error;
      if (cached) { cached.value={...cached.value,stale:true}; return cached.value; }
      const response=await fetcher('/catalog.json',{signal});
      if (!response.ok) throw Error('Não foi possível carregar o catálogo. Tente novamente.');
      return {...validate(await response.json()),fallback:true};
    }
  };
}
export const fetchCatalog=createCatalogLoader();
