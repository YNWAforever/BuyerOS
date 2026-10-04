import {spawnSync} from 'node:child_process';
import {readFileSync,writeFileSync,existsSync} from 'node:fs';
import {createHash,randomBytes} from 'node:crypto';
import {resolve,relative,isAbsolute,join} from 'node:path';
const root=resolve('.'),area=resolve('test-results/local-gates');
const cacheOwner=createHash('sha256').update(root).digest('hex').slice(0,12);
const cache=`buyeros-audit-ui-deps-${cacheOwner}`;
const owner=randomBytes(12).toString('hex'),name=`buyeros-local-gates-${owner}`;
const image='node:22.23.2-bookworm-slim';
function run(command,args,options={}){const r=spawnSync(command,args,{encoding:'utf8',timeout:60_000,...options});if(r.status!==0)throw new Error(`${command} ${args[0]} exit ${r.status}: ${r.stderr}`);return r.stdout.trim();}
const volume=JSON.parse(run('docker',['volume','inspect',cache]))[0];
if(volume.Labels?.['buyeros.audit.owner']!==cacheOwner)throw new Error('unowned cache');
if(existsSync('.vercel/output'))throw new Error('refuse to overwrite an existing Vercel artifact');
const files=run('git',['ls-files','--cached','--others','--exclude-standard']).split(/\r?\n/).filter(Boolean)
  .filter(p=>!/^(services\/(api|worker|cloudflare-jobs)|docs|artifacts|tests|\.github)\//.test(p));
files.push('tests/vercel-render.test.mjs');
for(const p of files){const inside=relative(root,resolve(root,p));if(isAbsolute(inside)||inside.startsWith('..')||p.startsWith('.env'))throw new Error(`unsafe source ${p}`);}
const hashes=files.map(path=>({path,sha256:createHash('sha256').update(readFileSync(path)).digest('hex')}));
writeFileSync(join(area,'build-inputs.json'),JSON.stringify({sourceBase:run('git',['rev-parse','HEAD']),image,cache,cacheOwner,owner,name,files:hashes},null,2)+'\n');
writeFileSync(join(area,'build-files.txt'),files.join('\n')+'\n');
run('C:/Windows/System32/tar.exe',['-cf',join(area,'build-source.tar'),'-T',join(area,'build-files.txt')]);
let started=false;
try{
 run('docker',['run','-d','--name',name,'--label',`buyeros.local-gates.owner=${owner}`,'--cpus','4','--memory','6g',
   '--mount',`type=volume,src=${cache},dst=/src/node_modules`,'-w','/src',
   '-e','BUYEROS_DEPLOY_TARGET=vercel','-e','NITRO_PRESET=vercel','-e','BUYEROS_API_BASE_URL=/',
   '-e','BUYEROS_AUTH0_ISSUER=https://oidc.buyeros.test/','-e','BUYEROS_AUTH0_CLIENT_ID=fixture-public-client',
   '-e','BUYEROS_AUTH0_AUDIENCE=fixture-api',image,'sleep','infinity']); started=true;
 run('docker',['cp',join(area,'build-source.tar'),`${name}:/tmp/source.tar`]);
 run('docker',['exec',name,'tar','-xf','/tmp/source.tar','-C','/src']);
 const build=spawnSync('docker',['exec',name,'sh','-c',
   'corepack pnpm install --frozen-lockfile && timeout --signal=TERM --kill-after=10s 180s node scripts/run-vercel.mjs build'],
   {encoding:'utf8',timeout:240_000,maxBuffer:20*1024*1024});
 writeFileSync(join(area,'vercel-build.log'),(build.stdout??'')+(build.stderr??''));
 console.log(JSON.stringify({buildExit:build.status,error:build.error?.message,container:name}));
 if(build.status!==0)throw new Error('local Vercel build failed; see vercel-build.log');
 const render=spawnSync('docker',['exec',name,'node','--test','tests/vercel-render.test.mjs'],{encoding:'utf8',timeout:60_000});
 writeFileSync(join(area,'vercel-render-linux.log'),(render.stdout??'')+(render.stderr??''));
 if(render.status!==0)throw new Error('actual emitted Linux Vercel handler failed');
 const inspected=JSON.parse(run('docker',['inspect',name]))[0];
 writeFileSync(join(area,'build-runtime.json'),JSON.stringify({imageId:inspected.Image,
   node:run('docker',['exec',name,'node','--version']),cpus:inspected.HostConfig.NanoCpus,memory:inspected.HostConfig.Memory,
   preset:'vercel',buildExit:build.status,renderExit:render.status,renderEntry:'.vercel/output/functions/__server.func/index.mjs'},null,2)+'\n');
 run('docker',['exec',name,'tar','-chzf','/tmp/vercel-output.tar.gz','.vercel'],{timeout:180_000});
 run('docker',['cp',`${name}:/tmp/vercel-output.tar.gz`,join(area,'vercel-output.tar.gz')],{timeout:180_000});
 run('C:/Windows/System32/tar.exe',['-xzf',join(area,'vercel-output.tar.gz'),'-C',root],{timeout:180_000});
 console.log(render.stdout);
}finally{
 if(started){const proof=JSON.parse(run('docker',['inspect',name]))[0];
   if(proof.Config.Labels?.['buyeros.local-gates.owner']!==owner)throw new Error('refuse cleanup: ownership changed');
   run('docker',['rm','-f',name]);
   writeFileSync(join(area,'build-cleanup.json'),JSON.stringify({name,owner,removed:true,cacheRetained:cache},null,2)+'\n');
 }
}
