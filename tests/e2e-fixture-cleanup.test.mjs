import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readdir,readFile} from 'node:fs/promises';
import {mkdtempSync,writeFileSync,mkdirSync,existsSync,rmSync} from 'node:fs';
import {spawnSync} from 'node:child_process';
import {randomBytes} from 'node:crypto';
import {tmpdir} from 'node:os';
import {join,resolve,relative,isAbsolute} from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';

const root=fileURLToPath(new URL('../',import.meta.url));
const owner=randomBytes(12).toString('hex');
const label='buyeros.cleanup-test.owner';
const image='node:22.23.2-bookworm-slim';
const configs=(await readdir(root))
  .filter(name=>/^playwright(?:\.[a-z-]+)?\.config\.ts$/.test(name));

function docker(args){
  const result=spawnSync('docker',args,{encoding:'utf8',timeout:30_000});
  assert.equal(result.status,0,`docker ${args[0]}: ${result.stderr}`);
  return result.stdout.trim();
}
function inspect(name){
  const result=spawnSync('docker',['inspect',name],{encoding:'utf8',timeout:30_000});
  if(result.status===0)return JSON.parse(result.stdout)[0];
  assert.match(result.stderr,/no such (object|container)/i,result.stderr);
  return null;
}
function sentinel(name,extraLabels=[]){
  docker(['run','-d','--name',name,'--label',`${label}=${owner}`, ...extraLabels,
    '--network','none','--cpus','0.1','--memory','32m',image,'sleep','infinity']);
  assert.equal(inspect(name).Config.Labels[label],owner);
}
function removeOwned(name){
  const proof=inspect(name);
  if(!proof)return;
  assert.equal(proof.Config.Labels[label],owner,'refuse fallback cleanup of another run');
  docker(['rm','-f',name]);
}
function temporaryDirectory(){
  const path=mkdtempSync(join(tmpdir(),'buyeros-cleanup-gate-'));
  mkdirSync(join(path,'test-results'));
  return path;
}
function removeTemporary(path){
  const inside=relative(tmpdir(),path);
  assert.ok(!isAbsolute(inside)&&inside.startsWith('buyeros-cleanup-gate-')&&!inside.startsWith('..'));
  rmSync(path,{recursive:true,force:true});
}
// Node's native TS loader reads the real configured teardown. The narrowly
// scoped resolution hook supplies the extension for its existing TS import;
// no teardown or Docker boundary is mocked.
const invoke=`
  import {registerHooks} from 'node:module';
  import {pathToFileURL} from 'node:url';
  const scope=pathToFileURL(process.argv[2]).href;
  registerHooks({resolve(specifier,context,nextResolve){
    try{return nextResolve(specifier,context);}catch(error){
      if(error.code!=='ERR_MODULE_NOT_FOUND'||!specifier.startsWith('.')||!context.parentURL?.startsWith(scope))throw error;
      return nextResolve(specifier+'.ts',context);
    }
  }});
  const {default:cleanup}=await import(pathToFileURL(process.argv[1]).href);
  await cleanup();
`;
function runTeardown(entry,cwd){
  return spawnSync(process.execPath,['--input-type=module','-e',invoke,entry,join(root,'tests/e2e/')],
    {cwd,encoding:'utf8',timeout:30_000});
}
async function teardownEntries(configName){
  const {default:config}=await import(pathToFileURL(join(root,configName)).href);
  const entries=Array.isArray(config.globalTeardown)?config.globalTeardown:[config.globalTeardown];
  assert.ok(entries.length&&entries.every(entry=>typeof entry==='string'),'configured teardown is required');
  return entries.map(entry=>resolve(root,entry));
}

test('every disposable-API Playwright configuration actually removes its owned container and marker',async t=>{
  let checked=0;
  for(const name of configs){
    const source=await readFile(join(root,name),'utf8');
    if(!source.includes('serve_e2e_fixture.py'))continue;
    await t.test(name,async()=>{
      const entries=await teardownEntries(name);
      const cwd=temporaryDirectory(),container=`buyeros-test-${randomBytes(4).toString('hex')}`;
      const marker=join(cwd,'test-results/e2e-db-container.txt');
      try{
        sentinel(container);
        writeFileSync(marker,container+'\n');
        for(const entry of entries){const result=runTeardown(entry,cwd);assert.equal(result.status,0,result.stderr);}
        assert.equal(existsSync(marker),false,'database marker retained: teardown did not run');
        assert.equal(inspect(container),null,'owned disposable container retained');
      }finally{try{removeOwned(container);}finally{removeTemporary(cwd);}}
    });
    checked++;
  }
  assert.ok(checked>0,'no disposable-API configuration was verified');
});

test('configured audit teardown also removes its labelled UI sentinel and marker',async()=>{
  const cwd=temporaryDirectory(),uiOwner=randomBytes(6).toString('hex');
  const container=`buyeros-audit-ui-${uiOwner}`,marker=join(cwd,'test-results/audit-ui-container.json');
  try{
    sentinel(container,['--label',`buyeros.audit.owner=${uiOwner}`]);
    writeFileSync(marker,JSON.stringify({name:container,owner:uiOwner}));
    for(const entry of await teardownEntries('playwright.audit-fixes.config.ts')){
      const result=runTeardown(entry,cwd);assert.equal(result.status,0,result.stderr);
    }
    assert.equal(existsSync(marker),false);
    assert.equal(inspect(container),null);
  }finally{try{removeOwned(container);}finally{removeTemporary(cwd);}}
});

test('configured audit teardown refuses a UI container whose owner label differs',async()=>{
  const cwd=temporaryDirectory(),uiOwner=randomBytes(6).toString('hex');
  const container=`buyeros-audit-ui-${uiOwner}`,marker=join(cwd,'test-results/audit-ui-container.json');
  try{
    sentinel(container,['--label','buyeros.audit.owner=another-owner']);
    writeFileSync(marker,JSON.stringify({name:container,owner:uiOwner}));
    const [entry]=await teardownEntries('playwright.audit-fixes.config.ts');
    const result=runTeardown(entry,cwd);
    assert.notEqual(result.status,0);
    assert.match(result.stderr,/unowned UI fixture/);
    assert.equal(existsSync(marker),true);
    assert.equal(inspect(container).Config.Labels['buyeros.audit.owner'],'another-owner');
  }finally{try{removeOwned(container);}finally{removeTemporary(cwd);}}
});

test('configured database teardown refuses an unrecognized marker without deleting it',async()=>{
  const cwd=temporaryDirectory(),marker=join(cwd,'test-results/e2e-db-container.txt');
  try{
    writeFileSync(marker,'shared-production-database\n');
    const [entry]=await teardownEntries('playwright.config.ts');
    const result=runTeardown(entry,cwd);
    assert.notEqual(result.status,0);
    assert.match(result.stderr,/Refusing to clean an unrecognized E2E database container/);
    assert.equal(existsSync(marker),true);
  }finally{removeTemporary(cwd);}
});
