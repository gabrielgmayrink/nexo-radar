export function RadarMark({ className = '' }: { className?: string }) {
  return <svg className={className} viewBox="0 0 64 64" fill="none" aria-hidden="true">
    <rect width="64" height="64" rx="19" fill="#163E35" />
    <path d="M44.8 17.4a20.3 20.3 0 1 0 5.3 25" stroke="#71998A" strokeWidth="1.4" strokeLinecap="round" />
    <path d="M43.3 24a13.8 13.8 0 1 0 .5 15.3" stroke="#B9D6BC" strokeWidth="1.8" strokeLinecap="round" />
    <path d="M32 32 47.5 16.5" stroke="#E0EAC8" strokeWidth="2" strokeLinecap="round" />
    <path d="m29 37 6-6.1c2.1-2.1 1.3-6.1-2.4-6.1H27v17" stroke="#F4F6E9" strokeWidth="3.3" strokeLinecap="round" strokeLinejoin="round" />
    <path d="m31.4 34.5 7 7" stroke="#F4F6E9" strokeWidth="3.3" strokeLinecap="round" />
    <circle cx="47.5" cy="16.5" r="4" fill="#CDE69C" />
    <circle cx="16.3" cy="43.8" r="2.2" fill="#88BDA5" />
  </svg>;
}

export function Brand() {
  return <a className="logo brand-lockup" href="#" aria-label="Radar de Licitações, início">
    <RadarMark className="brand-icon" />
    <div className="brand-wordmark">radar<span className="brand-period">.</span><small>DE LICITAÇÕES</small></div>
  </a>;
}
