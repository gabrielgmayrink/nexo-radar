import {createReadStream,createWriteStream} from 'node:fs';
import {pipeline} from 'node:stream/promises';
import {put,get,list,del} from '@vercel/blob';

const [operation,...args]=process.argv.slice(2);
const token=process.env.BLOB_READ_WRITE_TOKEN;
const option=name=>args[args.indexOf(name)+1];
try {
  if(!token)throw Error('Missing dedicated storage credential');
  if(operation==='list') {
    const result=await list({token,limit:1000,...(args.includes('--next')?{cursor:option('--next')}:{} )});
    process.stdout.write(JSON.stringify(result));
  } else if(operation==='put') {
    const result=await put(option('--pathname'),createReadStream(args[0]),{
      token,access:'private',addRandomSuffix:false,allowOverwrite:false,
      contentType:'application/octet-stream',cacheControlMaxAge:60,multipart:false,
    });
    process.stdout.write(JSON.stringify({pathname:result.pathname}));
  } else if(operation==='get') {
    const result=await get(args[0],{token,access:'private',useCache:false});
    if(!result || result.statusCode!==200)throw Error('Private archive unavailable');
    await pipeline(result.stream,createWriteStream(option('--output'),{flags:'wx',mode:0o600}));
    process.stdout.write('{}');
  } else if(operation==='delete') {
    await del(args[0],{token});process.stdout.write('{}');
  } else throw Error('Unsupported storage operation');
} catch(error) {
  // Never log provider messages, headers, tokens or file contents.
  process.stderr.write(JSON.stringify({event:'blob_transport_failed',errorType:error?.name || 'Error'}));
  process.exitCode=1;
}
