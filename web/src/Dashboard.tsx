import { useDeferredValue, useEffect, useMemo, useRef, useState } from 'react';
import { ChevronDown, ChevronLeft, ChevronRight, Download, LogIn, Menu, RefreshCw, RotateCcw, SearchX } from 'lucide-react';
import { motion } from 'motion/react';
import Sidebar from './Sidebar';
import CollectionStatus from './CollectionStatus';
import TeamAccess from './TeamAccess';
import SummaryNavigation from './SummaryNavigation';
import SearchFilters from './SearchFilters';
import OpportunityCard from './OpportunityCard';
import OpportunityDetails from './OpportunityDetails';
import ReviewForm from './ReviewForm';
import LearningPanel from './LearningPanel';
import CompanySetup from './CompanySetup';
import { companies as companyProfiles } from '../../src/radar/companies.json';
import { useTeam } from './useTeam';
import { createCatalogLoader, type Catalog } from './catalog';
import { createSearchDocument, parseSearchQuery } from './search';
import { EMPTY_FILTERS, VIEWS, matchesFilters, matchesView, parseDate, productScore, type Filters, type Review, type Row, type View } from './opportunities';

function saved(key: string): Record<string,Review> {
  try { const data = JSON.parse(sessionStorage.getItem(key) || '{}'); return data && typeof data === 'object' && !Array.isArray(data) ? data : {}; }
  catch { return {}; }
}
export default function Dashboard({company,companies,email,onCompany}: {company:string;companies:string[];email:string;onCompany:(company:string)=>void}) {
  const draftKey='nexo-radar-drafts:'+company+':'+email;
  const companyName=companyProfiles.find(profile=>profile.id===company)?.name || '';
  const configurationPending=!companyProfiles.some(profile=>profile.id===company && profile.enabled);
  const fetchCatalog=useMemo(()=>createCatalogLoader(),[]);
  const [catalog,setCatalog] = useState<Catalog|null>(null), [error,setError] = useState('');
  const [filters,setFilters] = useState<Filters>(EMPTY_FILTERS), [view,setView] = useState<View>('all');
  const [sort,setSort] = useState('deadline'), [page,setPage] = useState(1), [selected,setSelected] = useState<Row|null>(null);
  const [pageSize,setPageSize] = useState(12);
  const deferredQuery=useDeferredValue(filters.query);
  const effectiveFilters=useMemo(() => ({...filters,query:deferredQuery}),[filters,deferredQuery]);
  const searchPending=deferredQuery!==filters.query;
  const [drafts,setDrafts] = useState(()=>saved(draftKey)), [reviewMessage,setReviewMessage] = useState(''), [savingReview,setSavingReview] = useState(false);
  const [checking,setChecking] = useState(false), [checkError,setCheckError] = useState('');
  const [reviewIntent,setReviewIntent] = useState(false);
  const [collapsed,setCollapsed] = useState(() => { try { return localStorage.getItem('nexo-radar-menu-v1') === 'true'; } catch { return false; } });
  const [mobileOpen,setMobileOpen] = useState(false), [filtersOpen,setFiltersOpen] = useState(false), [loadVersion,setLoadVersion] = useState(0);
  const [now,setNow] = useState(Date.now);
  const searchRef = useRef<HTMLInputElement>(null), detailTriggerRef = useRef<HTMLElement>(null), menuTriggerRef = useRef<HTMLButtonElement>(null);
  const team = useTeam(company);
  const feedback = useMemo(() => ({ ...Object.fromEntries(Object.entries(team.reviews).filter(([,review])=>review.sourceCurrent!==false)),...drafts }),[team.reviews,drafts]);
  const rows = useMemo(() => catalog?.opportunities || [],[catalog]);
  const rowIndex=useMemo(() => new Map(rows.map(row => [row.id,{document:createSearchDocument(row),deadline:parseDate(row.proposalDeadline)?.getTime() ?? Infinity,published:parseDate(row.publishedAt)?.getTime() ?? 0}])),[rows]);
  const clauses=useMemo(() => parseSearchQuery(deferredQuery),[deferredQuery]);
  const scoped = useMemo(() => rows.filter(row => matchesFilters(row,effectiveFilters,feedback[row.id],now,{document:rowIndex.get(row.id)!.document,clauses})),[rows,effectiveFilters,feedback,now,rowIndex,clauses]);
  const counts = useMemo(() => {
    const keys=Object.keys(VIEWS) as View[];
    const result=Object.fromEntries(keys.map(key => [key,0]));
    for (const row of scoped) for (const key of keys) if (matchesView(row,key,feedback[row.id],now,filters.product)) result[key]++;
    return result;
  },[scoped,feedback,now,filters.product]);
  const filtered = useMemo(() => scoped.filter(row => matchesView(row,view,feedback[row.id],now,filters.product)).sort((a,b) =>
    (sort === 'value' ? (b.estimatedValue || 0)-(a.estimatedValue || 0) : sort === 'published' ? rowIndex.get(b.id)!.published-rowIndex.get(a.id)!.published :
    sort === 'deadline' ? rowIndex.get(a.id)!.deadline-rowIndex.get(b.id)!.deadline : productScore(b,filters.product)-productScore(a,filters.product)) || a.id.localeCompare(b.id)),[scoped,view,feedback,sort,now,filters.product,rowIndex]);
  const pages = Math.max(1,Math.ceil(filtered.length/pageSize)), current = Math.min(page,pages);

  useEffect(() => { const timer = window.setInterval(() => setNow(Date.now()),60000); return () => clearInterval(timer); },[]);
  useEffect(() => { const media = window.matchMedia('(min-width: 901px)'); const close = () => { if (media.matches) setMobileOpen(false); }; media.addEventListener('change',close); return () => media.removeEventListener('change',close); },[]);
  useEffect(() => { const refresh = () => setLoadVersion(value => value+1); window.addEventListener('radar:refresh',refresh); return () => window.removeEventListener('radar:refresh',refresh); },[]);
  useEffect(() => { setError(''); const controller = new AbortController(); fetchCatalog(controller.signal,loadVersion>0,company).then(data => { if(controller.signal.aborted)return; setCatalog(data); window.dispatchEvent(new CustomEvent('radar:catalog-ready',{detail:{fallback:!!data.fallback,stale:!!data.stale,count:data.opportunities.length}})); }).catch(error => { if (error.name !== 'AbortError') {setError(error.message);window.dispatchEvent(new Event('radar:catalog-error'));} }); return () => controller.abort(); },[loadVersion,company,fetchCatalog]);
  useEffect(() => { setPage(1); },[effectiveFilters,view,sort,pageSize]);
  useEffect(() => { try { sessionStorage.setItem(draftKey,JSON.stringify(drafts)); } catch { setError('Não foi possível salvar o rascunho no navegador. Publique sua avaliação ou exporte a seleção.'); } },[drafts,draftKey]);

  function changeFilters(change: Partial<Filters>) { setFilters(current => ({ ...current,...change })); }
  function focusResults() { requestAnimationFrame(() => { const results = document.getElementById('results'); results?.scrollIntoView({ block: 'start', behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' }); results?.focus({ preventScroll: true }); }); }
  function selectView(next: View) { setView(next); focusResults(); }
  function toggleCollapsed() { const next = !collapsed; setCollapsed(next); try { localStorage.setItem('nexo-radar-menu-v1',String(next)); } catch { /* Menu remains usable. */ } }
  function update(id: string,change: Partial<Review>) { setDrafts(current => { const base = current[id] || feedback[id] || { offer: '',reason: '',status: 'Nova',reasonCode: '',expectedScope: '' }; return { ...current,[id]: { ...base,...change } }; }); }
  function openDetails(row: Row,trigger: HTMLElement,decision?: 'yes'|'no') {
    detailTriggerRef.current = trigger; setCheckError(''); setReviewMessage(''); setReviewIntent(!!decision); setSelected(row);
    if (decision) update(row.id,decision === 'no' ? { offer: 'Nenhuma',status: 'Descartada',reasonCode: '' } : { offer: ['Public','Gerico','Ambas'].includes(row.suggestedOffer) ? row.suggestedOffer : companyName,status: 'Em avaliação',reasonCode: 'aderente' });
  }
  async function saveShared(row: Row) {
    const review = feedback[row.id]; if (!review) return;
    setSavingReview(true); setReviewMessage('');
    try {
      await team.save(row.id,review,row);
      setDrafts(current => { if (JSON.stringify(current[row.id]) !== JSON.stringify(review)) return current; const next = { ...current }; delete next[row.id]; return next; });
      setReviewMessage('Avaliação publicada. O exemplo já faz parte da memória da equipe.');
      setLoadVersion(value => value+1);
    } catch (error) { setReviewMessage(error instanceof Error ? error.message : 'Não foi possível publicar.'); }
    finally { setSavingReview(false); }
  }
  function useShared(id: string) { setDrafts(current => { const next = { ...current }; delete next[id]; return next; }); }
  async function refresh(row: Row) {
    setChecking(true); setCheckError('');
    try { const response = await fetch('/api/detail?id='+encodeURIComponent(row.id)+'&company='+encodeURIComponent(company)); const data = await response.json(); if (!response.ok) throw Error(data.error || 'Falha ao consultar PNCP'); const next = { ...row,...data,learning:data.object!==row.object || data.additionalInfo!==row.additionalInfo ? undefined : row.learning }; setSelected(current => current?.id === row.id ? next : current); setCatalog(current => current ? { ...current,opportunities: current.opportunities.map(item => item.id === row.id ? next : item) } : current); }
    catch (error) { setCheckError(error instanceof Error ? error.message : 'Falha ao consultar PNCP'); }
    finally { setChecking(false); }
  }
  function download() {
    const data = [['PNCP','Oferta sugerida','Pontuação de regra','Revisão humana','Motivo','Status','Objeto','Órgão','UF','Valor','Encerramento','Link'],...filtered.map(row => [row.id,row.suggestedOffer,row.score,feedback[row.id]?.offer || '',feedback[row.id]?.reason || '',feedback[row.id]?.status || '',row.object,row.organization,row.state,row.estimatedValue ?? '',row.proposalDeadline,row.pncpUrl])];
    const csv = data.map(line => line.map(value => '"'+String(value).replace(/^[=+@-]/,"'$&").replaceAll('"','""')+'"').join(';')).join('\r\n');
    const url = URL.createObjectURL(new Blob(['\uFEFF'+csv],{ type: 'text/csv;charset=utf-8' })); const link = document.createElement('a'); link.href = url; link.download = 'radar-licitacoes.csv'; link.click(); setTimeout(() => URL.revokeObjectURL(url),1000);
  }
  return <div className={'radar-app'+(collapsed ? ' menu-collapsed' : '')}>
    <a className="skip-link" href="#results">Ir para oportunidades</a>
    <Sidebar company={company} companies={companies} onCompany={onCompany} triggerRef={menuTriggerRef} collapsed={collapsed} mobileOpen={mobileOpen} blocked={!!selected} view={view} counts={counts} onCollapse={toggleCollapsed} onClose={() => setMobileOpen(false)} onView={selectView}/>
    <main className="workspace" inert={mobileOpen || !!selected}>
      <header className="workspace-header"><div className="header-navigation"><button ref={menuTriggerRef} className="icon-button menu-trigger" aria-label="Abrir menu" aria-expanded={mobileOpen} aria-controls="workspace-navigation" onClick={() => setMobileOpen(true)}><Menu size={22}/></button><span className="breadcrumb">Nexo Radar <b>/</b> Oportunidades</span></div><div><span className="snapshot-label">{configurationPending ? 'EM CONFIGURAÇÃO' : catalog?.collectionDate ? 'BASE DE ' + catalog.collectionDate.split('-').reverse().join('/') : 'FONTE OFICIAL · PNCP'}</span>{!team.authenticated && <button className="workspace-login" onClick={() => window.dispatchEvent(new Event('nexo:login'))}><LogIn size={15}/><span>Entrar na equipe</span></button>}</div></header>
      <motion.section className="page-title" initial={{opacity:0,y:10}} animate={{opacity:1,y:0}} transition={{duration:.4}}><div className="heading-row"><div><span className="overline">INTELIGÊNCIA EM OPORTUNIDADES</span><h1>Encontre. Analise. <em>Decida.</em></h1><p>As oportunidades certas para sua empresa. O contexto que sua equipe precisa para avançar.</p></div><button className="primary-button" disabled={!filtered.length} onClick={download}><Download size={16}/> Exportar seleção</button></div></motion.section>
      <CompanySetup company={company}/>
      {!configurationPending && <CollectionStatus collectionDate={catalog?.collectionDate} totalScanned={catalog?.metrics.unique}/>}
      {catalog?.fallback && !configurationPending && <p className="team-warning" role="status">A consulta ao servidor falhou. Exibindo a última cópia disponível. Atualize o painel para tentar novamente.</p>}
      {catalog?.stale && <p className="team-warning" role="status">Não foi possível atualizar agora. Mantivemos as oportunidades já carregadas para você continuar pesquisando.</p>}
      <TeamAccess enabled={team.enabled} email={team.email || undefined} reload={team.reload}/>{team.error && <p className="team-warning" role="status">{team.error}</p>}
      {error && <div className="error-message" role="alert">{error}{!catalog && <button className="secondary-button" onClick={() => setLoadVersion(value => value+1)}><RotateCcw size={15}/> Tentar novamente</button>}</div>}
      <SummaryNavigation counts={counts} view={view} onSelect={selectView} loading={!catalog}/>
      <section id="results" className="results-section" tabIndex={-1} aria-label="Resultados da busca" aria-busy={(!catalog && !error) || searchPending}>
        <div className="results-title"><div><span className="overline">{view === 'learning' ? 'MELHORIA CONTÍNUA' : 'LISTA SELECIONADA'}</span><h2>{VIEWS[view].label} {view !== 'learning' && <span>{filtered.length}</span>}</h2><p className="view-description">{VIEWS[view].description}</p></div>
          {view !== 'learning' && <label className="sort-label">Ordenar por <span className="sort-select"><select value={sort} onChange={event => setSort(event.target.value)}><option value="deadline">Prazo mais próximo</option><option value="score">Sinais de aderência</option><option value="published">Publicação recente</option><option value="value">Maior valor</option></select><ChevronDown size={14}/></span></label>}
        </div>
        {view === 'learning' ? <LearningPanel authenticated={team.authenticated} reviews={team.reviews}/> : <>
          <SearchFilters companyName={companyName} filters={filters} rows={rows} onChange={changeFilters} open={filtersOpen} onToggle={() => setFiltersOpen(value => !value)} searchRef={searchRef} total={filtered.length} pending={searchPending}/>
          {!catalog && !error ? <div className="loading-state" role="status"><RefreshCw className="spinning" size={20}/><p>Buscando suas oportunidades…</p><div className="skeleton-grid" aria-hidden="true">{[0,1,2,3].map(key => <div className="skeleton-card" key={key}/>)}</div></div> : !catalog ? null : !filtered.length ? <div className="zero-state"><SearchX size={32}/><h3>{filters.query ? 'Nenhuma licitação para esta busca' : 'Nenhum resultado nesta seleção'}</h3><p>{view!=='all' && counts.all>0 ? `Há ${counts.all} oportunidades em outras listas com estes filtros.` : 'Tente palavras mais gerais ou remova um filtro. Ao ampliar a lista, sua busca será preservada.'}</p><div className="empty-actions">{view!=='all' && <button className="secondary-button" onClick={() => setView('all')}>Buscar em todas as oportunidades</button>}<button className="secondary-button" onClick={() => { setFilters(EMPTY_FILTERS); setView('all'); }}>Limpar filtros</button></div></div> : <div className="cards-grid">{filtered.slice((current-1)*pageSize,current*pageSize).map(row => <OpportunityCard key={row.id} row={row} review={feedback[row.id]} product={filters.product} onOpen={(trigger,decision) => openDetails(row,trigger,decision)}/>)}</div>}
          <nav className="pager" aria-label="Paginação de oportunidades"><span>{filtered.length ? `${(current-1)*pageSize+1}–${Math.min(current*pageSize,filtered.length)} de ${filtered.length}` : '0 resultados'} <span className="page-number">· Página {current} de {pages}</span></span><div className="pager-controls"><label className="page-size">Por página <select aria-label="Licitações por página" value={pageSize} onChange={event => setPageSize(Number(event.target.value))}>{[12,24,48].map(size => <option key={size} value={size}>{size}</option>)}</select></label><button disabled={current<=1} onClick={() => { setPage(current-1); focusResults(); }}><ChevronLeft size={14}/> Anterior</button><button disabled={current>=pages} onClick={() => { setPage(current+1); focusResults(); }}>Próxima <ChevronRight size={14}/></button><button className="back-to-search" onClick={() => searchRef.current?.focus()}>↑ Voltar à busca</button></div></nav>
        </>}
      </section>
      <footer className="workspace-footer"><span>NEXO RADAR · INTELIGÊNCIA EM OPORTUNIDADES</span><span>Confira o edital oficial antes de participar.</span></footer>
    </main>
    {selected && <OpportunityDetails row={selected} checking={checking} checkError={checkError} reviewIntent={reviewIntent} onClose={() => setSelected(null)} onRefresh={() => void refresh(selected)} triggerRef={detailTriggerRef}>
      <ReviewForm companyName={companyName} row={selected} review={feedback[selected.id]} shared={team.reviews[selected.id]} draft={!!drafts[selected.id]} authenticated={team.authenticated} busy={savingReview} message={reviewMessage} onChange={change => update(selected.id,change)} onSave={() => void saveShared(selected)} onReload={() => void team.reload()} onUseShared={() => useShared(selected.id)}/>
    </OpportunityDetails>}
  </div>;
}
