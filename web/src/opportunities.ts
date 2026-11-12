import { createSearchDocument, matchesSearch, parseSearchQuery, type SearchClause, type SearchDocument } from './search.ts';
export type Review = { offer: string; reason: string; status: string; reasonCode?: string; expectedScope?: string; owner?: string; checklist?: {id:string;label:string;done:boolean}[]; sourceCurrent?: boolean; version?: number };
export type Decision = {status:string;reasonCodes:string[];evidence:{code:string;service?:string;role:string;source:string;start:number;end:number;matchedText:string;excerpt:string}[]};
export type ReviewHistory=Review & {actor?:string;version?:number;createdAt:string};
export type Row = { id: string; organization: string; state: string; city: string; modality: string; publishedAt: string; object: string; additionalInfo: string; estimatedValue: number | null; proposalDeadline: string; proposalStart?: string; statusId: number; instrumentId: number; pncpUrl: string; sourceUrl: string; suggestedOffer: string; score: number; scores?: Record<string,number>; evidence: string[]; checkedAt?: string; reviewCandidate?:boolean; classificationVersion?:string; decisionByCompany?:Record<string,Decision>; enrichment?:{analysisStatus:string;items:{number:number;description:string;source:string}[];documents:{title:string;url:string;status:string;contentHash?:string}[];textExcerpts:{documentKey:string;page:number;text:string}[];sources:{id:string;name:string;url:string;externalId:string;linkType:string}[];limitations:string[]}; procurementEvents?:{id:number;kind:string;oldValue:unknown;newValue:unknown;source:string;detectedAt:string}[]; learning?: { label: string; match: string; reasonCode: string; examples: number; offer?: string } };
export const VIEWS = {
  all: { label: 'Todas as oportunidades', short: 'No radar', description: 'Licitações abertas selecionadas para os serviços da sua empresa após a consulta à base nacional. A cobertura e as páginas pendentes aparecem no andamento da coleta.' },
  matches: { label: 'Mais compatíveis', short: 'Mais compatíveis', description: 'O objeto tem sinais de compatibilidade por regras ou foi aprovado pela equipe. Confira os requisitos do edital.' },
  review: { label: 'Precisam de análise', short: 'Precisam de análise', description: 'Há termos relacionados, mas a contratação do seu produto ainda precisa ser confirmada. Abra o objeto e registre sua avaliação.' },
  open: { label: 'Com prazo futuro', short: 'Com prazo futuro', description: 'Contratações ativas, recebendo ou prestes a receber propostas. Confirme prazo e situação no PNCP antes de participar.' },
  tracked: { label: 'Vou participar', short: 'Vou participar', description: 'Oportunidades que você ou a equipe marcaram para participação.' },
  dismissed: { label: 'Descartadas', short: 'Descartadas', description: 'Avaliações negativas e objetos idênticos a exemplos rejeitados. Você pode conferir e corrigir a decisão.' },
  discover: { label: 'Conferir outros objetos', short: 'Outros objetos', description: 'Acervo oficial aberto fora da seleção automática. Pesquise e recupere uma oportunidade que faça sentido para a empresa; nenhum objeto é apagado por ter pontuação baixa.' },
  learning: { label: 'Aprendizado da equipe', short: 'Aprendizado', description: 'Exemplos avaliados e motivos que ajudam a reduzir o ruído da busca.' },
} as const;
export type View = keyof typeof VIEWS;
export const REASONS: Record<string, string> = {
  produto_diferente: 'Está comprando outro produto ou serviço',
  nao_contrata_sistema: 'Não contrata o produto ou serviço oferecido',
  mencao_incidental: 'O termo aparece só como referência',
  escopo_fora: 'O escopo está fora do que oferecemos',
  edital_insuficiente: 'Faltam informações para decidir',
  aderente: 'O objeto corresponde ao nosso produto',
  outro: 'Outro motivo',
};
export type Filters = { query: string; product: string; uf: string; deadline: string; modality: string; assessment: string; city:string;organization:string;minValue:string;maxValue:string;publishedFrom:string;publishedTo:string;source:string;situation:string };
export const EMPTY_FILTERS: Filters = { query: '', product: 'Todos', uf: 'Todas', deadline: 'any', modality: 'Todas', assessment: 'any',city:'',organization:'',minValue:'',maxValue:'',publishedFrom:'',publishedTo:'',source:'all',situation:'open' };
export const normalize = (value: string) => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
export function parseDate(value: string) {
  if (!value) return null;
  const parsed = new Date(/(?:[zZ]|[+-]\d\d:\d\d)$/.test(value) ? value : value.length === 10 ? value + 'T00:00:00-03:00' : value + '-03:00');
  return Number.isNaN(+parsed) ? null : parsed;
}
export function formatDate(value: string) {
  return parseDate(value)?.toLocaleString('pt-BR', { timeZone: 'America/Sao_Paulo', day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }) || 'Não informado';
}
export function procurementState(row: Row, now = Date.now()) {
  if (row.statusId !== 1) return 'Inativa';
  if (![1, 2, 4].includes(row.instrumentId)) return 'Inteligência';
  const deadline = parseDate(row.proposalDeadline);
  if (!deadline) return 'Prazo não informado';
  if (+deadline <= now) return 'Encerrada';
  const start = parseDate(row.proposalStart || '');
  return start && +start > now ? 'A receber propostas' : 'Recebendo propostas';
}
export function hasFutureDeadline(row: Row, now = Date.now()) {
  return ['Recebendo propostas', 'A receber propostas'].includes(procurementState(row, now));
}
export function isDismissed(row: Row, review?: Review) {
  return review?.offer === 'Nenhuma' || review?.status === 'Descartada' || (!review?.offer && row.learning?.label === 'irrelevante');
}
export function productScore(row: Row, product = 'Todos') {
  if (product === 'Todos') return row.score;
  return row.scores?.[product] ?? (row.suggestedOffer === product || row.suggestedOffer === 'Ambas' ? row.score : 0);
}
function approvedOffer(row: Row, review?: Review) {
  if (review?.offer) return ['Public','Gerico','Ambas'].includes(review.offer) ? review.offer : undefined;
  return row.learning?.label === 'relevante' ? row.learning.offer : undefined;
}
export function matchesView(row: Row, view: View, review?: Review, now = Date.now(), product = 'Todos') {
  const dismissed = isDismissed(row, review);
  if (view === 'dismissed') return dismissed;
  if (dismissed) return false;
  if (view === 'all') return true;
  if (view === 'open') return hasFutureDeadline(row, now);
  if (view === 'tracked') return review?.status === 'Vou participar';
  const offer = approvedOffer(row,review);
  const approved = !!offer && (product === 'Todos' || offer === product || offer === 'Ambas');
  const uncertain = review?.offer === 'Revisar' || !approved && (productScore(row,product) < 60 || row.learning?.label === 'revisar');
  return view === 'review' ? uncertain : view === 'matches' ? !uncertain : false;
}
export function matchesFilters(row: Row, filters: Filters, review?: Review, now = Date.now(), search?: { document: SearchDocument; clauses: SearchClause[] }) {
  const confirmed = approvedOffer(row,review);
  const offer = confirmed || row.suggestedOffer;
  if (filters.product !== 'Todos' && offer !== filters.product && offer !== 'Ambas' && (confirmed || productScore(row,filters.product) < 40)) return false;
  if (filters.uf !== 'Todas' && row.state !== filters.uf) return false;
  if (filters.modality !== 'Todas' && row.modality !== filters.modality) return false;
  if (filters.query.trim() && !matchesSearch(search?.document || createSearchDocument(row),search?.clauses || parseSearchQuery(filters.query))) return false;
  if (filters.deadline !== 'any') {
    if (filters.deadline === 'unknown') { if (parseDate(row.proposalDeadline)) return false; }
    else {
      const end = parseDate(row.proposalDeadline);
      if (!hasFutureDeadline(row, now) || !end || +end > now + Number(filters.deadline) * 86400000) return false;
    }
  }
  if (filters.assessment === 'unreviewed' && review?.offer || filters.assessment === 'reviewed' && !review?.offer) return false;
  return true;
}
