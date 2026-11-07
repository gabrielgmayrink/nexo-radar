import { ChevronDown, LoaderCircle, Search, SlidersHorizontal, X } from 'lucide-react';
import { useEffect, useMemo, type RefObject } from 'react';
import { EMPTY_FILTERS, type Filters, type Row } from './opportunities';
import { BRAZIL_STATES, stateLabel } from './states';
const DEADLINES: Record<string, string> = { any: 'Qualquer prazo', '7': 'Próximos 7 dias', '15': 'Próximos 15 dias', '30': 'Próximos 30 dias', unknown: 'Prazo não informado' };
export default function SearchFilters({ companyName, filters, rows, onChange, open, onToggle, searchRef, total, pending=false }: {
  companyName: string; filters: Filters; rows: Row[]; onChange: (change: Partial<Filters>) => void; open: boolean; onToggle: () => void; searchRef: RefObject<HTMLInputElement | null>; total: number; pending?: boolean;
}) {
  const stateCounts=useMemo(() => {
    const counts=new Map<string,number>();
    for (const row of rows) counts.set(row.state,(counts.get(row.state) || 0)+1);
    return counts;
  },[rows]);
  const modalities=useMemo(() => [...new Set(rows.map(row => row.modality).filter(Boolean))].sort().map(value => [value,value]),[rows]);
  useEffect(() => {
    const shortcut=(event: KeyboardEvent) => {
      if (event.defaultPrevented || searchRef.current?.closest('[inert]')) return;
      const editing=event.target instanceof Element && !!event.target.closest('input,textarea,select,[contenteditable="true"]');
      if ((event.key==='/' && !editing) || (event.key.toLowerCase()==='k' && (event.ctrlKey || event.metaKey))) {
        event.preventDefault();searchRef.current?.focus();
      }
    };
    window.addEventListener('keydown',shortcut);
    return () => window.removeEventListener('keydown',shortcut);
  },[searchRef]);
  const active = (Object.keys(EMPTY_FILTERS) as (keyof Filters)[]).filter(key => filters[key] !== EMPTY_FILTERS[key]);
  const fields = [
    { key: 'product', label: 'Empresa', aria: 'Filtrar empresa', options: [['Todos',companyName]] },
    { key: 'deadline', label: 'Encerramento', aria: 'Filtrar encerramento', options: Object.entries(DEADLINES) },
    { key: 'modality', label: 'Modalidade', aria: 'Filtrar modalidade', options: [['Todas','Todas as modalidades'], ...modalities] },
    { key: 'assessment', label: 'Avaliação', aria: 'Filtrar avaliação', options: [['any','Todas as avaliações'],['unreviewed','Ainda não avaliadas'],['reviewed','Já avaliadas']] },
  ] as const;
  const chip = (key: keyof Filters) => key === 'uf' ? `Estado: ${stateLabel(filters.uf)}` : key === 'query' ? `Busca: ${filters.query}` : key === 'deadline' ? DEADLINES[filters.deadline] : key === 'assessment' ? filters.assessment === 'reviewed' ? 'Já avaliadas' : 'Ainda não avaliadas' : filters[key];
  return <div className="search-workbench">
    <div className="search-tools"><label className="search-field"><Search size={20}/><input ref={searchRef} type="search" aria-label="Buscar licitações" aria-describedby="search-guidance" autoComplete="off" spellCheck={false} maxLength={240} placeholder="Objeto, órgão, cidade, UF ou número PNCP" value={filters.query} onChange={event => onChange({ query: event.target.value })}/>
      {pending && <LoaderCircle className="spinning search-pending" size={16} aria-label="Atualizando busca"/>}
      {!filters.query && <kbd className="search-shortcut" title="Pressione / ou Ctrl+K para buscar">/</kbd>}
      {filters.query && <button type="button" className="clear-search" aria-label="Limpar busca" onClick={() => { onChange({ query: '' }); searchRef.current?.focus(); }}><X size={17}/></button>}
    </label><label className="state-filter"><span>Estado</span><span className="select-surface"><select aria-label="Filtrar estado" aria-describedby="state-filter-help" value={filters.uf} onChange={event => onChange({uf:event.target.value})}>
      <option value="Todas">Todos os estados</option>
      {BRAZIL_STATES.map(([uf]) => <option key={uf} value={uf}>{stateLabel(uf)} · {(stateCounts.get(uf) || 0).toLocaleString('pt-BR')}</option>)}
    </select><ChevronDown size={16} aria-hidden="true"/></span></label><button className="filter-toggle secondary-button" onClick={onToggle} aria-expanded={open} aria-controls="advanced-filters"><SlidersHorizontal size={17}/> Refinar busca{active.length > 0 && <span className="filter-count">{active.length}</span>}</button></div>
    <p id="state-filter-help" className="state-filter-help">As quantidades por estado consideram as oportunidades disponíveis para sua empresa.</p>
    <p id="search-guidance" className="search-help">Combine palavras, use <b>"aspas"</b> para uma expressão exata e <b>-palavra</b> para excluir. Acentos não alteram a busca.</p>
    {companyName==='Public' && <div className="search-suggestions" aria-label="Sugestões de busca"><span>Experimente</span>{['"apoio administrativo"','gestão pública','capacitação','EAD'].map(query => <button key={query} type="button" onClick={() => { onChange({query});searchRef.current?.focus(); }}>{query.replaceAll('"','')}</button>)}</div>}
    <div id="advanced-filters" className={'advanced-filters' + (open ? ' filters-open' : '')}>{fields.map(field => <label className="filter-field" key={field.key}>
      <span>{field.label}</span><span className="select-surface"><select aria-label={field.aria} value={filters[field.key]} onChange={event => onChange({ [field.key]: event.target.value })}>
        {field.options.map(([value,label]) => <option key={value} value={value}>{label}</option>)}
      </select><ChevronDown size={16} aria-hidden="true"/></span>
    </label>)}</div>
    <div className="active-filters"><span className="result-summary" role="status" aria-live="polite">{pending ? 'Atualizando resultados…' : `${total} ${total===1?'licitação nesta lista':'licitações nesta lista'}`}</span>
      {active.map(key => <button key={key} className="filter-chip" aria-label={'Remover filtro de ' + ({ product: 'empresa', uf: 'estado', query: 'busca', deadline: 'encerramento', modality: 'modalidade', assessment: 'avaliação' }[key])} onClick={() => onChange({ [key]: EMPTY_FILTERS[key] })}>{chip(key)}<X size={13}/></button>)}
      {!!active.length && <button className="reset-filters" onClick={() => onChange(EMPTY_FILTERS)}>Limpar filtros</button>}
    </div>
  </div>;
}
