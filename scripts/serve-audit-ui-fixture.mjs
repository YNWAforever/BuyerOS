/** Local Linux fixture for Windows Vite transport failures. No cloud deployment. */
import {spawn,spawnSync} from 'node:child_process';
import {mkdtempSync,writeFileSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {resolve,join,relative,isAbsolute} from 'node:path';
import {createHash} from 'node:crypto';
const root=resolve('.'),owner=createHash('sha256').update(root).digest('hex').slice(0,12);
const name=`buyeros-audit-ui-${owner}`,volume=`buyeros-audit-ui-deps-${owner}`;
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
 '-e','BUYEROS_DEPLOY_TARGET=vercel','-e','BUYEROS_INTERNAL_API_URL=http://host.docker.internal:8000',
 '-e','BUYEROS_API_BASE_URL=/','-e','BUYEROS_AUTH0_ISSUER=https://oidc.buyeros.test/',
 '-e','BUYEROS_AUTH0_CLIENT_ID=fixture-public-client','-e','BUYEROS_AUTH0_AUDIENCE=fixture-api',
 '-w','/src','node:22.23.2-bookworm-slim','sleep','infinity']);
writeFileSync('test-results/audit-ui-container.json',JSON.stringify({name,volume,owner,image:'node:22.23.2-bookworm-slim'}));
try {
 docker(['cp',join(work,'source.tar'),`${name}:/tmp/source.tar`]);
 docker(['exec',name,'sh','-c',`tar -xf /tmp/source.tar -C /src && mkdir -p /src/.sites-runtime && printf '%s' '{"executionProfile":"managed-linux"}' > /src/.sites-runtime/execution-profile.json`]);
} finally {const inside=relative(tmpdir(),work);if(isAbsolute(inside)||!inside.startsWith('buyeros-audit-ui-'))throw new Error('unsafe temp cleanup');rmSync(work,{recursive:true,force:true});}
const child=spawn('docker',['exec',name,'sh','-c','corepack pnpm install --frozen-lockfile && node scripts/run-framework.mjs dev'],{stdio:'inherit'});
let stopping=false;function stop(){if(stopping)return;stopping=true;spawnSync('docker',['rm','-f',name],{stdio:'ignore',timeout:30_000});}
process.once('SIGTERM',()=>{stop();process.exit(0);});process.once('SIGINT',()=>{stop();process.exit(0);});
child.once('exit',code=>{stop();process.exit(code??1);});
