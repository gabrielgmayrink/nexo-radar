const fs=require('node:fs');
const {Resvg}=require('../web/node_modules/@resvg/resvg-js');
const renderer=new Resvg(fs.readFileSync('web/public/brand/nexo-symbol.svg'),{fitTo:{mode:'width',value:1024}});
fs.writeFileSync('web/public/brand/nexo-symbol-reference.png',renderer.render().asPng());
console.log('Rendered brand reference at 1024px.');
