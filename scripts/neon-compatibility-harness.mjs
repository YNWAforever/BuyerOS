import {spawnSync} from 'node:child_process';
import {createHash,randomBytes} from 'node:crypto';
import {existsSync,readFileSync,writeFileSync,mkdirSync,copyFileSync,lstatSync,readdirSync,rmSync,realpathSync} from 'node:fs';
import {resolve,relative,isAbsolute,join,dirname} from 'node:path';
import {pathToFileURL} from 'node:url';
export function assertLoopbackUrl(value) {
 const url=new URL(value);
 if(url.protocol!=='http:'||!['127.0.0.1','localhost','[::1]'].includes(url.hostname)||url.username||url.password)throw new Error('N00 requires an owned loopback fixture URL');
 return url;
}
export function assertSourcePath(value) {
 const segments=value.split('/');
 if(!value||isAbsolute(value)||/[\\:]/.test(value)||segments.some(s=>!s||s==='.'||s==='..'||/^\.env/i.test(s)||['.git','node_modules','test-results','.vercel'].includes(s)))throw new Error(`unsafe N00 source: ${value}`);
 return value;
}
export function isBuildSource(path) {return !/^(services\/(api|worker|cloudflare-jobs)|docs|artifacts|tests|spikes|\.github)\//.test(path)&&!path.endsWith('.tmp');}
export function staticAssetPath(root,pathname) {
 const part=decodeURIComponent(pathname).replace(/^\//,'');assertSourcePath(part);
 const path=resolve(root,part),inside=relative(resolve(root),path);
 if(isAbsolute(inside)||inside.startsWith('..'))throw new Error('unsafe static asset path');return path;
}
export function assertProtocolStorage(entries) {
 for(const [key,value] of entries) {
  if(key!=='buyeros-prefs-v1')throw new Error('unexpected persisted N00 state');
  const prefs=JSON.parse(value);
  if(!prefs||!['en','zh-HK'].includes(prefs.locale)||value!==JSON.stringify({locale:prefs.locale}))throw new Error('only canonical locale preferences may persist');
 }
}
export function fixtureChildEnvironment(parent) {
 const env=Object.fromEntries(['PATH','Path','SystemRoot','SYSTEMROOT','TEMP','TMP','COMSPEC','PATHEXT','USERPROFILE','LOCALAPPDATA'].filter(key=>parent[key]).map(key=>[key,parent[key]]));
 return {...env,BUYEROS_STRICT_INTEGRATION:'1',WRANGLER_SEND_METRICS:'false',WRANGLER_WRITE_LOGS:'false',CLOUDFLARE_CF_FETCH_ENABLED:'false'};
}
export function assertSeedMetadata(seed,owner,labels) {
 if(!/^[a-f0-9]{12}$/.test(owner??'')||seed!==`buyeros-audit-ui-deps-${owner}`||labels?.['buyeros.audit.owner']!==owner)throw new Error('unowned read-only dependency seed');
}
export function compatibilityViteConfig(input) {
 const marker='.nitro({ vercel: ';
 if(input.split(marker).length!==2)throw new Error('N00 fixture requires the reviewed Nitro build interface');
 return input.replace(marker,'.nitro({ experimental: { vite: { services: { rsc: { entry: "./lib/neon-compatibility/rsc-service.ts" } } } }, vercel: ');
}
function run(cmd,args,options={}) {
 const result=spawnSync(cmd,args,{encoding:'utf8',timeout:60_000,maxBuffer:32*1024*1024,...options});
 if(result.status!==0)throw new Error(`${cmd} failed (${result.status}): ${result.error?.message ?? result.stderr}`);
 return result.stdout.trim();
}
export function buildFixture() {
 const root=resolve('.'),area=resolve('test-results/neon-compatibility');
 if(existsSync(join(area,'build-inputs.json')))throw new Error('refuse to overwrite an existing N00 build proof');
 const seed=process.env.BUYEROS_N00_SEED_VOLUME;
 if(seed){const seedProof=JSON.parse(run('docker',['volume','inspect',seed]))[0];assertSeedMetadata(seed,process.env.BUYEROS_N00_SEED_OWNER,seedProof.Labels);}
 mkdirSync(area,{recursive:true});
 const source=join(area,'source');mkdirSync(source);
 const files=run('git',['ls-files','--cached','--others','--exclude-standard']).split(/\r?\n/).filter(Boolean)
  .filter(isBuildSource);
 const hashes=[];
 function copy(p,destination=p) {
  assertSourcePath(p);assertSourcePath(destination);
  const absolute=resolve(root,p),inside=relative(root,absolute);
  if(isAbsolute(inside)||inside.startsWith('..')||!lstatSync(absolute).isFile())throw new Error(`unsafe source file ${p}`);
  mkdirSync(dirname(join(source,destination)),{recursive:true});copyFileSync(absolute,join(source,destination));
  const output=join(source,destination);
  if(destination==='vite.config.ts')writeFileSync(output,compatibilityViteConfig(readFileSync(absolute,'utf8')));
  hashes.push({path:p,destination,sha256:createHash('sha256').update(readFileSync(absolute)).digest('hex'),stagedSha256:createHash('sha256').update(readFileSync(output)).digest('hex')});
 }
 for(const p of files)copy(p);
 const overlay='tests/fixtures/neon-compatibility/overlay';
 function walk(folder) {for(const entry of readdirSync(folder,{withFileTypes:true})){const path=join(folder,entry.name);if(entry.isDirectory())walk(path);else if(entry.isFile()){const from=relative(root,path).replaceAll('\\','/');copy(from,relative(resolve(overlay),path).replaceAll('\\','/'));}else throw new Error('overlay symlink refused');}}
 walk(overlay);
 const owner=randomBytes(12).toString('hex'),name=`buyeros-n00-${owner}`,image='node:22.23.2-bookworm-slim';
 writeFileSync(join(area,'build-inputs.json'),JSON.stringify({base:run('git',['rev-parse','HEAD']),owner,name,image,readOnlySeed:seed,files:hashes,liveVerification:false},null,2)+'\n');
 const tar=process.platform==='win32'?'C:/Windows/System32/tar.exe':'tar';
 run(tar,['-cf',join(area,'source.tar'),'-C',source,'.']);
 if(realpathSync(source)!==join(realpathSync(area),'source'))throw new Error('unsafe staging cleanup path');
 rmSync(source,{recursive:true});
 let started=false;
 try {
  run('docker',['run','-d','--name',name,'--label',`buyeros.n00.owner=${owner}`,'--cpus','4','--memory','6g',...(seed?['--mount',`type=volume,src=${seed},dst=/seed,readonly`]:[]),'-w','/src',
   '-e','WRANGLER_SEND_METRICS=false','-e','CLOUDFLARE_CF_FETCH_ENABLED=false',image,'sleep','infinity']);started=true;
  run('docker',['cp',join(area,'source.tar'),`${name}:/tmp/source.tar`]);
  run('docker',['exec',name,'tar','-xf','/tmp/source.tar','-C','/src']);
  if(seed){run('docker',['exec',name,'mkdir','-p','/src/node_modules']);run('docker',['exec',name,'sh','-c','tar -C /seed -cf - . | tar -C /src/node_modules -xf -'],{timeout:360_000});}
  const install=spawnSync('docker',['exec',name,'sh','-c','corepack pnpm install --frozen-lockfile'],{encoding:'utf8',timeout:300_000,maxBuffer:32*1024*1024});
  writeFileSync(join(area,'install-linux.log'),(install.stdout??'')+(install.stderr??''));
  if(install.status!==0)throw new Error(`Linux frozen install exit${install.status}`);
  const proof={node:run('docker',['exec',name,'node','--version']),imageId:JSON.parse(run('docker',['inspect',name]))[0].Image,cpus:4,memoryGiB:6,outputs:[]};
  for(const [target,command,output] of [['portable','corepack pnpm build','dist'],['vercel','node scripts/run-vercel.mjs build','.vercel']]) {
   run('docker',['exec',name,'sh','-c','test "$(pwd)" = /src && rm -rf /src/dist /src/.vercel /src/.vinext']);
   const result=spawnSync('docker',['exec',name,'sh','-c',`timeout --signal=TERM --kill-after=10s 300s ${command}`],{encoding:'utf8',timeout:330_000,maxBuffer:32*1024*1024});
   writeFileSync(join(area,`${target}-build.log`),(result.stdout??'')+(result.stderr??''));
   proof.outputs.push({target,command,exit:result.status,error:result.error?.message??null});
   writeFileSync(join(area,'build-runtime.json'),JSON.stringify(proof,null,2)+'\n');
   console.log(`${target}: exit ${result.status}`);
   if(result.status!==0)continue;
   run('docker',['exec',name,'tar','-chzf',`/tmp/${target}.tar.gz`,output],{timeout:180_000});
   run('docker',['cp',`${name}:/tmp/${target}.tar.gz`,join(area,`${target}.tar.gz`)],{timeout:180_000});
   const destination=join(area,target);mkdirSync(destination);
   run(tar,['-xzf',join(area,`${target}.tar.gz`),'-C',destination],{timeout:180_000});
  }
  if(proof.outputs.some(output=>output.exit!==0))throw new Error('N00 output build failed; retain exact logs');
 }finally {
  if(started) {
   const container=JSON.parse(run('docker',['inspect',name]))[0];
   if(container.Config.Labels?.['buyeros.n00.owner']!==owner)throw new Error('cleanup ownership mismatch');
   run('docker',['rm','-f',name]);writeFileSync(join(area,'cleanup.json'),JSON.stringify({owner,name,removed:true})+'\n');
  }
 }
}
if(process.argv[1]&&import.meta.url===pathToFileURL(resolve(process.argv[1])).href)buildFixture();
