import { Building2, CircleCheck, Clock3 } from 'lucide-react';
import { companies } from '../../src/radar/companies.json';

export const configurationPending = !companies.some(company => company.enabled && company.terms.length > 0);

export default function CompanySetup() {
  return <section className="company-setup" aria-labelledby="company-setup-title">
    <div className="company-setup-heading"><div><span className="overline">PERFIS DAS EMPRESAS</span><h2 id="company-setup-title">{configurationPending ? 'Vamos preparar suas próximas oportunidades.' : 'Cada empresa, uma busca própria.'}</h2>
      <p>{configurationPending ? 'A estrutura do Radar está pronta. Para começar a selecionar licitações, falta definir o que cada empresa oferece.' : 'O Radar seleciona editais pelos serviços e termos de cada perfil. Confira o objeto antes de participar.'}</p></div><Building2 size={26} aria-hidden="true" /></div>
    <div className="company-profile-grid">{companies.map(company => <article key={company.id} className="company-profile">
      <div><h3>{company.name}</h3><span className={company.enabled ? 'profile-ready' : 'profile-pending'}>{company.enabled ? <CircleCheck size={14} /> : <Clock3 size={14} />}{company.enabled ? 'Busca configurada' : 'Aguardando serviços'}</span></div>
      <p>{company.services.length ? company.services.join(' · ') : 'Produtos, serviços e objetos de interesse serão definidos com a empresa.'}</p>
    </article>)}</div>
    {configurationPending && <p className="company-next-step">Para ativar: reúna os serviços de cada empresa, exemplos de editais desejados, regiões atendidas e o que deve ficar fora da busca.</p>}
  </section>;
}
