const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const base='https://raw.githubusercontent.com/DavidHDev/react-bits/main/';
const directory=path.join('web','src','components','reactbits');
const resources=[['src/ts-default/Components/SpotlightCard/SpotlightCard.tsx','SpotlightCard.tsx'],['src/ts-default/Components/SpotlightCard/SpotlightCard.css','SpotlightCard.css'],['src/ts-default/TextAnimations/BlurText/BlurText.tsx','BlurText.tsx'],['LICENSE.md','LICENSE.md']];
(async()=>{
  fs.mkdirSync(directory,{recursive:true});
  const manifest=[];
  for(const [source,target] of resources){
    const response=await fetch(base+source,{signal:AbortSignal.timeout(30000)});
    if(!response.ok)throw Error('Cannot download React Bits source: HTTP '+response.status);
    const body=await response.text();fs.writeFileSync(path.join(directory,target),body);
    manifest.push({source:base+source,file:target,sha256:crypto.createHash('sha256').update(body).digest('hex')});
  }
  fs.writeFileSync(path.join(directory,'UPSTREAM.json'),JSON.stringify({project:'React Bits',author:'David Haz',retrievedAt:'2026-11-06',usage:'Integrated UI components in Nexo Radar',resources:manifest},null,2)+'\n');
  console.log(JSON.stringify({downloaded:manifest.map(item=>item.file)}));
})().catch(error=>{console.error(error.message);process.exit(1)});
