/** Local acceptance only. Hosted probes require a separate explicit activation. */
import {createHash} from 'node:crypto';
import {spawn,execFileSync} from 'node:child_process';
import {mkdir,readFile,writeFile,rm} from 'node:fs/promises';
import {resolve,relative,sep,isAbsolute} from 'node:path';
import {fileURLToPath} from 'node:url';

const root=fileURLToPath(new URL('../',import.meta.url));
export function validateAcceptanceOptions(options,environment=process.env){
  if(options?.mode!=='local') throw new Error('protected preview requires separately authorized hosted probe setup');
  if(options.baseUrl!=='http://localhost:5173') throw new Error('acceptance target must be the owned loopback stack');
  for(const key of ['BUYEROS_TEST_DATABASE_URL','BUYEROS_REUSE_TEST_SERVER','CLOUDFLARE_API_TOKEN']){
    if(environment[key]) throw new Error(`unset inherited ${key}; the fixture must own its targets`);
  }
  if(typeof options.evidenceDir!=='string'||!options.evidenceDir) throw new Error('evidence directory is required');
  const directory=resolve(root,options.evidenceDir),inside=relative(root,directory);
  if(isAbsolute(inside) || !inside || inside==='..'||inside.startsWith(`..${sep}`)||inside.startsWith(sep)) throw new Error('evidence must stay inside this checkout');
  return {...options,evidenceDir:directory};
}
export function summarizeJUnit(xml){
  const suites=[...xml.matchAll(/<testsuite\s([^>]+)>?/g)];
  const counts={passed:0,failed:0,errors:0,skipped:0,total:0};
  for(const [,attributes] of suites){
    const number=name=>{const value=new RegExp(`(?:^|\\s)${name}="(\\d+)"`).exec(attributes);if(!value) throw new Error(`JUnit ${name} count absent`);return Number(value[1]);};
    counts.total+=number('tests');counts.failed+=number('failures');counts.errors+=number('errors');counts.skipped+=number('skipped');
  }
  counts.passed=counts.total-counts.failed-counts.errors-counts.skipped;
  if(counts.total<=0 || counts.failed || counts.errors || counts.skipped || counts.passed<0) throw new Error(`required acceptance did not pass:${JSON.stringify(counts)}`);
  return counts;
}
export async function beginAcceptanceEvidence(options){
  const valid=validateAcceptanceOptions(options);
  await mkdir(valid.evidenceDir,{recursive:true});
  for(const file of ['report.json','journey.xml']) await rm(resolve(valid.evidenceDir,file),{force:true});
  return valid;
}
export async function runCloudflareAcceptance(options){
  const valid=await beginAcceptanceEvidence(options);
  const started=new Date().toISOString();
  const junit=resolve(valid.evidenceDir,'journey.xml'),log=resolve(valid.evidenceDir,'journey.txt');
  const command=[process.execPath,'node_modules/@playwright/test/cli.js','test','--config','playwright.cloudflare.config.ts','--reporter=line,junit'];
  const environment=Object.fromEntries(Object.entries(process.env).filter(([key])=>!(/^(BUYEROS_|AUTH0_|R2_|VERCEL_|CLOUDFLARE_|DATABASE_URL|REDIS_URL|OPENAI_)/.test(key))));
  environment.BUYEROS_STRICT_INTEGRATION='1';environment.PLAYWRIGHT_JUNIT_OUTPUT_FILE=junit;
  environment.BUYEROS_AUTH0_ISSUER='https://oidc.buyeros.test/';
  environment.BUYEROS_AUTH0_CLIENT_ID='fixture-public-client';environment.BUYEROS_AUTH0_AUDIENCE='fixture-api';
  environment.BUYEROS_API_BASE_URL='/';
  const buildCommand=[process.execPath,'scripts/run-vercel.mjs','build'];
  const buildLog=resolve(valid.evidenceDir,'build.txt');
  await new Promise((done,reject)=>{
    const child=spawn(buildCommand[0],buildCommand.slice(1),{cwd:root,env:environment,windowsHide:true,stdio:['ignore','pipe','pipe']});
    let output='';
    child.stdout.on('data',chunk=>{output+=chunk;});child.stderr.on('data',chunk=>{output+=chunk;});
    child.once('error',reject);child.once('close',async code=>{
      await writeFile(buildLog,output,'utf8');
      if(code!==0) reject(new Error(`fixture Vercel build exited ${code}; see ${buildLog}`));else done();
    });
  });
  let output='';
  const code=await new Promise((done,reject)=>{
    const child=spawn(command[0],command.slice(1),{cwd:root,env:environment,windowsHide:true,stdio:['ignore','pipe','pipe']});
    const record=chunk=>{const text=chunk.toString();output+=text;process.stdout.write(text);};
    child.stdout.on('data',record);child.stderr.on('data',record);child.once('error',reject);child.once('close',done);
  });
  await writeFile(log,output,'utf8');
  if(code!==0) throw new Error(`local acceptance exited ${code}; see ${log}`);
  const counts=summarizeJUnit(await readFile(junit,'utf8'));
  const files=['services/cloudflare-jobs/src/dispatcher.ts','services/cloudflare-jobs/src/api-client.ts','services/cloudflare-jobs/src/protocol.ts','services/cloudflare-jobs/src/queue.ts','vite.config.ts','package.json','pnpm-lock.yaml','services/api/uv.lock','services/cloudflare-jobs/src/index.ts','services/cloudflare-jobs/src/workflow.ts','services/cloudflare-jobs/wrangler.jsonc','services/api/tools/serve_cloudflare_e2e.py','services/api/tools/serve_e2e_fixture.py','scripts/serve-cloudflare-fixture.mjs','scripts/serve-built-ui-fixture.mjs','scripts/run-cloudflare-acceptance.mjs','tests/e2e/cloudflare-journey.spec.ts','tests/e2e/fixtures/staff-journey.ts','playwright.cloudflare.config.ts'];
  const sourceFiles=Object.fromEntries(await Promise.all(files.map(async file=>[file,createHash('sha256').update(await readFile(resolve(root,file))).digest('hex')])));
  const report={mode:'local',baseUrl:valid.baseUrl,sourceHead:execFileSync('git',['rev-parse','HEAD'],{cwd:root,encoding:'utf8'}).trim(),sourceFiles,started,finished:new Date().toISOString(),buildCommand,buildExitCode:0,command,exitCode:code,counts,
    evidence:{identity:'fictional OIDC/machine identity',provider:'fictional bounded search and unknown lookup acceptance',transport:'actual local Queue/Workflow -> HMAC native API -> owned PostgreSQL16',frontend:'actual emitted Vercel function/static assets; runtime loopback app-to-API binding',scheduledIntervalMilliseconds:1000,productionCronSeconds:60,hosted:'not run',deployed:false}};
  await writeFile(resolve(valid.evidenceDir,'report.json'),JSON.stringify(report,null,2)+'\n','utf8');return report;
}
if(process.argv[1]&&resolve(process.argv[1])===fileURLToPath(import.meta.url)){
  const report=await runCloudflareAcceptance({mode:'local',baseUrl:'http://localhost:5173',evidenceDir:'artifacts/cloudflare/acceptance'});
  console.log(JSON.stringify(report.counts));
}
