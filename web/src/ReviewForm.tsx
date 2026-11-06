import { Check, HelpCircle, ThumbsDown, ThumbsUp } from 'lucide-react';
import { REASONS, type Review, type Row } from './opportunities';
import type { SharedReview } from './useTeam';

export default function ReviewForm({ row, review, shared, draft, authenticated, busy, message, onChange, onSave, onReload, onUseShared }: {
  row: Row; review?: Review; shared?: SharedReview; draft: boolean; authenticated: boolean; busy: boolean; message: string;
  onChange: (change: Partial<Review>) => void; onSave: () => void; onReload: () => void; onUseShared: () => void;
}) {
  const assessment = review?.offer === 'Nenhuma' ? 'no' : review?.offer === 'Revisar' ? 'unsure' : review?.offer ? 'yes' : '';
  const negative = assessment === 'no';
  return <section className="review-form" aria-labelledby="review-title">
    <div className="review-intro"><h3 id="review-title">Essa licitação faz sentido para vocês?</h3><p>Sua decisão ajuda a separar oportunidades de ruído. Registre o motivo para a equipe aprender com o exemplo.</p></div>
    {shared?.sourceCurrent===false&&<p role="status">O objeto mudou desde a última avaliação. A decisão anterior foi preservada no histórico e precisa ser revista.</p>}
    <div className="assessment-options" role="group" aria-label="Avaliar relevância">
      <button type="button" aria-pressed={assessment === 'yes'} onClick={() => onChange({ offer: ['Daltton','Gerico','Ambas'].includes(row.suggestedOffer) ? row.suggestedOffer : 'Daltton', status: 'Em avaliação', reasonCode: 'aderente' })}><ThumbsUp size={16}/> Faz sentido</button>
      <button type="button" aria-pressed={negative} onClick={() => onChange({ offer: 'Nenhuma', status: 'Descartada', reasonCode: '' })}><ThumbsDown size={16}/> Não tem relação</button>
      <button type="button" aria-pressed={assessment === 'unsure'} onClick={() => onChange({ offer: 'Revisar', status: 'Em avaliação', reasonCode: 'edital_insuficiente' })}><HelpCircle size={16}/> Preciso analisar</button>
    </div>
    <label>Produto relacionado<select value={review?.offer || ''} onChange={event => onChange({ offer: event.target.value,...(event.target.value==='Nenhuma'?{reasonCode:'',status:'Descartada'}:{}) })}>
      <option value="">Selecione uma decisão</option>{['Daltton','Gerico','Ambas','Nenhuma','Revisar'].map(value => <option key={value}>{value}</option>)}
    </select></label>
    <label>{negative ? 'Por que não serve? *' : 'Motivo da avaliação'}<select aria-label="Motivo da avaliação" value={review?.reasonCode || ''} onChange={event => onChange({ reasonCode: event.target.value })}>
      <option value="">Selecione o motivo</option>{Object.entries(REASONS).filter(([key]) => !negative || key !== 'aderente').map(([key,label]) => <option value={key} key={key}>{label}</option>)}
    </select></label>
    <label>Explique o que identificou<textarea aria-label="Motivo" rows={3} maxLength={2000} placeholder="Descreva por que o objeto atende ou não aos serviços da empresa." value={review?.reason || ''} onChange={event => onChange({ reason: event.target.value })}/></label>
    <label>O que uma oportunidade boa deveria contratar?<textarea rows={2} maxLength={500} placeholder="Informe o produto ou serviço esperado e os limites de atendimento." value={review?.expectedScope || ''} onChange={event => onChange({ expectedScope: event.target.value })}/></label>
    <label>Acompanhamento<select value={review?.status || 'Nova'} onChange={event => onChange({ status: event.target.value })}>{['Nova','Em avaliação','Vou participar','Descartada','Ganhou','Perdeu'].map(value => <option key={value}>{value}</option>)}</select></label>
    <div className="learning-note"><Check size={16}/><p>Ao publicar, o Radar guarda o exemplo. Rejeições pelo produto errado, ausência do serviço oferecido ou menção incidental podem separar objetos idênticos em “Descartadas”. Restrições de escopo e casos parecidos pedem nova análise. Nenhuma regra geral muda por uma avaliação isolada.</p></div>
    <small>{draft ? 'Rascunho salvo neste navegador. Publique para compartilhar e alimentar os exemplos da equipe.' : shared ? `Avaliação compartilhada · versão ${shared.version}` : 'Sua avaliação ainda não foi publicada.'}</small>
    {authenticated ? <><button className="primary-button" disabled={busy || !review?.offer || negative && !review?.reasonCode} onClick={onSave}>{busy ? 'Publicando…' : 'Publicar avaliação e ensinar o Radar'}</button>
      {shared && <><button className="secondary-button" onClick={onReload}>Recarregar avaliação da equipe</button>{draft && <button className="secondary-button" onClick={onUseShared}>Remover meu rascunho e usar a avaliação da equipe</button>}</>}
    </> : <small>Entre na equipe no topo da página para publicar. Seu rascunho continua salvo aqui.</small>}
    {message && <p role="status">{message}</p>}
  </section>;
}
