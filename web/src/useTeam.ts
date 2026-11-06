import { useCallback, useEffect, useMemo, useState } from 'react';

import type { Review } from './opportunities';
export type SharedReview = Review & { id: string; actor: string; version: number; updatedAt: string; exampleObject?: string; sourceCurrent?: boolean };
type Session = { enabled: boolean; authenticated: boolean; email?: string; company?: string; companies?: string[]; reviews?: SharedReview[] };
class TeamRequestError extends Error {
  constructor(message: string,readonly status: number) { super(message); }
}

export async function teamRequest(data?: Record<string, unknown>,company?: string) {
  const response = await fetch('/api/team'+(company?'?company='+encodeURIComponent(company):''), data ? {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data),
  } : { cache: 'no-store' });
  const result = await response.json();
  if (!response.ok) throw new TeamRequestError(result.error || 'Não foi possível acessar a equipe.',response.status);
  if (['confirm_login','password_login','setup_password','logout'].includes(String(data?.action))) window.dispatchEvent(new Event('nexo:session'));
  return result;
}

export function useTeam(company?: string) {
  const [session, setSession] = useState<Session>({ enabled: false, authenticated: false });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const reload = useCallback(async () => {
    try { setSession(await teamRequest(undefined,company)); setError(''); }
    catch (error) {
      if(error instanceof TeamRequestError && (error.status===401 || error.status===403)) setSession({enabled:true,authenticated:false});
      setError('Não foi possível carregar a equipe. Tente entrar novamente.');
    }
    finally { setLoading(false); }
  }, [company]);
  useEffect(() => {
    void reload();
    const changed = () => { void reload(); };
    window.addEventListener('nexo:session',changed);
    return () => window.removeEventListener('nexo:session',changed);
  }, [reload]);
  const reviews = useMemo(() => Object.fromEntries((session.reviews || []).map(review => [review.id, review])), [session.reviews]);
  async function save(id: string, review: Review, source: { object: string; additionalInfo: string }) {
    const result = await teamRequest({ action: 'save_review',company, review: { id, ...review, version: reviews[id]?.version || 0, sourceObject: source.object, sourceAdditional: source.additionalInfo } });
    setSession(current => ({ ...current, reviews: [...(current.reviews || []).filter(r => r.id !== id), result.review] }));
  }
  return { ...session, reviews, error, loading, reload, save };
}
