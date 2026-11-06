import { ArrowUpRight, Building2, Clock3, Info, MapPin, ThumbsDown, ThumbsUp } from 'lucide-react';
import { formatDate, hasFutureDeadline, parseDate, procurementState, productScore, REASONS, type Review, type Row } from './opportunities';
const money = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 });
export default function OpportunityCard({ row, review, product='Todos', onOpen }: {
  row: Row; review?: Review; product?: string; onOpen: (trigger: HTMLElement, decision?: 'yes' | 'no') => void;
}) {
  const deadline = parseDate(row.proposalDeadline);
  const days = deadline ? Math.ceil((+deadline - Date.now()) / 86400000) : null;
  const offer = review?.offer || row.learning?.offer || row.suggestedOffer;
  const score=productScore(row,product);
  const label=product!=='Todos'?product:offer;
  const tone=label==='Public'?'purple':label==='Gerico'?'mint':'neutral';
  return <article className="tender-card">
    <div className="card-top"><span className={'product-pill '+tone}>{label}{product!=='Todos'&&score<60?' · analisar':''}</span>
      <span className="rule-score" title="Pontuação das regras para o produto selecionado. Não é probabilidade de acerto."><small>Regra</small> {score}<small>/100</small><Info size={14}/></span></div>
    <div className="tender-place"><MapPin size={13}/>{row.city} · {row.state}<span>{row.modality}</span></div>
    <button className="tender-object" onClick={event => onOpen(event.currentTarget)}>{row.object}</button>
    <div className="tender-buyer"><Building2 size={14}/><span>{row.organization}</span></div>
    <div className="signal-box"><p><b>Por que apareceu</b><br/>{row.evidence.slice(0,2).join(' · ') || 'Termos relacionados; confirme o escopo no edital.'}</p></div>
    {row.learning && <div className={'learned-signal ' + (row.learning.label === 'irrelevante' ? 'learned-negative' : '')}>
      <b>{row.learning.match === 'similar_negative' ? 'Lembra um exemplo rejeitado' : row.learning.match === 'identical_context' ? 'Confira o contexto: há um exemplo rejeitado' : row.learning.match === 'conflicting_examples' ? 'Há exemplos com decisões diferentes' : row.learning.label === 'irrelevante' ? 'Objeto já rejeitado pela equipe' : 'Objeto avaliado pela equipe'}</b>
      <span>{REASONS[row.learning.reasonCode] || 'Abra os detalhes para conferir o contexto.'}</span>
    </div>}
    <div className="tender-values"><div><small>VALOR ESTIMADO</small><strong>{row.estimatedValue !== null ? money.format(row.estimatedValue) : 'Não informado / sigiloso'}</strong></div>
      <div><small>ENCERRAMENTO · BRASÍLIA</small><strong>{formatDate(row.proposalDeadline)}</strong>{hasFutureDeadline(row) && days !== null && days <= 7 && <span className="deadline-warning"><Clock3 size={12}/>{days <= 1 ? 'Encerra em até 24 horas' : `Encerra em até ${days} dias`}</span>}</div></div>
    <div className="tender-bottom"><span className={'state-pill ' + (hasFutureDeadline(row) ? 'future' : '')}>{procurementState(row)}</span><button onClick={event => onOpen(event.currentTarget)}>Ver detalhes <ArrowUpRight size={15}/></button></div>
    <div className="card-assessment" role="group" aria-label="Sua avaliação rápida"><span>Faz sentido?</span><button onClick={event => onOpen(event.currentTarget,'yes')}><ThumbsUp size={14}/> Sim</button><button onClick={event => onOpen(event.currentTarget,'no')}><ThumbsDown size={14}/> Não tem relação</button></div>
    {review?.offer && <div className="review-label">Avaliação: {review.offer} · {review.status}</div>}
  </article>;
}
