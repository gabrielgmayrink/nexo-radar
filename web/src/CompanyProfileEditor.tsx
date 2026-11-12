import { useEffect,useState } from 'react';
import { Save,Settings2 } from 'lucide-react';
import type { CompanyProfile } from './catalog';

type ProfileResponse={profile:CompanyProfile;version:number;canManage:boolean;updatedAt:string|null};
const list=(value:string)=>value.split(/\n|;/).map(item=>item.trim()).filter(Boolean);
export default function CompanyProfileEditor({company,onSaved}:{company:string;onSaved:()=>void}) {
  const [data,setData]=useState<ProfileResponse|null>(null),[profile,setProfile]=useState<CompanyProfile|null>(null);
  const [message,setMessage]=useState(''),[busy,setBusy]=useState(false),[synonyms,setSynonyms]=useState('');
  const [raw,setRaw]=useState<Record<string,string>>({});
  useEffect(()=>{const controller=new AbortController();setData(null);setMessage('');
    fetch('/api/profile?company='+encodeURIComponent(company),{signal:controller.signal,cache:'no-store'}).then(async response=>{const result=await response.json();if(!response.ok)throw Error(result.error || 'Não foi possível consultar o perfil.');return result as ProfileResponse;}).then(result=>{if(controller.signal.aborted)return;setData(result);setProfile(result.profile);setRaw(Object.fromEntries(['services','terms','excludeTerms','cities','modalities','states'].map(key=>[key,((result.profile as unknown as Record<string,string[]>)[key] || []).join(key==='states'?'; ':'\n')])));setSynonyms(Object.entries(result.profile.synonyms || {}).map(([term,values])=>term+' = '+values.join('; ')).join('\n'));}).catch(error=>{if(!controller.signal.aborted)setMessage(error.message);});
    return ()=>controller.abort();},[company]);
  function change(values:Partial<CompanyProfile>){setProfile(current=>current?{...current,...values}:current);}
  async function save(){if(!profile || !data)return;setBusy(true);setMessage('');try {
    const pairs=synonyms.split('\n').filter(line=>line.trim()).map(line=>{const separator=line.indexOf('=');if(separator<1)throw Error('Nos sinônimos, use termo = variação; outra variação.');return [line.slice(0,separator).trim(),list(line.slice(separator+1))] as const;});
    const {enabled,minValue,maxValue}=profile;
    const [services,terms,excludeTerms,states,cities,modalities]=['services','terms','excludeTerms','states','cities','modalities'].map(key=>list(raw[key] || ''));
    const response=await fetch('/api/profile?company='+encodeURIComponent(company),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({version:data.version,configuration:{enabled,services,terms,excludeTerms,states:states || [],cities:cities || [],modalities:modalities || [],minValue:minValue ?? null,maxValue:maxValue ?? null,synonyms:Object.fromEntries(pairs)}})});
    const result=await response.json();if(!response.ok)throw Error(result.error || 'Não foi possível salvar.');setData(result);setProfile(result.profile);setMessage('Critérios salvos. A seleção será atualizada em lotes, preservando avaliações e histórico.');onSaved();
  }catch(error){setMessage(error instanceof Error?error.message:'Não foi possível salvar.');}finally{setBusy(false);}}
  return <section className="profile-editor" aria-labelledby="profile-editor-title"><div className="heading-row"><div><span className="overline">CONFIGURAÇÃO DA EMPRESA</span><h2 id="profile-editor-title"><Settings2 size={21}/> Critérios de busca</h2></div>{data && <span className="snapshot-label">Versão {data.version}</span>}</div>
    <p>A coleta nacional continua sem filtro de empresa. Estes critérios organizam a seleção comercial e ficam registrados no histórico da sua equipe.</p>
    {!data && !message && <p role="status">Carregando critérios…</p>}
    {data && profile && <form onSubmit={event=>{event.preventDefault();void save();}}><fieldset disabled={!data.canManage || busy}><legend>Serviços e limites de atendimento</legend>
      <label className="profile-check"><input type="checkbox" checked={profile.enabled} onChange={event=>change({enabled:event.target.checked})}/> Ativar seleção de oportunidades</label>
      <div className="profile-grid">{([{key:'services',label:'Serviços oferecidos',help:'Um serviço por linha. Preserve somente o escopo que a empresa pode atender.'},{key:'terms',label:'Expressões de interesse',help:'Uma expressão por linha. Menções isoladas continuam sujeitas à análise do objeto.'},{key:'excludeTerms',label:'Expressões para exclusão',help:'Uma expressão por linha. A análise considera a intenção principal da contratação.'},{key:'cities',label:'Municípios atendidos',help:'Deixe vazio para todos os municípios.'},{key:'modalities',label:'Modalidades aceitas',help:'Uma modalidade por linha; deixe vazio para todas.'}] as const).map(field=><label key={field.key}>{field.label}<textarea rows={field.key==='services'?5:3} value={raw[field.key] || ''} onChange={event=>setRaw(current=>({...current,[field.key]:event.target.value}))}/><small>{field.help}</small></label>)}
      <label>Sinônimos<textarea rows={3} placeholder="apoio administrativo = suporte administrativo; rotinas de escritório" value={synonyms} onChange={event=>setSynonyms(event.target.value)}/><small>Uma relação por linha: termo = variação; outra variação.</small></label>
      <label>Estados (UF, separados por ponto e vírgula)<input value={raw.states || ''} maxLength={106} placeholder="Todos os estados" onChange={event=>setRaw(current=>({...current,states:event.target.value.toUpperCase()}))}/></label>
      <label>Valor mínimo estimado (R$)<input type="number" min="0" step="0.01" value={profile.minValue ?? ''} onChange={event=>change({minValue:event.target.value?Number(event.target.value):null})}/></label>
      <label>Valor máximo estimado (R$)<input type="number" min="0" step="0.01" value={profile.maxValue ?? ''} onChange={event=>change({maxValue:event.target.value?Number(event.target.value):null})}/></label></div>
      <p>Registros sem valor não passam por um limite de valor configurado. Para buscar no país inteiro, deixe os limites regionais vazios.</p>
      {data.canManage && <button type="submit" className="primary-button"><Save size={16}/>{busy?'Salvando…':'Salvar critérios da empresa'}</button>}
    </fieldset>{!data.canManage && <p>Apenas o responsável ou administrador desta empresa pode alterar os critérios.</p>}</form>}
    {message && <p role="status">{message}</p>}
  </section>;
}
