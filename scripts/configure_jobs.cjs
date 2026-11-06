// Repository credentials stay in process memory; job variables contain no secrets.
const {spawnSync}=require('node:child_process');
const owner='gabrielgmayrink',repository='nexo-radar';
const filled=spawnSync('git',['credential','fill'],{input:'protocol=https\nhost=github.com\nusername='+owner+'\n\n',encoding:'utf8',env:{...process.env,GIT_TERMINAL_PROMPT:'0',GCM_INTERACTIVE:'Never'},timeout:30000});
if(filled.status!==0)throw Error('GitHub authentication unavailable');
const values=Object.fromEntries(filled.stdout.trim().split(/\r?\n/).map(line=>{const at=line.indexOf('=');return[line.slice(0,at),line.slice(at+1)]}));
const headers={Authorization:'Bearer '+values.password,Accept:'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','User-Agent':'NexoRadar-setup'};
const base='/repos/'+owner+'/'+repository;
async function api(path,options={}){return fetch('https://api.github.com'+path,{...options,headers:{...headers,...options.headers},signal:AbortSignal.timeout(30000)})}
(async()=>{
  const identity=await api('/user');if(!identity.ok||(await identity.json()).login.toLowerCase()!==owner)throw Error('Unexpected GitHub identity');
  const mode=process.argv[2]||'configure';
  if(mode==='configure'){
    for(const [name,value] of Object.entries({RADAR_APP_URL:'https://nexo-radar-taupe.vercel.app',RADAR_COLLECTION_ENABLED:'1',RADAR_EMAIL_ENABLED:'0'})){
      const current=await api(base+'/actions/variables/'+name);
      const response=await api(base+'/actions/variables'+(current.ok?'/'+name:''),{method:current.ok?'PATCH':'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,value})});
      if(!response.ok)throw Error('Could not configure '+name+' (HTTP '+response.status+')');
    }
    console.log(JSON.stringify({variablesConfigured:true,emailScheduleEnabled:false}));return;
  }
  if(mode==='enable-email'){
    const response=await api(base+'/actions/variables/RADAR_EMAIL_ENABLED',{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:'RADAR_EMAIL_ENABLED',value:'1'})});
    if(!response.ok)throw Error('Could not enable email schedule');
    console.log(JSON.stringify({emailScheduleEnabled:true}));return;
  }
  if(mode==='verify-smtp'){
    const response=await api(base+'/actions/workflows/notify.yml/dispatches',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ref:'main',inputs:{kind:'verify_smtp'}})});
    if(!response.ok)throw Error('Could not dispatch verification (HTTP '+response.status+')');
    console.log(JSON.stringify({verificationRequested:true,emailSent:false}));return;
  }
  throw Error('Invalid operation');
})().catch(error=>{console.error(error.message);process.exit(1)});
