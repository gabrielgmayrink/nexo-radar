// The GitHub connector has no repository-creation operation. Use the selected
// Git Credential Manager account; keep its credential in process memory only.
const {spawnSync}=require('node:child_process');
const expected='gabrielgmayrink', name='nexo-radar';
const result=spawnSync('git',['credential','fill'],{input:'protocol=https\nhost=github.com\nusername='+expected+'\n\n',encoding:'utf8',env:{...process.env,GIT_TERMINAL_PROMPT:'0',GCM_INTERACTIVE:'Never'},timeout:30000});
if(result.status!==0) throw Error('A conta gabrielgmayrink precisa estar autenticada no Git Credential Manager.');
const credential=Object.fromEntries(result.stdout.trim().split(/\r?\n/).map(line=>{const at=line.indexOf('=');return[line.slice(0,at),line.slice(at+1)]}));
if(!credential.password)throw Error('GitHub authentication unavailable');
const headers={Authorization:'Bearer '+credential.password,Accept:'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','User-Agent':'RadarPublicGerico-setup'};
async function api(path,options={}){return fetch('https://api.github.com'+path,{...options,headers:{...headers,...options.headers},signal:AbortSignal.timeout(30000)})}
(async()=>{
  const response=await api('/user');if(!response.ok)throw Error('GitHub identity check failed (HTTP '+response.status+')');
  const user=await response.json();if(user.login.toLowerCase()!==expected)throw Error('Unexpected GitHub identity; no changes made');
  const existing=await api('/repos/'+expected+'/'+name);let repo;
  if(existing.status===404){
    const created=await api('/user/repos',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,private:true,auto_init:false,description:'Radar PNCP para Public e Gerico, com perfis de serviços independentes.'})});
    if(!created.ok)throw Error('Repository creation failed (HTTP '+created.status+')');repo=await created.json();
  }else if(existing.ok){repo=await existing.json();if(repo.size>0)throw Error('Repository already has content; no changes made');}
  else throw Error('Repository inspection failed (HTTP '+existing.status+')');
  if(!repo.private)throw Error('Expected a private repository');
  for(const [key,value] of [['user.name',user.name||user.login],['user.email',user.id+'+'+user.login+'@users.noreply.github.com']]){
    const changed=spawnSync('git',['config','--local',key,value],{encoding:'utf8'});if(changed.status!==0)throw Error('Cannot configure Git author');
  }
  console.log(JSON.stringify({account:user.login,repository:repo.html_url,repositoryId:repo.id,private:repo.private}));
})().catch(error=>{console.error(error.message);process.exit(1)});
