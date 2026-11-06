import { useState } from 'react';
import { LogIn, LogOut, Mail, ShieldCheck } from 'lucide-react';
import { teamRequest } from './useTeam';

// Remove the token from browser history before any request or other navigation.
let pendingToken = '';
if (window.location.hash.startsWith('#login=')) {
  pendingToken = window.location.hash.slice(7);
  window.history.replaceState(null, '', window.location.pathname + window.location.search);
}

export default function TeamAccess({ enabled, email, reload }: {
  enabled: boolean; email?: string; reload: () => Promise<void>;
}) {
  const [open, setOpen] = useState(!!pendingToken);
  const [token, setToken] = useState(pendingToken);
  const [address, setAddress] = useState(''), [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  async function action(kind: string) {
    setBusy(true); setMessage('');
    try {
      const result = await teamRequest({ action: kind, ...(kind === 'request_link' ? { email: address } : { token }) });
      if (kind === 'confirm_login') { pendingToken = ''; setToken(''); setOpen(false); await reload(); }
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
          : <form onSubmit={event => { event.preventDefault(); void action('request_link'); }}>
            <p>Use o e-mail autorizado. Enviaremos um link de acesso, sem senha.</p>
            <label htmlFor="team-email">Seu e-mail</label><div className="team-login-input"><input id="team-email" type="email" autoComplete="email" required maxLength={254} value={address} onChange={event => setAddress(event.target.value)}/>
              <button className="primary-button" disabled={busy}><Mail size={15}/>{busy ? 'Enviando…' : 'Receber link'}</button></div>
          </form>}
      {message && <p role="status">{message}</p>}
    </div>}
  </section>;
}
