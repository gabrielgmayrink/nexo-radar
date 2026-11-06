import { useEffect, useRef, type ReactNode, type RefObject } from 'react';
import { ExternalLink, RefreshCw, X } from 'lucide-react';
import { useDialogFocus } from './useDialogFocus';
import { formatDate, procurementState, type Row } from './opportunities';
export default function OpportunityDetails({ row, checking, checkError, reviewIntent, onClose, onRefresh, triggerRef, children }: {
  row: Row; checking: boolean; checkError: string; reviewIntent: boolean; onClose: () => void; onRefresh: () => void; triggerRef: RefObject<HTMLElement | null>; children: ReactNode;
}) {
  const ref = useRef<HTMLElement>(null);
  useDialogFocus(true,ref,triggerRef);
  useEffect(() => { if (!reviewIntent) return; const frame=requestAnimationFrame(() => { const form=ref.current?.querySelector<HTMLElement>('.review-form'); form?.scrollIntoView({block:'start'}); form?.querySelector<HTMLButtonElement>('button')?.focus({preventScroll:true}); }); return () => cancelAnimationFrame(frame); },[reviewIntent]);
  useEffect(() => { const close = (event: KeyboardEvent) => { if (event.key === 'Escape') onClose(); }; window.addEventListener('keydown',close); return () => window.removeEventListener('keydown',close); },[onClose]);
  return <div className="modal-backdrop" onClick={onClose}><section ref={ref} tabIndex={-1} className="detail-panel" role="dialog" aria-modal="true" aria-labelledby="detail-title" onClick={event => event.stopPropagation()}>
    <button className="close-panel" onClick={onClose} aria-label="Fechar detalhes"><X size={20}/></button><span className="detail-eyebrow">ANÁLISE DA OPORTUNIDADE</span>
    <span className="overline">CONFIRA O OBJETO E DECIDA O PRÓXIMO PASSO</span><h2 id="detail-title">{row.organization}</h2><p>{row.city} · {row.state} · {row.modality}</p>
    <div className="detail-links"><a className="primary-button" href={row.pncpUrl} target="_blank" rel="noreferrer">Abrir edital no PNCP <ExternalLink size={15}/></a>{/^https?:\/\//.test(row.sourceUrl) && <a className="secondary-button" href={row.sourceUrl} target="_blank" rel="noreferrer">Sistema de origem <ExternalLink size={15}/></a>}</div>
    <button className="secondary-button refresh-button" disabled={checking} onClick={onRefresh}><RefreshCw size={15} className={checking ? 'spinning' : ''}/>{checking ? 'Consultando PNCP…' : 'Atualizar situação no PNCP'}</button>
    <p>{procurementState(row)} · Encerramento: {formatDate(row.proposalDeadline)} (Brasília)</p>{row.checkedAt && <p>Conferido em {formatDate(row.checkedAt)}</p>}{checkError && <p role="alert">{checkError}</p>}
    <h3>Objeto completo</h3><p className="full-object">{row.object}</p>{row.additionalInfo && <><h3>Informações complementares</h3><p className="full-object">{row.additionalInfo}</p></>}
    <h3>Por que apareceu na busca</h3><p>Sugestão: {row.suggestedOffer} · Regra {row.score}/100. A pontuação indica termos encontrados e não confirma elegibilidade.</p><ul>{row.evidence.map((item,index) => <li key={index}>{item}</li>)}</ul>
    {row.learning && <p className="learning-detail-note">A memória de exemplos da equipe sinalizou este objeto. Confira a avaliação e o escopo antes de decidir.</p>}
    {children}<p className="detail-id">PNCP {row.id} · Publicado em {formatDate(row.publishedAt)}</p>
  </section></div>;
}
