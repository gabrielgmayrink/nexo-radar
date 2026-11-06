import { useCallback, useEffect, useMemo, useState } from 'react';

import type { Review } from './opportunities';
export type SharedReview = Review & { id: string; actor: string; version: number; updatedAt: string; exampleObject?: string; sourceCurrent?: boolean };
type Session = { enabled: boolean; authenticated: boolean; email?: string; reviews?: SharedReview[] };

export async function teamRequest(data?: Record<string, unknown>) {
  const response = await fetch('/api/team', data ? {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data),
  } : { cache: 'no-store' });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'Não foi possível acessar a equipe.');
  return result;
}

export function useTeam() {
  const [session, setSession] = useState<Session>({ enabled: false, authenticated: false });
  const [error, setError] = useState('');
  const reload = useCallback(async () => {
    try { setSession(await teamRequest()); setError(''); }
    catch { setError('Não foi possível carregar a equipe. Suas anotações locais estão disponíveis.'); }
  }, []);
  useEffect(() => { void reload(); }, [reload]);
  const reviews = useMemo(() => Object.fromEntries((session.reviews || []).map(review => [review.id, review])), [session.reviews]);
  async function save(id: string, review: Review, source: { object: string; additionalInfo: string }) {
    const result = await teamRequest({ action: 'save_review', review: { id, ...review, version: reviews[id]?.version || 0, sourceObject: source.object, sourceAdditional: source.additionalInfo } });
    setSession(current => ({ ...current, reviews: [...(current.reviews || []).filter(r => r.id !== id), result.review] }));
  }
  return { ...session, reviews, error, reload, save };
}
