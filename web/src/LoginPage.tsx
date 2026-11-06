import { useState, type FormEvent } from 'react';
import { motion, useReducedMotion } from 'motion/react';
import { ArrowRight, ArrowUpRight, CheckCheck, Eye, EyeOff, Fingerprint, LoaderCircle, LockKeyhole, Mail, Radar, ShieldCheck } from 'lucide-react';
import BlurText from './components/reactbits/BlurText';
import { Brand } from './Brand';
import { getLoginToken, clearLoginToken, getSetupToken, clearSetupToken } from './loginToken';
import { teamRequest } from './useTeam';

type Props = { enabled: boolean; loading: boolean; onAuthenticated: () => Promise<void> };

export default function LoginPage({ enabled, loading, onAuthenticated }: Props) {
  const [email,setEmail] = useState('');
  const [token,setToken] = useState(getLoginToken);
  const [setup,setSetup] = useState(getSetupToken);
  const [password,setPassword] = useState(''), [confirmation,setConfirmation] = useState('');
  const [showPassword,setShowPassword] = useState(false);
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState('');
  const reduced = useReducedMotion();

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy || loading) return;
    setError('');
    if (!enabled) { setError('O acesso da equipe está sendo preparado. Enquanto isso, você pode conhecer o painel público.'); return; }
    if (setup && password !== confirmation) { setError('As senhas precisam ser iguais.'); return; }
    setBusy(true);
    try {
      if (setup) {
        await teamRequest({ action:'setup_password',token:setup,password });
        clearSetupToken();setSetup('');setPassword('');setConfirmation('');
        await onAuthenticated();
      } else if (token) {
        await teamRequest({ action:'confirm_login',token });
        clearLoginToken();setToken('');
        await onAuthenticated();
      } else {
        await teamRequest({ action:'password_login',email:email.trim(),password });
        setPassword('');
        await onAuthenticated();
      }
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Não foi possível entrar. Tente novamente.'); }
    finally { setBusy(false); }
  }

  return <main className="login-page">
    <section className="login-story" aria-label="Nexo Radar, inteligência em oportunidades">
      <div className="login-grid" aria-hidden="true" />
      <header className="login-story-header"><Brand /><span className="login-product-tag"><span /> INTELIGÊNCIA EM LICITAÇÕES</span></header>
      <motion.div className="login-visual" initial={reduced ? false : { opacity:0,y:25 }} animate={{ opacity:1,y:0 }} transition={{ duration:.9,ease:[.22,1,.36,1] }} aria-hidden="true">
        <div className="logo-halo logo-halo-one" /><div className="logo-halo logo-halo-two" />
        <div className="logo-orbit orbit-one" /><div className="logo-orbit orbit-two" />
        <img src="/brand/nexo-symbol-3d.png" className="login-logo-3d" width="1024" height="1024" alt="" fetchPriority="high" onError={event => { event.currentTarget.onerror=null; event.currentTarget.src='/brand/nexo-symbol.svg'; }} />
        <div className="signal-label signal-label-one"><Radar size={15}/><div><b>Encontre o sinal.</b><span>Oportunidades com contexto.</span></div></div>
        <div className="signal-label signal-label-two"><CheckCheck size={15}/><div><b>Avance com clareza.</b><span>Do edital à decisão.</span></div></div>
      </motion.div>
      <div className="login-story-copy"><span className="login-eyebrow"><span /> UM NOVO OLHAR PARA CADA OPORTUNIDADE</span>
        <div className="login-story-title">{reduced ? <p>Veja antes.<br/>Decida melhor.</p> : <BlurText text="Veja antes. Decida melhor." delay={70} animateBy="words" trigger="load" blur={5} distance={14} />}</div>
        <p>Conecte sua empresa às licitações que fazem sentido. Menos ruído na busca. Mais clareza para o próximo passo.</p>
      </div>
      <footer className="login-story-footer"><span><ShieldCheck size={14}/> Dados de fontes oficiais</span><span>Feito para quem quer ir além <ArrowUpRight size={14}/></span></footer>
    </section>

    <section className="login-access" aria-labelledby="login-title">
      <div className="login-mobile-brand"><Brand /></div>
      <div className="login-access-top"><span>SEU PRÓXIMO PASSO COMEÇA AQUI</span><a href="https://pncp.gov.br/app/editais" target="_blank" rel="noreferrer">Fonte PNCP <ArrowUpRight size={13}/></a></div>
      <motion.div className="login-form-wrap" initial={reduced ? false : { opacity:0,y:16 }} animate={{ opacity:1,y:0 }} transition={{ duration:.6,delay:.12 }}>
        <div className="login-access-icon"><Fingerprint size={29} strokeWidth={1.5}/></div>
        <span className="login-form-eyebrow">BEM-VINDO AO NEXO RADAR</span>
        <h1 id="login-title">Seu radar.<br/><span>Suas possibilidades.</span></h1>
        <p className="login-form-intro">Entre no seu espaço para acompanhar oportunidades e decidir junto com sua equipe.</p>

          <form onSubmit={event => void submit(event)} className="login-form">
            {!token && !setup && <><label htmlFor="login-email">E-mail de acesso</label><div className="login-input-wrap"><Mail size={18} aria-hidden="true"/><input id="login-email" name="email" type="email" autoComplete="email" inputMode="email" required maxLength={254} value={email} onChange={event => setEmail(event.target.value)} placeholder="voce@empresa.com.br" disabled={busy}/></div></>}
            {!token && <><label htmlFor="login-password" className="login-password-label">{setup ? 'Crie sua senha' : 'Sua senha'}</label><div className="login-input-wrap"><LockKeyhole size={18} aria-hidden="true"/><input id="login-password" name="password" type={showPassword ? 'text' : 'password'} autoComplete={setup ? 'new-password' : 'current-password'} required minLength={setup ? 12 : 1} maxLength={128} value={password} onChange={event => setPassword(event.target.value)} placeholder={setup ? 'Pelo menos 12 caracteres' : 'Digite sua senha'} disabled={busy}/><button type="button" className="login-password-visibility" aria-label={showPassword ? 'Ocultar senha' : 'Mostrar senha'} aria-pressed={showPassword} onClick={() => setShowPassword(value => !value)}>{showPassword ? <EyeOff size={17}/> : <Eye size={17}/>}</button></div>{setup && <><label htmlFor="login-confirmation" className="login-password-label">Confirme sua senha</label><div className="login-input-wrap"><LockKeyhole size={18} aria-hidden="true"/><input id="login-confirmation" name="confirmation" type={showPassword ? 'text' : 'password'} autoComplete="new-password" required minLength={12} maxLength={128} value={confirmation} onChange={event => setConfirmation(event.target.value)} placeholder="Repita a senha" disabled={busy}/></div></>}<p className="login-field-hint"><ShieldCheck size={12}/>{setup ? 'Este convite é pessoal e só pode ser usado uma vez.' : 'Acesso pessoal e exclusivo para sua equipe.'}</p></>}
            {token && <p className="login-confirm-copy">Seu link de acesso está pronto. Confirme abaixo para entrar com segurança.</p>}
            {error && <p className="login-error" role="alert">{error}</p>}
            <button className="login-submit" type="submit" disabled={busy || loading} aria-busy={busy}>{busy || loading ? <><LoaderCircle size={18} className="spinning"/>{busy ? 'Só um instante…' : 'Preparando seu acesso…'}</> : <>{setup ? 'Definir senha e entrar' : token ? 'Confirmar meu acesso' : 'Entrar no meu radar'}<ArrowRight size={18}/></>}</button>
            {!loading && !enabled && !token && <p className="login-pending-note">O acesso está indisponível neste momento. Tente novamente em instantes.</p>}
          </form>

        <div className="login-trust-card">
          <ShieldCheck size={19}/><div><b>Um espaço exclusivo para sua empresa.</b><p>Use seu e-mail autorizado. Oportunidades e avaliações ficam restritas à sua equipe.</p></div>
        </div>
      </motion.div>
      <footer className="login-access-footer"><span>© {new Date().getFullYear()} Nexo Radar</span><span><ShieldCheck size={13}/> Acesso exclusivo da equipe</span></footer>
    </section>
  </main>;
}
