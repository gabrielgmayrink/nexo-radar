import { useEffect, useRef, type RefObject } from 'react';
import { ArrowUpRight, Bookmark, BookOpenCheck, Clock, FileCheck, Folders, HelpCircle, Layers, PanelLeftClose, PanelLeftOpen, ShieldCheck, Trash2, X } from 'lucide-react';
import { Brand } from './Brand';
import { useDialogFocus } from './useDialogFocus';
import { VIEWS, type View } from './opportunities';

const views = [
  { key: 'all', icon: Layers },
  { key: 'open', icon: Clock },
  { key: 'matches', icon: FileCheck },
  { key: 'review', icon: HelpCircle },
  { key: 'tracked', icon: Bookmark },
  { key: 'dismissed', icon: Trash2 },
  { key: 'learning', icon: BookOpenCheck },
] as const;

type Props = {
  triggerRef: RefObject<HTMLButtonElement | null>; collapsed: boolean; mobileOpen: boolean; blocked: boolean; view: View; product: string; counts: Record<string,number>;
  onCollapse: () => void; onClose: () => void;
  onView: (view: View) => void; onProduct: (product: string) => void;
};

export default function Sidebar({ triggerRef, collapsed, mobileOpen, blocked, view, product, counts, onCollapse, onClose, onView, onProduct }: Props) {
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
        <p className="nav-caption">SUAS EMPRESAS</p>
        {['Daltton', 'Gerico'].map(name => <button key={name} className={'rail-link ' + (product === name ? 'product-selected' : '')}
          aria-label={name} aria-pressed={product === name} title={collapsed ? name : undefined}
          onClick={() => { onProduct(product === name ? 'Todos' : name); onClose(); }}>
          <span className={'product-nav-icon ' + (name === 'Daltton' ? 'purple' : 'mint')}>{name === 'Daltton' ? <Layers /> : <Folders />}</span><span className="nav-text">{name}</span>
        </button>)}
      </nav>
      <div className="rail-footer"><b><ShieldCheck size={15} /> Fonte oficial · PNCP</b><p>Oportunidades para Daltton e Gerico, em um só radar.</p><a href="https://pncp.gov.br/app/editais" target="_blank" rel="noreferrer">Consultar portal <ArrowUpRight size={14} /></a></div>
    </aside>
  </>;
}
