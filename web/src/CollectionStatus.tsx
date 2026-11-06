import { useEffect, useRef, useState } from 'react';
import { AlertCircle, CheckCircle2, Clock, RefreshCw } from 'lucide-react';

type Job = { kind: string; status: string; recordsReceived: number; completedPartitions?: number; totalPartitions?: number; lastActivityAt?: string; error?: string };
type Status = { enabled: boolean; collections: { publications?: { completedAt?: string; source?: string }; open?: { completedAt?: string } }; executions: Job[] };

export default function CollectionStatus({ collectionDate, totalScanned }: { collectionDate?: string; totalScanned?: number }) {
  const [status,setStatus] = useState<Status|null>(null);
  const [refreshing,setRefreshing] = useState(false), [manual,setManual] = useState(false);
  const [notice,setNotice] = useState(''), [statusError,setStatusError] = useState('');
  const [noticeError,setNoticeError] = useState(false);
  const requested = useRef(false), lastCompleted = useRef('');
  const refresh = useRef<() => void>(() => {});
  useEffect(() => {
    const controller = new AbortController();
    const load = async () => {
      setRefreshing(true);
      try {
        const response = await fetch('/api/status',{ signal: controller.signal,cache: 'no-store' });
        if (!response.ok) throw Error();
        const next: Status = await response.json();
        if (!next.collections || !Array.isArray(next.executions)) throw Error();
        if (controller.signal.aborted) return;
        setStatus(next); setStatusError('');
        const completed = next.collections.publications?.completedAt || '';
        if (completed && completed !== lastCompleted.current) {
          lastCompleted.current = completed; window.dispatchEvent(new Event('radar:refresh'));
        }
      } catch { if (!controller.signal.aborted) setStatusError('Não foi possível consultar o andamento da coleta. A data abaixo é a última confirmada.'); }
      finally { if (!controller.signal.aborted) setRefreshing(false); }
    };
    refresh.current = () => {
      requested.current = true; setManual(true); setNoticeError(false); setNotice('Recarregando os resultados e a situação da coleta…');
      void load(); window.dispatchEvent(new Event('radar:refresh'));
    };
    const ready = (event: Event) => {
      if (!requested.current) return;
      requested.current = false; setManual(false);
      const detail = (event as CustomEvent<{ fallback: boolean; count: number }>).detail;
      setNoticeError(detail.fallback);
      const time = new Date().toLocaleTimeString('pt-BR',{ hour: '2-digit',minute: '2-digit',timeZone:'America/Sao_Paulo' });
      setNotice(detail.fallback ? 'O banco não respondeu. Mantivemos uma cópia histórica; tente recarregar novamente em instantes.' : `Resultados recarregados às ${time}: ${detail.count.toLocaleString('pt-BR')} oportunidades na seleção por produto. A data da base muda quando a coleta termina.`);
    };
    const failed = () => { if (!requested.current) return; requested.current = false; setManual(false); setNoticeError(true); setNotice('Não foi possível recarregar os resultados. Tente novamente em instantes.'); };
    window.addEventListener('radar:catalog-ready',ready); window.addEventListener('radar:catalog-error',failed);
    void load(); const timer = window.setInterval(() => void load(),60000);
    return () => { controller.abort(); window.clearInterval(timer); window.removeEventListener('radar:catalog-ready',ready); window.removeEventListener('radar:catalog-error',failed); };
  },[]);

  const latest = status?.executions.filter((job,index,jobs) => jobs.findIndex(other => other.kind === job.kind) === index) || [];
  const unfinished = latest.filter(job => job.status !== 'ok');
  const pending = unfinished.find(job => job.status === 'running' && !!job.lastActivityAt && Date.now()-Date.parse(job.lastActivityAt) < 300000) || unfinished[0];
  const partial = pending?.status === 'partial' || pending?.status === 'failed';
  const active = !!pending && !partial && !!pending.lastActivityAt && Date.now()-Date.parse(pending.lastActivityAt) < 300000;
  const completedAt = status?.collections.publications?.completedAt;
  const historical = !completedAt || status?.collections.publications?.source === 'historical-import';
  const current = !historical && !!completedAt && Date.now()-Date.parse(completedAt) < 26*3600000;
  const awaitingFirstCollection = totalScanned === 0 && !collectionDate && !pending;
  const lastDate = completedAt ? new Date(completedAt).toLocaleString('pt-BR',{ timeZone:'America/Sao_Paulo',dateStyle:'short',timeStyle:'short' }) : collectionDate?.split('-').reverse().join('/') || '…';
  const Icon = partial || statusError ? AlertCircle : active ? RefreshCw : current && !pending ? CheckCircle2 : Clock;
  const pauseMessage=pending?.error==='http_429'?'O PNCP limitou as consultas. O Radar aguarda para retomar com o progresso salvo.':pending?.error==='timeout'?'O PNCP demorou para responder. O progresso está salvo para uma nova tentativa.':pending?.error==='storage_guard'?'A coleta atingiu a proteção de armazenamento. Os dados já coletados foram preservados.':'Atualização pausada, com progresso salvo.';
  return <div className="collection-status-section">
    <div className={'freshness collection-health'+(partial ? ' collection-warning' : current && !pending ? ' collection-current' : '')}>
      <span><Icon size={19} className={active ? 'spinning' : ''}/></span>
      <div className="collection-message">
        <strong>{awaitingFirstCollection ? 'A primeira coleta de licitações ainda não foi executada.' : partial ? pauseMessage : active ? 'Coletando novas publicações do PNCP.' : pending ? 'Coleta parcial: faltam lotes do PNCP. A próxima execução continua de onde parou.' : current ? 'Coleta automática atualizada.' : historical ? 'Base histórica do PNCP.' : 'A base aguarda uma nova coleta completa.'}</strong>
        <p>{awaitingFirstCollection ? 'Os critérios da Public estão preparados. As oportunidades aparecerão após a ativação da coleta.' : <>Última coleta concluída: {lastDate}.{pending ? ` ${pending.recordsReceived.toLocaleString('pt-BR')} registros recebidos${pending.totalPartitions ? ` · ${pending.completedPartitions || 0}/${pending.totalPartitions} etapas concluídas` : ''}.` : ' Confira sempre a situação no PNCP.'}</>}</p>
        {pending && <p>Cada lote contém até 50 licitações. Os resultados já encontrados estão disponíveis; recarregar o painel não inicia uma nova coleta.</p>}
        {totalScanned !== undefined && <p>{totalScanned.toLocaleString('pt-BR')} contratações na base concluída. Abaixo aparecem apenas as selecionadas para seus produtos.</p>}
        {statusError && <p className="collection-error">{statusError}</p>}
      </div>
      <button className="refresh-catalog" disabled={refreshing || manual} onClick={() => refresh.current()} aria-label="Recarregar resultados"><RefreshCw size={15} className={refreshing || manual ? 'spinning' : ''}/><span>{manual ? 'Recarregando…' : 'Recarregar resultados'}</span></button>
    </div>
    {notice && <p className={'refresh-notice'+(noticeError?' notice-error':'')} role={noticeError?'alert':'status'} aria-live="polite">{notice}</p>}
  </div>;
}
