const fs=require('node:fs');
const {spawnSync}=require('node:child_process');
function git(args){const result=spawnSync('git',args,{encoding:'utf8'});if(result.status!==0)throw Error('Git failed: '+args[0]);return result.stdout}
const paths=['.env.example','.github','.gitignore','.vercelignore','README.md','api','docs','migrations','pyproject.toml','scripts','src','tests','vercel.json','web'];
git(['add','--',...paths]);
const files=git(['diff','--cached','--name-only','-z']).split('\0').filter(Boolean);
const sensitive=/-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\bgh[pousr]_[A-Za-z0-9]{30,}|\bgithub_pat_[A-Za-z0-9_]{30,}|\b(?:sb_secret_|sk-proj-)[A-Za-z0-9_-]{20,}/;
for(const file of files){
  if(file!=='.env.example'&&/(^|\/)(\.env[^/]*|node_modules|work|outputs|evaluation|\.vercel|\.venv|\.npm-cache)(\/|$)/.test(file))throw Error('Excluded path is staged');
  if(sensitive.test(fs.readFileSync(file,'utf8')))throw Error('Potential secret detected; commit cancelled');
}
git(['diff','--cached','--check']);
git(['commit','-m',process.argv[2]||'Prepara varredura nacional de todas as propostas abertas']);
console.log(JSON.stringify({committedFiles:files.length,secretScanPassed:true,commit:git(['rev-parse','HEAD']).trim()}));
