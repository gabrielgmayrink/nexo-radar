import { lazy, Suspense, useEffect, useState } from 'react';
import { MotionConfig } from 'motion/react';
import LoginPage from './LoginPage';
import { getLoginToken, getSetupToken } from './loginToken';
import { useTeam } from './useTeam';

const Dashboard = lazy(() => import('./Dashboard'));
const SignedFeedback = lazy(() => import('./SignedFeedback'));

export default function Portal() {
  const team = useTeam();
  const [exploring,setExploring] = useState(false);
  const [hasToken,setHasToken] = useState(() => !!getLoginToken() || !!getSetupToken());
  useEffect(() => {
    const open = () => setExploring(false);
    window.addEventListener('nexo:login',open);
    return () => window.removeEventListener('nexo:login',open);
  },[]);
  async function authenticated() { await team.reload();setHasToken(false); }
  return <MotionConfig reducedMotion="user">
    {(team.authenticated && !hasToken) || exploring ? <Suspense fallback={<div className="portal-loading" role="status">Preparando seu radar…</div>}><Dashboard /></Suspense> : <LoginPage enabled={team.enabled} loading={team.loading} onAuthenticated={authenticated} onExplore={() => setExploring(true)}/>}
    <Suspense fallback={null}><SignedFeedback /></Suspense>
  </MotionConfig>;
}
