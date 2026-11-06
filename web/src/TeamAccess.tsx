import { useState } from 'react';
import { LogIn, LogOut, ShieldCheck } from 'lucide-react';
import { teamRequest } from './useTeam';
import { getLoginToken, clearLoginToken } from './loginToken';

// Remove the token from browser history before any request or other navigation.
let pendingToken = getLoginToken();

export default function TeamAccess({ enabled, email, reload }: {
  enabled: boolean; email?: string; reload: () => Promise<void>;
}) {
  const [open, setOpen] = useState(!!pendingToken);
  const [token, setToken] = useState(pendingToken);
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  async function action(kind: string) {
    setBusy(true); setMessage('');
    try {
      const result = await teamRequest({ action: kind, token });
      if (kind === 'confirm_login') { pendingToken = ''; clearLoginToken(); setToken(''); setOpen(false); await reload(); }
      else if (kind === 'logout') { await reload(); setOpen(false); }
      else setMessage(result.message);
    } catch (error) { setMessage(error instanceof Error ? error.message : 'Tente novamente.'); }
    finally { setBusy(false); }
  }
  if (!enabled && !token) return null;
  return <section className="team-access" aria-label="Acesso da equipe">
    <div className="team-access-heading"><span><ShieldCheck size={18}/>{email ? 'Equipe conectada' : 'Trabalhe junto com a equipe'}</span>
      <button className="secondary-button" onClick={() => setOpen(!open)} aria-expanded={open} aria-controls="team-access-form">
        <LogIn size={15}/>{email ? 'Minha conta' : 'Entrar na equipe'}
      </button></div>
    {open && <div id="team-access-form" className="team-access-form">
      {email ? <><p>Conectado como <b>{email}</b>. As avaliações que você publicar ficam disponíveis para a equipe.</p>
        <button className="secondary-button" disabled={busy} onClick={() => void action('logout')}><LogOut size={15}/> Sair</button></>
        : token ? <><p>Confirme para entrar no Radar. Este link é pessoal e só pode ser usado uma vez.</p>
          <button className="primary-button" disabled={busy} onClick={() => void action('confirm_login')}>{busy ? 'Confirmando…' : 'Confirmar entrada'}</button>
          <button className="secondary-button" disabled={busy} onClick={() => { pendingToken = ''; setToken(''); setMessage(''); }}>Solicitar outro link</button></>
          : <div><p>Entre com seu e-mail e sua senha para publicar avaliações e acompanhar a equipe.</p><button className="primary-button" onClick={() => window.dispatchEvent(new Event('nexo:login'))}><LogIn size={15}/> Ir para o acesso</button></div>}
      {message && <p role="status">{message}</p>}
    </div>}
  </section>;
}
