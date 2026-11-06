import { useEffect, useState } from 'react';
import { CheckCircle2, LoaderCircle, X } from 'lucide-react';

type Feedback = { opportunityId: string; productId: string; label: string };
const labels: Record<string, string> = {
  relevante: 'Relevante', irrelevante: 'Irrelevante',
  vai_participar: 'Vou participar', ganhou: 'Ganhou', perdeu: 'Perdeu',
};

export default function SignedFeedback() {
  const [token] = useState(() => new URLSearchParams(location.search).get('feedback') || '');
  const [visible, setVisible] = useState(Boolean(token));
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!token) return;
    const clean = new URL(location.href);
    clean.searchParams.delete('feedback');
    history.replaceState(null, '', clean.pathname + clean.search + clean.hash);
    const controller = new AbortController();
    fetch('/api/feedback?token=' + encodeURIComponent(token), { signal: controller.signal })
      .then(async response => {
        const data = await response.json();
        if (!response.ok) throw Error(data.error || 'Não foi possível validar o link.');
        setFeedback(data);
      })
      .catch(e => { if (e.name !== 'AbortError') setError(e.message); });
    return () => controller.abort();
  }, [token]);

  async function confirm() {
    setBusy(true); setError('');
    try {
      const response = await fetch('/api/feedback', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token }),
      });
      const data = await response.json();
      if (!response.ok) throw Error(data.error || 'Não foi possível salvar.');
      setSaved(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Não foi possível salvar.');
    } finally { setBusy(false); }
  }

  if (!visible) return null;
  return <div className="modal-backdrop shared-feedback-overlay">
    <section className="shared-feedback" role="dialog" aria-modal="true" aria-labelledby="feedback-title">
      <button className="feedback-close" aria-label="Fechar confirmação" autoFocus onClick={() => setVisible(false)}><X size={18}/></button>
      <span className="overline">REVISÃO COMPARTILHADA</span>
      <h2 id="feedback-title">{saved ? 'Avaliação registrada' : 'Confirmar sua avaliação'}</h2>
      {saved ? <p className="feedback-saved"><CheckCircle2 size={20}/> A equipe poderá consultar esse feedback. Você pode fechar esta janela.</p> : feedback ? <>
        <p>Produto: <strong>{feedback.productId === 'daltton' ? 'Daltton' : 'Gerico'}</strong></p>
        <p>PNCP: {feedback.opportunityId}</p>
        <p>Avaliação: <strong>{labels[feedback.label] || feedback.label}</strong></p>
        <button className="primary-button" disabled={busy} onClick={confirm}>{busy && <LoaderCircle className="spinning" size={16}/>}Confirmar avaliação</button>
      </> : !error && <p><LoaderCircle className="spinning" size={16}/> Validando link…</p>}
      {error && <p role="alert">{error}</p>}
    </section>
  </div>;
}
