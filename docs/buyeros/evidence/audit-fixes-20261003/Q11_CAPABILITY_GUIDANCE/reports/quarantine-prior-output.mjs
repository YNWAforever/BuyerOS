import {readFileSync,readdirSync,lstatSync,realpathSync,existsSync,renameSync,writeFileSync} from 'node:fs';
import {resolve,relative,isAbsolute,join} from 'node:path';
import {createHash} from 'node:crypto';
const root=realpathSync('.'), src=resolve('.vercel/output'),dest=resolve('test-results/q11-capability-guidance/prior-main-output');
for(const p of [src,dest]){const r=relative(root,p);if(isAbsolute(r)||r==='..'||r.startsWith('..\\')||r.startsWith('../'))throw Error('outside workspace');}
if(existsSync(dest))throw Error('destination exists');
const manifest=JSON.parse(readFileSync('test-results/q11-current-source-gates/build-output.json','utf8'));let count=0;
function walk(p){for(const name of readdirSync(p)){const file=join(p,name),s=lstatSync(file);if(s.isDirectory())walk(file);else if(s.isFile())count++;else throw Error('unexpected link');}}walk(src);
if(count!==manifest.files.length)throw Error('unexpected output count');
for(const item of manifest.files){if(!item.path.startsWith('.vercel/output/'))throw Error('unowned manifest path');const p=realpathSync(item.path),r=relative(src,p);if(isAbsolute(r)||r.startsWith('..'))throw Error('unsafe output');if(createHash('sha256').update(readFileSync(p)).digest('hex')!==item.sha256)throw Error(`output changed ${item.path}`);}
renameSync(src,dest);writeFileSync('test-results/q11-capability-guidance/prior-output-quarantine.json',JSON.stringify({source:src,destination:dest,verifiedFiles:count,unchanged:true,rollback:'Rename destination back to source when the new owned output has been moved aside.'},null,2)+'\n');console.log(`Preserved ${count} verified prior files`);
