import { lazy, Suspense, useEffect, useState } from 'react';
import { MotionConfig } from 'motion/react';
import LoginPage from './LoginPage';
import { getLoginToken, getSetupToken } from './loginToken';
import { useTeam } from './useTeam';
import PageBoundary from './PageBoundary';

const Dashboard = lazy(() => import('./Dashboard'));
const SignedFeedback = lazy(() => import('./SignedFeedback'));

export default function Portal() {
  const team = useTeam();
  const [company,setCompany] = useState('');
  const [hasToken,setHasToken] = useState(() => !!getLoginToken() || !!getSetupToken());
  useEffect(() => {
    const open = () => setHasToken(false);
    window.addEventListener('nexo:login',open);
    return () => window.removeEventListener('nexo:login',open);
  },[]);
  async function authenticated() { await team.reload();setHasToken(false); }
  return <MotionConfig reducedMotion="user"><PageBoundary>
    {team.authenticated && !hasToken && team.company ? <Suspense fallback={<div className="portal-loading" role="status">Preparando seu radar…</div>}><Dashboard key={((team.companies || []).includes(company)?company:team.company)+team.email} email={team.email || ''} company={(team.companies || []).includes(company)?company:team.company} companies={team.companies || [team.company]} onCompany={setCompany}/></Suspense> : <LoginPage enabled={team.enabled} loading={team.loading} onAuthenticated={authenticated}/>}
    <Suspense fallback={null}><SignedFeedback /></Suspense>
  </PageBoundary></MotionConfig>;
}
