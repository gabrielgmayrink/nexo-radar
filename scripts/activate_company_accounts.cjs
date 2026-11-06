// Passwords are received through hidden stdin, never arguments, files or logs.
const {spawnSync}=require('node:child_process');
if(process.stdin.isTTY)process.stdin.setRawMode(true);
process.stdin.setEncoding('utf8');
process.stdout.write('Ready for private account configuration on stdin (input is hidden).\n');
let buffer='';
process.stdin.on('data',chunk=>{
  buffer+=chunk;
  if(!/[\r\n]/.test(buffer))return;
  process.stdin.pause();
  try{
    const input=JSON.stringify(JSON.parse(buffer.trim()));buffer='';
    const result=spawnSync('.venv/Scripts/python.exe',['scripts/activate_company_accounts.py'],{input,encoding:'utf8',timeout:180000});
    if(result.stdout)process.stdout.write(result.stdout);
    if(result.status!==0)throw Error('Account configuration did not complete; no passwords were logged.');
    process.exitCode=0;
  }catch{process.stderr.write('Account configuration did not complete; no passwords were logged.\n');process.exitCode=1;}
  process.stdin.destroy();
});
