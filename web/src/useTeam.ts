import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import type { Review } from './opportunities';
export type SharedReview = Review & { id: string; actor: string; version: number; updatedAt: string; exampleObject?: string; sourceCurrent?: boolean };
type Session = { enabled: boolean; authenticated: boolean; email?: string; company?: string; companies?: string[]; reviews?: SharedReview[]; reviewsPage?: number; reviewsHasMore?: boolean };
class TeamRequestError extends Error {
  constructor(message: string,readonly status: number) { super(message); }
}

export async function teamRequest(data?: Record<string, unknown>,company?: string,reviewsPage = 0) {
  const query=new URLSearchParams({reviewsPage:String(reviewsPage)});
  if (company) query.set('company',company);
  const response = await fetch('/api/team?'+query.toString(), data ? {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data),
  } : { cache: 'no-store' });
  const result = await response.json();
  if (!response.ok) throw new TeamRequestError(result.error || 'Não foi possível acessar a equipe.',response.status);
  if (data && (result.authenticated || data.action==='logout')) window.dispatchEvent(new Event('nexo:session'));
  return result;
}

export function useTeam(company?: string) {
  const [session, setSession] = useState<Session>({ enabled: false, authenticated: false });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const requestGeneration=useRef(0),loadingMore=useRef(false);
  const reload = useCallback(async () => {
    const generation=++requestGeneration.current;
    try { const next=await teamRequest(undefined,company);if(generation!==requestGeneration.current)return;setSession(next); setError(''); }
    catch (error) {
      if(generation!==requestGeneration.current)return;
      if(error instanceof TeamRequestError && (error.status===401 || error.status===403)) setSession({enabled:true,authenticated:false});
      setError('Não foi possível carregar a equipe. Tente entrar novamente.');
    }
    finally { if(generation===requestGeneration.current)setLoading(false); }
  }, [company]);
  useEffect(() => {
    void reload();
    const changed = () => { void reload(); };
    window.addEventListener('nexo:session',changed);
    return () => {requestGeneration.current++;window.removeEventListener('nexo:session',changed);};
  }, [reload]);
  const reviews = useMemo(() => Object.fromEntries((session.reviews || []).map(review => [review.id, review])), [session.reviews]);
  async function loadMoreReviews() {
    if (!session.reviewsHasMore || loadingMore.current) return;
    loadingMore.current=true;const generation=requestGeneration.current;
    try {
      const next: Session=await teamRequest(undefined,company,(session.reviewsPage || 0)+1);
      if(generation!==requestGeneration.current)return;
      setSession(current=>({...next,reviews:[...new Map([...(current.reviews || []),...(next.reviews || [])].map(review=>[review.id,review])).values()]}));
    } catch {if(generation===requestGeneration.current)setError('Não foi possível carregar as avaliações seguintes. Tente novamente.');}
    finally {loadingMore.current=false;}
  }
  async function save(id: string, review: Review, source: { object: string; additionalInfo: string }) {
    const result = await teamRequest({ action: 'save_review',company, review: { id, ...review, version: reviews[id]?.version ?? review.version ?? 0, sourceObject: source.object, sourceAdditional: source.additionalInfo } });
    setSession(current => ({ ...current, reviews: [...(current.reviews || []).filter(r => r.id !== id), result.review] }));
  }
  return { ...session, reviews, error, loading, reload, save, loadMoreReviews };
}
