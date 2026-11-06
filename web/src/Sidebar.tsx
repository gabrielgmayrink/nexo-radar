import { useEffect, useRef, type RefObject } from 'react';
import { ArrowUpRight, BookmarkCheck, NotebookPen, CalendarClock, ListChecks, Building2, CircleHelp, LayoutGrid, PanelLeftClose, PanelLeftOpen, ShieldCheck, ArchiveX, X } from 'lucide-react';
import { Brand } from './Brand';
import { useDialogFocus } from './useDialogFocus';
import { VIEWS, type View } from './opportunities';

const views = [
  { key: 'all', icon: LayoutGrid },
  { key: 'open', icon: CalendarClock },
  { key: 'matches', icon: ListChecks },
  { key: 'review', icon: CircleHelp },
  { key: 'tracked', icon: BookmarkCheck },
  { key: 'dismissed', icon: ArchiveX },
  { key: 'learning', icon: NotebookPen },
] as const;

type Props = {
  company: string; companies: string[]; onCompany:(company:string)=>void;
  triggerRef: RefObject<HTMLButtonElement | null>; collapsed: boolean; mobileOpen: boolean; blocked: boolean; view: View; counts: Record<string,number>;
  onCollapse: () => void; onClose: () => void;
  onView: (view: View) => void;
};

export default function Sidebar({ company, companies, onCompany, triggerRef, collapsed, mobileOpen, blocked, view, counts, onCollapse, onClose, onView }: Props) {
  const ref = useRef<HTMLElement>(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  useDialogFocus(mobileOpen, ref, triggerRef);
  useEffect(() => {
    if (!mobileOpen) return;
    const close = (event: KeyboardEvent) => { if (event.key === 'Escape') closeRef.current(); };
    document.addEventListener('keydown', close);
    return () => document.removeEventListener('keydown', close);
  }, [mobileOpen]);

  return <>
    {mobileOpen && <div className="navigation-backdrop" aria-hidden="true" onClick={onClose} />}
    <aside id="workspace-navigation" className={'rail' + (mobileOpen ? ' mobile-open' : '')} ref={ref}
      role={mobileOpen ? 'dialog' : undefined} aria-modal={mobileOpen || undefined}
      aria-label="Navegação do Radar" tabIndex={-1} inert={blocked}>
      <div className="rail-brand"><Brand /><button className="icon-button mobile-close" onClick={onClose} aria-label="Fechar menu"><X size={20} /></button></div>
      <button className="collapse-button" onClick={onCollapse} aria-expanded={!collapsed} aria-controls="workspace-navigation" aria-label={collapsed ? 'Expandir menu' : 'Recolher menu'} title={collapsed ? 'Expandir menu' : 'Recolher menu'}>
        {collapsed ? <PanelLeftOpen size={19} /> : <PanelLeftClose size={19} />}<span>Recolher menu</span>
      </button>
      <nav aria-label="Oportunidades">
        <p className="nav-caption">ESPAÇO DE TRABALHO</p>
        {views.map(({ key, icon: Icon }) => <button key={key} className={'rail-link ' + (view === key ? 'chosen' : '')}
          aria-current={view === key ? 'page' : undefined} aria-label={VIEWS[key].label} title={collapsed ? VIEWS[key].label : undefined}
          onClick={() => { onView(key); onClose(); }}><span><Icon /></span><span className="nav-text">{VIEWS[key].label}</span>{key!=='learning'&&<span className="nav-count" aria-hidden="true">{counts[key]||0}</span>}</button>)}
        <p className="nav-caption">{companies.length>1?'ADMINISTRAÇÃO':'SUA EMPRESA'}</p>
        {companies.map(id=><button key={id} className={'rail-link '+(id===company?'product-selected':'')} aria-pressed={id===company} onClick={()=>{onCompany(id);onClose();}} title={collapsed?(id==='public'?'Public':'Gerico'):undefined}>
          <span className="product-nav-icon"><Building2/></span><span className="nav-text">{id==='public'?'Public':'Gerico'}</span>
        </button>)}
      </nav>
      <div className="rail-footer"><b><ShieldCheck size={15} /> Fonte oficial · PNCP</b><p>Dados oficiais para decisões bem fundamentadas.</p><a href="https://pncp.gov.br/app/editais" target="_blank" rel="noreferrer">Consultar portal <ArrowUpRight size={14} /></a></div>
    </aside>
  </>;
}
