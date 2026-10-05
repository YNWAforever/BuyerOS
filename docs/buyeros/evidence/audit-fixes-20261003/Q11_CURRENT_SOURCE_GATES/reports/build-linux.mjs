import {spawn,spawnSync} from 'node:child_process';
import {readFileSync,writeFileSync,appendFileSync,existsSync,readdirSync,statSync,realpathSync} from 'node:fs';
import {createHash,randomBytes} from 'node:crypto';
import {resolve,relative,isAbsolute,join} from 'node:path';
const root=resolve('.'),area=resolve('test-results/q11-current-source-gates');
const seed='buyeros-audit-ui-deps-052d6a686de9',seedOwner='052d6a686de9';
const owner=randomBytes(12).toString('hex'),name=`buyeros-q11-gates-${owner}`;
const image='node:22.23.2-bookworm-slim';
function run(command,args,options={}){const r=spawnSync(command,args,{encoding:'utf8',timeout:60_000,maxBuffer:16*1024*1024,...options});if(r.status!==0)throw new Error(`${command} ${args[0]} exit ${r.status}: ${r.stderr??r.error?.message}`);return r.stdout.trim();}
async function logged(command,args,file,timeout){writeFileSync(file,'');return await new Promise((yes,no)=>{const p=spawn(command,args,{stdio:['ignore','pipe','pipe']});let timedOut=false;const timer=setTimeout(()=>{timedOut=true;p.kill();},timeout);p.stdout.on('data',x=>appendFileSync(file,x));p.stderr.on('data',x=>appendFileSync(file,x));p.on('error',e=>{clearTimeout(timer);no(e);});p.on('exit',(code,signal)=>{clearTimeout(timer);yes({code,signal,timedOut});});});}
const volume=JSON.parse(run('docker',['volume','inspect',seed]))[0];
if(volume.Labels?.['buyeros.audit.owner']!==seedOwner)throw new Error('unrecognized read-only seed');
if(existsSync('.vercel/output'))throw new Error('refuse to overwrite main Vercel output');
const files=run('git',['ls-files','--cached','--others','--exclude-standard']).split(/\r?\n/).filter(Boolean).filter(p=>! /^(services\/(api|worker|cloudflare-jobs)|docs|artifacts|tests|inputs|\.github|\.agents|\.codex|\.superpowers)\//.test(p));
files.push('tests/vercel-render.test.mjs');
for(const p of files){const inside=relative(root,realpathSync(resolve(root,p)));if(isAbsolute(inside)||inside==='..'||inside.startsWith('..\\')||inside.startsWith('../')||/(^|\/)\.env/.test(p))throw new Error(`unsafe input ${p}`);}
const hashes=files.map(path=>({path,sha256:createHash('sha256').update(readFileSync(path)).digest('hex')}));
writeFileSync(join(area,'build-inputs.json'),JSON.stringify({sourceBase:run('git',['rev-parse','HEAD']),image,readOnlySeed:seed,seedOwner,owner,name,files:hashes,overlay:false,liveVerification:false},null,2)+'\n');
writeFileSync(join(area,'build-files.txt'),files.join('\n')+'\n');
run('C:/Windows/System32/tar.exe',['-cf',join(area,'build-source.tar'),'-T',join(area,'build-files.txt')]);
let started=false;
try{
 run('docker',['run','-d','--name',name,'--label',`buyeros.q11-gates.owner=${owner}`,'--cpus','4','--memory','6g',
 '--mount',`type=volume,src=${seed},dst=/seed,readonly`,'-w','/src',
 '-e','CI=true',
 '-e','BUYEROS_DEPLOY_TARGET=vercel','-e','NITRO_PRESET=vercel','-e','BUYEROS_API_BASE_URL=/',
 '-e','BUYEROS_AUTH0_ISSUER=https://oidc.buyeros.test/','-e','BUYEROS_AUTH0_CLIENT_ID=fixture-public-client','-e','BUYEROS_AUTH0_AUDIENCE=fixture-api',image,'sleep','infinity']);started=true;
 run('docker',['cp',join(area,'build-source.tar'),`${name}:/tmp/source.tar`]);
 const setup=await logged('docker',['exec',name,'sh','-c','timeout --signal=TERM --kill-after=10s 240s sh -c "tar -xf /tmp/source.tar -C /src && mkdir -p /src/node_modules && cp -a /seed/. /src/node_modules/"'],join(area,'setup.log'),260_000);
 console.log(JSON.stringify({phase:'setup',...setup}));if(setup.code!==0)throw new Error('bounded seed setup failed');
 const install=await logged('docker',['exec',name,'sh','-c','timeout --signal=TERM --kill-after=10s 120s corepack pnpm install --frozen-lockfile'],join(area,'install.log'),140_000);
 console.log(JSON.stringify({phase:'install',...install}));if(install.code!==0)throw new Error('frozen install failed');
 run('docker',['network','disconnect','bridge',name]);
 const build=await logged('docker',['exec',name,'sh','-c','timeout --signal=TERM --kill-after=10s 180s node scripts/run-vercel.mjs build'],join(area,'vercel-build.log'),200_000);
 console.log(JSON.stringify({phase:'build',...build}));if(build.code!==0)throw new Error('genuine main Vercel build failed');
 const render=await logged('docker',['exec',name,'node','--test','--test-reporter=spec','--test-reporter-destination=/tmp/render.log','--test-reporter=junit','--test-reporter-destination=/tmp/render.xml','tests/vercel-render.test.mjs'],join(area,'render-process.log'),60_000);
 for(const [from,to]of [['render.log','vercel-render-linux.log'],['render.xml','vercel-render-linux.xml']])run('docker',['cp',`${name}:/tmp/${from}`,join(area,to)]);
 console.log(JSON.stringify({phase:'linuxSSR',...render}));if(render.code!==0)throw new Error('emitted Linux Vercel handler failed');
 const inspected=JSON.parse(run('docker',['inspect',name]))[0];
 writeFileSync(join(area,'build-runtime.json'),JSON.stringify({imageId:inspected.Image,node:run('docker',['exec',name,'node','--version']),cpus:inspected.HostConfig.NanoCpus,memory:inspected.HostConfig.Memory,preset:'vercel',setup,install,build,render,networks:Object.keys(inspected.NetworkSettings.Networks),renderEntry:'.vercel/output/functions/__server.func/index.mjs',liveVerification:false},null,2)+'\n');
 run('docker',['exec',name,'tar','-chzf','/tmp/vercel-output.tar.gz','.vercel'],{timeout:180_000});
 run('docker',['cp',`${name}:/tmp/vercel-output.tar.gz`,join(area,'vercel-output.tar.gz')],{timeout:180_000});
 const archive=join(area,'vercel-output.tar.gz');
 const members=run('C:/Windows/System32/tar.exe',['-tzf',archive],{timeout:180_000}).split(/\r?\n/);
 if(members.some(p=>p!=='.vercel/'&&(!p.startsWith('.vercel/')||p.split('/').includes('..')||p.includes('\\')||p.includes(':'))))throw new Error('unsafe artifact path');
 const kinds=run('C:/Windows/System32/tar.exe',['-tvzf',archive],{timeout:180_000}).split(/\r?\n/);
 if(kinds.some(p=>!/^[-d]/.test(p)))throw new Error('artifact must contain regular files/directories only');
 run('C:/Windows/System32/tar.exe',['-xzf',archive,'-C',root],{timeout:180_000});
 const outputs=[];function walk(dir){for(const item of readdirSync(dir,{withFileTypes:true})){const path=join(dir,item.name);if(item.isDirectory())walk(path);else if(item.isFile())outputs.push({path:relative(root,path).replaceAll('\\','/'),bytes:statSync(path).size,sha256:createHash('sha256').update(readFileSync(path)).digest('hex')});else throw new Error('unexpected output link');}}walk(resolve('.vercel/output'));
 writeFileSync(join(area,'build-output.json'),JSON.stringify({archive:{bytes:statSync(archive).size,sha256:createHash('sha256').update(readFileSync(archive)).digest('hex')},files:outputs},null,2)+'\n');
 console.log(JSON.stringify({phase:'export',files:outputs.length,archiveBytes:statSync(archive).size}));
}finally{
 if(started){const proof=JSON.parse(run('docker',['inspect',name]))[0];if(proof.Config.Labels?.['buyeros.q11-gates.owner']!==owner)throw new Error('refuse unowned cleanup');run('docker',['rm','-f',name]);const inspected=spawnSync('docker',['inspect',name],{encoding:'utf8',timeout:30_000});const absent=inspected.status!==0&&/no such (object|container)/i.test(inspected.stderr);if(!absent)throw new Error('cleanup not proved');writeFileSync(join(area,'build-cleanup.json'),JSON.stringify({name,owner,removed:true,seedRetainedReadOnly:seed,seedOwnerVerified:JSON.parse(run('docker',['volume','inspect',seed]))[0].Labels?.['buyeros.audit.owner']===seedOwner},null,2)+'\n');console.log(JSON.stringify({phase:'cleanup',removed:true}));}
}
