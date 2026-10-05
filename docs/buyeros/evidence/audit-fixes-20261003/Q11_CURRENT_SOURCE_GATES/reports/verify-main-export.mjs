import {readFileSync,readdirSync,writeFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {resolve,join,relative} from 'node:path';
const root=resolve('.'),area=resolve('test-results/q11-current-source-gates');
const expected=JSON.parse(readFileSync(join(area,'build-output-expected.json'),'utf8'));
const map=new Map(expected.files.map(x=>[x.path,x]));let checked=0;
function walk(dir){for(const x of readdirSync(dir,{withFileTypes:true})){const p=join(dir,x.name);if(x.isDirectory())walk(p);else {if(!x.isFile())throw new Error('unexpected emitted link');const path=relative(root,p).replaceAll('\\','/'),item=map.get(path),bytes=readFileSync(p);if(!item||item.bytes!==bytes.length||item.sha256!==createHash('sha256').update(bytes).digest('hex'))throw new Error(`emitted mismatch ${path}`);checked++;}}}
walk(resolve('.vercel/output'));if(checked!==map.size)throw new Error('incomplete emitted output');writeFileSync(join(area,'build-output.json'),JSON.stringify({...expected,verified_export:{files:checked,bytesMatch:true,sha256Match:true,regularFilesOnly:true}},null,2)+'\n');console.log(JSON.stringify({verified_export_files:checked}));
