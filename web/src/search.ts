type Searchable = { object: string; additionalInfo?: string; organization?: string; city?: string; state?: string; id?: string };
export type SearchDocument = { text: string; words: Set<string> };
export type SearchClause = { value: string; excluded: boolean; phrase: boolean };
const aliases: Record<string,string[]> = { ti:['ti','tecnologia da informacao','informatica','desenvolvimento de sistemas','desenvolvimento de software','fabrica de software'],ead:['ead','ensino a distancia','educacao a distancia'] };

export const normalizeSearch = (value: string) => value.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^\p{L}\p{N}]+/gu,' ').trim().replace(/\s+/g,' ');

export function createSearchDocument(row: Searchable): SearchDocument {
  const text=normalizeSearch([row.object,row.additionalInfo,row.organization,row.city,row.state,row.id].filter(Boolean).join(' '));
  return { text:' '+text+' ',words:new Set(text.split(' ').filter(Boolean)) };
}

export function parseSearchQuery(query: string): SearchClause[] {
  const clauses: SearchClause[]=[];
  for (const match of query.slice(0,240).matchAll(/(-?)"([^"]*)"|(-?)([^\s"]+)/g)) {
    const value=normalizeSearch(match[2] ?? match[4] ?? '');
    if (value) clauses.push({ value,excluded:(match[1] || match[3])==='-',phrase:match[2]!==undefined });
  }
  return clauses;
}

export function matchesSearch(document: SearchDocument,clauses: SearchClause[]) {
  return clauses.every(clause => {
    const candidates=clause.phrase ? [clause.value] : aliases[clause.value] || [clause.value];
    const matched=candidates.some(term => clause.phrase || term.includes(' ') ? document.text.includes(' '+term+' ') : term.length<=2 ? document.words.has(term) : document.text.includes(term));
    return clause.excluded ? !matched : matched;
  });
}
