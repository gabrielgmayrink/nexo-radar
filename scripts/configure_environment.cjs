// Private values arrive only through hidden stdin and are forwarded to Vercel's
// CLI on stdin. They are never put in command arguments, files or output.
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const {spawnSync}=require('node:child_process');
const scope='gabriels-projects-6ec97526',project='nexo-radar';
const linked=JSON.parse(fs.readFileSync('.vercel/project.json','utf8'));
if(linked.projectId!=='prj_tfJQ71F25cU2zmmMoNjLim4jSObq'||linked.orgId!=='team_o95aNRrdjrBWCJLdtgRqdTjU')throw Error('Unexpected deployment target');
const root=path.join(process.env.APPDATA,'npm','node_modules','vercel');
const manifest=JSON.parse(fs.readFileSync(path.join(root,'package.json'),'utf8'));
const cli=path.join(root,typeof manifest.bin==='string'?manifest.bin:manifest.bin.vercel);
if(process.stdin.isTTY)process.stdin.setRawMode(true);
process.stdin.setEncoding('utf8');
process.stdout.write('Ready for private configuration JSON on stdin (input is hidden).\n');
let buffer='';
process.stdin.on('data',chunk=>{
  buffer+=chunk;
  if(!/[\r\n]/.test(buffer))return;
  process.stdin.pause();
  try{
    const data=JSON.parse(buffer.trim());buffer='';
    const values={...data.values};
    if(data.newSigningSecret)values.FEEDBACK_SIGNING_SECRET=crypto.randomBytes(48).toString('base64url');
    const secrets=new Set(['SMTP_APP_PASSWORD','FEEDBACK_SIGNING_SECRET']);
    for(const [name,value] of Object.entries(values)){
      if(!/^(RADAR_[A-Z0-9_]+|SMTP_USERNAME|SMTP_APP_PASSWORD|FEEDBACK_SIGNING_SECRET)$/.test(name)||typeof value!=='string'||/[\r\n]/.test(value))throw Error('Invalid setting');
      const result=spawnSync(process.execPath,[cli,'env','add',name,'--environment','production','--force','--yes','--type',secrets.has(name)?'secret':'config','--project',project,'--scope',scope],{input:value+'\n',encoding:'utf8',timeout:60000});
      if(result.status!==0)throw Error('Could not configure '+name+' (no secret values logged)');
      process.stdout.write(JSON.stringify({configured:name,type:secrets.has(name)?'secret':'config'})+'\n');
    }
    process.exitCode=0;
  }catch(error){process.stderr.write(error.message+'\n');process.exitCode=1;}
  process.stdin.destroy();
});
