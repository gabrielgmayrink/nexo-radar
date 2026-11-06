import { BookOpenCheck, ThumbsDown, ThumbsUp } from 'lucide-react';
import { REASONS } from './opportunities';
import type { SharedReview } from './useTeam';
export default function LearningPanel({ authenticated, reviews }: { authenticated: boolean; reviews: Record<string,SharedReview> }) {
  const values = Object.values(reviews), negative = values.filter(row => row.sourceCurrent!==false && row.offer === 'Nenhuma');
  const positive = values.filter(row => row.sourceCurrent!==false && ['Daltton','Gerico','Ambas'].includes(row.offer));
  return <section className="learning-panel" aria-label="Base de exemplos da equipe">
    <div className="learning-explainer"><BookOpenCheck size={26}/><div><h3>Ensine com exemplos concretos</h3><p>Use “Não tem relação” para rejeitar um objeto e explicar o erro. Use “Faz sentido” para registrar o que queremos encontrar. Os exemplos ficam disponíveis aqui para a equipe.</p></div></div>
    {!authenticated ? <div className="zero-state"><h3>Entre para acompanhar os exemplos da equipe</h3><p>O acesso fica no topo da página. A busca de licitações continua pública.</p></div> : <>
      <div className="learning-counts"><span><ThumbsUp size={18}/><strong>{positive.length}</strong> exemplos relevantes</span><span><ThumbsDown size={18}/><strong>{negative.length}</strong> exemplos rejeitados</span></div>
      {!!negative.length && <div className="reason-breakdown">{Object.entries(REASONS).map(([key,label]) => { const count = negative.filter(row => row.reasonCode === key).length; return count ? <span key={key}>{label}<b>{count}</b></span> : null; })}</div>}
      {!values.length ? <div className="zero-state"><h3>A base começa com a primeira avaliação</h3><p>Abra uma licitação, registre a decisão e clique em “Publicar avaliação e ensinar o Radar”.</p></div> : <div className="learning-examples">{values.slice().sort((a,b) => b.updatedAt.localeCompare(a.updatedAt)).slice(0,50).map(row => <article key={row.id}><span className={'example-label ' + (row.offer === 'Nenhuma' ? 'example-negative' : '')}>{row.offer === 'Nenhuma' ? 'Não tem relação' : row.offer === 'Revisar' ? 'Em análise' : 'Faz sentido · '+row.offer}</span><h3>{row.exampleObject || row.id}</h3><p><b>Motivo:</b> {REASONS[row.reasonCode || ''] || 'Não informado'}{row.reason ? ' — '+row.reason : ''}</p>{row.expectedScope && <p><b>O que procurar:</b> {row.expectedScope}</p>}<small>{row.id} · versão {row.version}</small></article>)}</div>}
    </>}
    <p className="learning-limits">Sem IA paga. O Radar usa memória de objetos idênticos e comparação de palavras para sinalizar semelhanças. Semelhança não confirma irrelevância; mudanças gerais nas regras precisam de revisão.</p>
  </section>;
}
