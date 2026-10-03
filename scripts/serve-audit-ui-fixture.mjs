/** Local Linux fixture for Windows Vite transport failures. No cloud deployment. */
import {spawn,spawnSync} from 'node:child_process';
import {mkdtempSync,writeFileSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {resolve,join,relative,isAbsolute} from 'node:path';
import {createHash} from 'node:crypto';
const root=resolve('.'),owner=createHash('sha256').update(root).digest('hex').slice(0,12);
const name=`buyeros-audit-ui-${owner}`,volume=`buyeros-audit-ui-deps-${owner}`;
const mode=process.env.BUYEROS_AUDIT_UI_MODE??'http';
if(!['http','demo'].includes(mode))throw new Error('unrecognized audit UI mode');
const runtime=process.env.BUYEROS_AUDIT_UI_RUNTIME??'dev';
if(!['dev','built'].includes(runtime)||mode==='demo'&&runtime!=='dev')throw new Error('unrecognized audit UI runtime');
const docker=(args)=>{const r=spawnSync('docker',args,{encoding:'utf8',timeout:60_000});if(r.status!==0)throw new Error(`docker ${args[0]} failed: ${r.stderr}`);return r.stdout.trim();};
const exists=spawnSync('docker',['volume','inspect',volume],{encoding:'utf8'});
if(exists.status===0){const v=JSON.parse(exists.stdout)[0];if(v.Labels?.['buyeros.audit.owner']!==owner)throw new Error('unowned fixture cache');}
else docker(['volume','create','--label',`buyeros.audit.owner=${owner}`,volume]);
const work=mkdtempSync(join(tmpdir(),'buyeros-audit-ui-'));
const source=spawnSync('git',['ls-files','--cached','--others','--exclude-standard'],{encoding:'utf8'});
if(source.status!==0)throw new Error('source inventory failed');
const files=source.stdout.split(/\r?\n/).filter(Boolean).filter(p=>! /^(services\/(api|worker|cloudflare-jobs)|docs|artifacts|tests)\//.test(p));
for(const p of files){const inside=relative(root,resolve(root,p));if(isAbsolute(inside)||inside.startsWith('..')||p.startsWith('.env'))throw new Error('unsafe source file');}
writeFileSync(join(work,'files.txt'),files.join('\n')+'\n');
const tar=spawnSync('tar',['-cf',join(work,'source.tar'),'-T',join(work,'files.txt')],{cwd:root,encoding:'utf8',timeout:60_000});
if(tar.status!==0)throw new Error(tar.stderr);
docker(['run','-d','--name',name,'--label',`buyeros.audit.owner=${owner}`,'--cpus','4','--memory','6g',
 '-p','127.0.0.1:5173:3000','--mount',`type=volume,src=${volume},dst=/src/node_modules`,
 '-e',`BUYEROS_DEPLOY_TARGET=${mode==='http'?'vercel':''}`,'-e','BUYEROS_INTERNAL_API_URL=http://host.docker.internal:8000',
 '-e',`BUYEROS_API_BASE_URL=${mode==='http'?'/':''}`,'-e',`BUYEROS_AUTH0_ISSUER=${mode==='http'?'https://oidc.buyeros.test/':''}`,
 '-e',`BUYEROS_AUTH0_CLIENT_ID=${mode==='http'?'fixture-public-client':''}`,'-e',`BUYEROS_AUTH0_AUDIENCE=${mode==='http'?'fixture-api':''}`,
 ...(runtime==='built'?['-e','NITRO_PRESET=node-server','-e','PORT=3000','-e','HOST=0.0.0.0']:[]),
 '-w','/src','node:22.23.2-bookworm-slim','sleep','infinity']);
const executionProfile=mode==='demo'?'portable':'managed-linux';
writeFileSync('test-results/audit-ui-container.json',JSON.stringify({name,volume,owner,mode,runtime,executionProfile,image:'node:22.23.2-bookworm-slim'}));
try {
 docker(['cp',join(work,'source.tar'),`${name}:/tmp/source.tar`]);
 docker(['exec',name,'sh','-c',`tar -xf /tmp/source.tar -C /src && mkdir -p /src/.sites-runtime && printf '%s' '${JSON.stringify({executionProfile})}' > /src/.sites-runtime/execution-profile.json`]);
} finally {const inside=relative(tmpdir(),work);if(isAbsolute(inside)||!inside.startsWith('buyeros-audit-ui-'))throw new Error('unsafe temp cleanup');rmSync(work,{recursive:true,force:true});}
// Installed Nitro supports NITRO_PRESET. Build only the owned local container,
// bound the build, verify its actual entrypoint, then serve the compiled handler.
const serve=runtime==='built'
 ? 'timeout --signal=TERM --kill-after=10s 180s node node_modules/vite/bin/vite.js build && test -f .output/server/index.mjs && node .output/server/index.mjs'
 // Demo uses the existing portable Sites mock-auth profile inside this owned fixture only.
 : mode==='demo'?'node node_modules/vite/bin/vite.js dev --host 0.0.0.0 --port 3000':'node scripts/run-framework.mjs dev';
const child=spawn('docker',['exec',name,'sh','-c',`corepack pnpm install --frozen-lockfile && ${serve}`],{stdio:'inherit'});
let stopping=false;function stop(){if(stopping)return;stopping=true;spawnSync('docker',['rm','-f',name],{stdio:'ignore',timeout:30_000});}
process.once('SIGTERM',()=>{stop();process.exit(0);});process.once('SIGINT',()=>{stop();process.exit(0);});
child.once('exit',code=>{stop();process.exit(code??1);});
