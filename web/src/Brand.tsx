export function RadarMark({ className = '' }: { className?: string }) {
  return <img className={className} src="/brand/nexo-symbol.svg" alt="" aria-hidden="true" width="64" height="64" />;
}

export function Brand() {
  return <a className="logo brand-lockup" href="#" aria-label="Nexo Radar, início">
    <RadarMark className="brand-icon" />
    <div className="brand-wordmark">nexo<span className="brand-period">.</span><small>RADAR</small></div>
  </a>;
}
