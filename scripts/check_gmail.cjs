const {spawnSync}=require('node:child_process');
if(process.stdin.isTTY)process.stdin.setRawMode(true);
process.stdin.setEncoding('utf8');
process.stdout.write('Ready for private Gmail check JSON on stdin (input is hidden).\n');
let buffer='';
process.stdin.on('data',chunk=>{
  buffer+=chunk;if(!/[\r\n]/.test(buffer))return;process.stdin.pause();
  try {
    const data=JSON.parse(buffer.trim());buffer='';
    const result=spawnSync('.venv/Scripts/python.exe',['scripts/validate_smtp.py'],{input:JSON.stringify(data),encoding:'utf8',timeout:30000});
    process.stdout.write(result.stdout||JSON.stringify({gmailAuthentication:false,emailSent:false})+'\n');
    process.exitCode=result.status===0?0:1;
  } catch {process.stdout.write(JSON.stringify({gmailAuthentication:false,emailSent:false})+'\n');process.exitCode=1;}
  process.stdin.destroy();
});
