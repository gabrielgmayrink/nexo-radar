const {spawnSync}=require('node:child_process');
const expected='gabrielgmayrink';
const result=spawnSync('git',['credential','fill'],{input:'protocol=https\nhost=github.com\nusername='+expected+'\n\n',encoding:'utf8',env:{...process.env,GIT_TERMINAL_PROMPT:'0',GCM_INTERACTIVE:'Never'},timeout:30000});
if(result.status!==0)throw Error('GitHub authentication unavailable');
const values=Object.fromEntries(result.stdout.trim().split(/\r?\n/).map(line=>{const at=line.indexOf('=');return[line.slice(0,at),line.slice(at+1)]}));
const headers={Authorization:'Bearer '+values.password,Accept:'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','User-Agent':'NexoRadar-setup'};
async function api(path,options={}){return fetch('https://api.github.com'+path,{...options,headers:{...headers,...options.headers},signal:AbortSignal.timeout(30000)})}
(async()=>{
  const identity=await api('/user');if(!identity.ok||(await identity.json()).login.toLowerCase()!==expected)throw Error('Unexpected GitHub account');
  const current=await api('/repositories/1448230071');if(!current.ok)throw Error('Cannot inspect repository');
  let repo=await current.json();if(repo.owner.login!==expected||!repo.private)throw Error('Unexpected repository');
  if(repo.name!=='nexo-radar'){
    const renamed=await api('/repositories/1448230071',{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:'nexo-radar',description:'Nexo Radar: inteligência em licitações, com perfis independentes por empresa.'})});
    if(!renamed.ok)throw Error('Rename failed (HTTP '+renamed.status+')');repo=await renamed.json();
  }
  const remote=spawnSync('git',['remote','get-url','origin'],{encoding:'utf8'});
  const configured=spawnSync('git',remote.status===0?['remote','set-url','origin',repo.clone_url]:['remote','add','origin',repo.clone_url],{encoding:'utf8'});
  if(configured.status!==0)throw Error('Cannot configure local remote');
  console.log(JSON.stringify({url:repo.html_url,private:repo.private,repositoryId:repo.id}));
})().catch(error=>{console.error(error.message);process.exit(1)});
