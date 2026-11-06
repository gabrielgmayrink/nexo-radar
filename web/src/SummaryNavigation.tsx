import { ArrowDownRight, Clock, FileCheck, HelpCircle, Layers } from 'lucide-react';
import { VIEWS, type View } from './opportunities';
const items = [
  { view: 'all', Icon: Layers, hint: 'Resultados selecionados para seus produtos' },
  { view: 'matches', Icon: FileCheck, hint: 'Indícios no objeto ou aprovação da equipe' },
  { view: 'review', Icon: HelpCircle, hint: 'Confirme se a contratação atende ao produto' },
  { view: 'open', Icon: Clock, hint: 'Ativas, com encerramento adiante' },
] as const;
export default function SummaryNavigation({ counts, view, onSelect, loading }: {
  counts: Record<string, number>; view: View; onSelect: (view: View) => void; loading: boolean;
}) {
  return <section className="summary-navigation" aria-label="Listas de oportunidades">
    <p className="summary-instruction">Abra uma lista pelos indicadores abaixo. Os números acompanham os filtros da busca.</p>
    <div className="stat-grid">{items.map(({ view: key, Icon, hint }) => <button key={key} className={'stat stat-link' + (view === key ? ' stat-selected' : '')}
      aria-pressed={view === key} aria-controls="results" disabled={loading} onClick={() => onSelect(key)}>
      <span className="stat-top">{VIEWS[key].short}<i><Icon size={18}/></i></span>
      <strong>{loading ? '—' : counts[key].toLocaleString('pt-BR')}</strong><small>{hint}</small>
      <span className="stat-action">{view === key ? 'Lista selecionada' : 'Ver licitações'}<ArrowDownRight size={15}/></span>
    </button>)}</div>
  </section>;
}
