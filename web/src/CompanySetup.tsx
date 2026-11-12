import { BriefcaseBusiness, Building2, CircleCheck, FileText, GraduationCap, LockKeyhole, Mic2 } from 'lucide-react';
import { companies } from '../../src/radar/companies.json';
import type { CompanyProfile } from './catalog';

const serviceIcons = [FileText, BriefcaseBusiness, Mic2, GraduationCap];
export default function CompanySetup({company,profile:currentProfile}: {company:string;profile?:CompanyProfile}) {
  const profile=currentProfile || companies.find(item=>item.id===company);
  if (!profile) return null;
  return <section className="company-setup" aria-labelledby="company-setup-title">
    <div className="company-setup-heading"><div className="company-heading"><span className="company-avatar"><Building2 size={24}/></span><div><span className="overline">SEU ESPAÇO DE TRABALHO</span><h2 id="company-setup-title">{profile.name}</h2></div></div><span className={profile.enabled ? 'profile-ready' : 'profile-pending'}>{profile.enabled ? <CircleCheck size={14}/> : <LockKeyhole size={14}/>}{profile.enabled ? 'Perfil configurado' : 'Aguardando configuração'}</span></div>
    {profile.enabled ? <><p className="company-intro">A seleção considera os serviços e os limites de atendimento informados pela empresa.</p><ul className="company-services">{profile.services.map((service,index)=>{const Icon=serviceIcons[index] || BriefcaseBusiness;return <li key={service}><span><Icon size={19}/></span><p>{service}</p></li>;})}</ul></> : <div className="company-pending"><GraduationCap size={24}/><div><h3>Vamos definir o que sua empresa oferece.</h3><p>Informe os serviços, as regiões atendidas e exemplos de editais de interesse para começar a receber oportunidades próprias.</p></div></div>}
    <p className="company-privacy"><LockKeyhole size={13}/> Oportunidades e avaliações restritas à equipe {profile.name}.</p>
  </section>;
}
