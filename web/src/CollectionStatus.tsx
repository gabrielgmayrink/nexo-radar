import { useEffect, useRef, useState } from 'react';
import { AlertCircle, CheckCircle2, Clock, RefreshCw } from 'lucide-react';
import { hasCurrentWeeklyCollection } from './schedule';

type Job = { kind: string; status: string; recordsReceived: number; expectedRecords?: number; expectedPages?: number; passPages?: number; passNumber?: number; completedFullPasses?: number; coverageComplete?: boolean; completedPartitions?: number; totalPartitions?: number; lastActivityAt?: string; error?: string };
type Status = { enabled: boolean; collections: { publications?: { completedAt?: string; source?: string }; open?: { completedAt?: string; coverageComplete?: boolean; captureComplete?:boolean;indexingComplete?:boolean|null;consistency?:string;quarantinedRecords?:number; metrics?: {unique?: number} } }; executions: Job[] };

export default function CollectionStatus({ collectionDate, totalScanned, selectedCount }: { collectionDate?: string; totalScanned?: number; selectedCount?: number }) {
  const [status,setStatus] = useState<Status|null>(null);
  const [refreshing,setRefreshing] = useState(false), [manual,setManual] = useState(false);
  const [notice,setNotice] = useState(''), [statusError,setStatusError] = useState('');
  const [noticeError,setNoticeError] = useState(false);
  const requested = useRef(false), lastCompleted = useRef('');
  const hasLoaded=useRef(false);
  const lastProgress=useRef('');
  const refresh = useRef<() => void>(() => {});
  useEffect(() => {
    const controller = new AbortController();
    const load = async (emitRefresh=true) => {
      setRefreshing(true);
      try {
        const response = await fetch('/api/status',{ signal: controller.signal,cache: 'no-store' });
        if (!response.ok) throw Error();
        const next: Status = await response.json();
        if (!next.collections || !Array.isArray(next.executions)) throw Error();
        if (controller.signal.aborted) return;
        setStatus(next); setStatusError('');
        const completed = next.collections.open?.completedAt || '';
        const progress=next.executions.map(job => job.kind+':'+job.recordsReceived+':'+job.status).join('|');
        if (emitRefresh && hasLoaded.current && ((completed && completed !== lastCompleted.current) || progress!==lastProgress.current)) window.dispatchEvent(new Event('radar:refresh'));
        lastCompleted.current=completed;lastProgress.current=progress;hasLoaded.current=true;
      } catch { if (!controller.signal.aborted) setStatusError('Não foi possível consultar o andamento da coleta. A data abaixo é a última confirmada.'); }
      finally { if (!controller.signal.aborted) setRefreshing(false); }
    };
    refresh.current = () => {
      requested.current = true; setManual(true); setNoticeError(false); setNotice('Recarregando os resultados e a situação da coleta…');
      void load(false); window.dispatchEvent(new Event('radar:refresh'));
    };
    const ready = (event: Event) => {
      if (!requested.current) return;
      requested.current = false; setManual(false);
      const detail = (event as CustomEvent<{ fallback: boolean; stale?: boolean; count: number }>).detail;
      setNoticeError(detail.fallback || !!detail.stale);
      const time = new Date().toLocaleTimeString('pt-BR',{ hour: '2-digit',minute: '2-digit',timeZone:'America/Sao_Paulo' });
      setNotice(detail.stale ? 'A atualização não foi concluída. Mantivemos as oportunidades que você já havia carregado.' : detail.fallback ? 'O banco não respondeu. Mantivemos uma cópia histórica; tente recarregar novamente em instantes.' : `Resultados recarregados às ${time}: ${detail.count.toLocaleString('pt-BR')} oportunidades no perfil da empresa. A data da base muda quando a coleta termina.`);
    };
    const failed = () => { if (!requested.current) return; requested.current = false; setManual(false); setNoticeError(true); setNotice('Não foi possível recarregar os resultados. Tente novamente em instantes.'); };
    window.addEventListener('radar:catalog-ready',ready); window.addEventListener('radar:catalog-error',failed);
    void load(); const timer = window.setInterval(() => void load(),60000);
    return () => { controller.abort(); window.clearInterval(timer); window.removeEventListener('radar:catalog-ready',ready); window.removeEventListener('radar:catalog-error',failed); };
  },[]);

  const latest = status?.executions.filter((job,index,jobs) => jobs.findIndex(other => other.kind === job.kind) === index) || [];
  const unfinished = latest.filter(job => job.status !== 'ok');
  const pending = unfinished.find(job => job.status === 'running' && !!job.lastActivityAt && Date.now()-Date.parse(job.lastActivityAt) < 300000) || unfinished[0];
  const partial = !!pending?.error || pending?.status === 'partial' || pending?.status === 'failed';
  const active = !!pending && !partial && !!pending.lastActivityAt && Date.now()-Date.parse(pending.lastActivityAt) < 300000;
  const verification = (pending?.passNumber || 1)>1;
  const initialPassFinished = (pending?.completedFullPasses || 0)>0;
  const completedAt = status?.collections.open?.completedAt;
  const captured=status?.collections.open?.captureComplete;
  const legacy=status?.collections.open?.consistency==='legacy_count_check';
  const historical = !completedAt || !status?.collections.open?.coverageComplete;
  const current = !historical && !!completedAt && hasCurrentWeeklyCollection(completedAt);
  const awaitingFirstCollection = totalScanned === 0 && !collectionDate && !pending;
  const lastDate = completedAt ? new Date(completedAt).toLocaleString('pt-BR',{ timeZone:'America/Sao_Paulo',dateStyle:'short',timeStyle:'short' }) : collectionDate?.split('-').reverse().join('/') || '…';
  const Icon = partial || statusError ? AlertCircle : active ? RefreshCw : current && !pending ? CheckCircle2 : Clock;
  const pauseMessage=pending?.error==='http_429'?'O PNCP limitou as consultas. O Radar aguarda para retomar com o progresso salvo.':pending?.error==='timeout'?'O PNCP demorou para responder. O progresso está salvo para uma nova tentativa.':pending?.error==='storage_guard'?'A coleta atingiu a proteção de armazenamento. Os dados já coletados foram preservados.':'Atualização pausada, com progresso salvo.';
  return <div className="collection-status-section">
    <div className={'freshness collection-health'+(partial ? ' collection-warning' : current && !pending ? ' collection-current' : '')}>
      <span><Icon size={19} className={active ? 'spinning' : ''}/></span>
      <div className="collection-message">
        <strong>{awaitingFirstCollection ? 'Preparando a varredura nacional de licitações abertas.' : partial ? pauseMessage : active ? initialPassFinished ? 'Conferindo a integridade da captura nacional.' : 'Percorrendo todas as licitações abertas do Brasil.' : pending ? 'Varredura nacional incompleta: há páginas pendentes do PNCP.' : current ? 'Captura e conferência do PNCP concluídas.' : captured ? 'Captura finalizada; cobertura ainda sem conferência completa.' : historical ? 'A primeira varredura nacional ainda não foi concluída.' : 'A base aguarda uma nova coleta completa.'}</strong>
        <p>{awaitingFirstCollection ? 'A consulta percorre todas as páginas do PNCP, sem filtro de empresa, estado ou modalidade.' : <>{completedAt ? `Última captura finalizada: ${lastDate}.` : initialPassFinished ? 'A leitura inicial terminou. Agora comparamos identificadores e versões.' : 'A primeira varredura completa ainda está em andamento.'}{pending ? ` ${pending.recordsReceived.toLocaleString('pt-BR')} leituras de registros${verification ? ' (inclui a conferência)' : ''}${pending.expectedPages ? ` · ${verification ? 'Conferência na página ' : ''}${pending.passPages || 0}/${pending.expectedPages}${verification ? '' : ' páginas da varredura atual'}` : ''}.` : ' Confira sempre a situação no PNCP.'}</>}</p>
        {legacy && <p>Esta captura antiga foi conferida por contagem. Isso não comprova a presença de todos os registros; uma nova coleta compara identificadores e versões para verificar a consistência.</p>}
        {status?.collections.open?.indexingComplete===false && <p>A organização dos dados capturados ainda tem etapas pendentes.</p>}
        {!!status?.collections.open?.quarantinedRecords && <p>{status.collections.open.quarantinedRecords.toLocaleString('pt-BR')} registros aguardam tratamento. Os originais foram preservados.</p>}
        {pending?.expectedPages && <div className="national-coverage"><label htmlFor="national-coverage-progress">{verification ? 'Página conferida: ' : ''}{(pending.passPages || 0).toLocaleString('pt-BR')} de {pending.expectedPages.toLocaleString('pt-BR')}{verification ? '' : ' páginas'} · {pending.expectedRecords?.toLocaleString('pt-BR')} licitações informadas pelo PNCP</label><progress id="national-coverage-progress" max={pending.expectedPages} value={pending.passPages || 0}/><p>{verification ? 'Nova leitura para comparar identificadores e versões; inclui registros já lidos. ' : ''}A cobertura só será concluída após confirmar todas as páginas e os registros únicos.</p></div>}
        {completedAt && totalScanned !== undefined && <p><strong>{totalScanned.toLocaleString('pt-BR')} licitações na captura nacional</strong>{selectedCount !== undefined && <> · <strong>{selectedCount.toLocaleString('pt-BR')} oportunidades no perfil da empresa</strong></>}. Os filtros abaixo refinam essa seleção.</p>}
        <p>A coleta percorre todas as páginas de propostas abertas disponibilizadas pelo PNCP, sem filtro de empresa, estado ou modalidade. A seleção considera o serviço no objeto principal; menções de contexto e serviços acessórios são desconsiderados. Recarregar o painel atualiza os resultados sem iniciar outra coleta.</p>
        <p>Coleta semanal: segunda às 07h. Limpeza do catálogo ativo: domingo às 23h. Horários de Brasília.</p>
        {statusError && <p className="collection-error">{statusError}</p>}
      </div>
      <button className="refresh-catalog" disabled={refreshing || manual} onClick={() => refresh.current()} aria-label="Recarregar resultados"><RefreshCw size={15} className={refreshing || manual ? 'spinning' : ''}/><span>{manual ? 'Recarregando…' : 'Recarregar resultados'}</span></button>
    </div>
    {notice && <p className={'refresh-notice'+(noticeError?' notice-error':'')} role={noticeError?'alert':'status'} aria-live="polite">{notice}</p>}
  </div>;
}
