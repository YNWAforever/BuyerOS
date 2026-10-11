import assert from 'node:assert/strict';
import {test} from 'node:test';
import {existsSync,mkdtempSync,readFileSync,realpathSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join,basename,dirname} from 'node:path';
const target=new URL('./e2e/fixtures/owned-fixture-process.ts',import.meta.url);
async function runner(){assert.ok(existsSync(target),'owned fixture subprocess diagnostics missing');return (await import(target.href)).runOwnedFixtureProcess;}

test('owned fixture subprocess returns original successful JSON without diagnostics',async()=>{
 const run=await runner();const logs=[];const original=console.error;console.error=(...v)=>logs.push(v);
 try{const result=await run(process.execPath,['-e','process.stdout.write(JSON.stringify({owned:true}))'],{cwd:process.cwd(),timeout:10_000});assert.deepEqual(JSON.parse(result.stdout),{owned:true});assert.equal(result.stderr,'');assert.deepEqual(logs,[]);}
 finally{console.error=original;}
});

test('owned fixture subprocess preserves exit13, redacts DSN in thrown error and logs, and executes once',async()=>{
 const run=await runner();const root=mkdtempSync(join(tmpdir(),'c61-owned-fixture-'));const marker=join(root,'attempts');const logs=[];const original=console.error;console.error=(...v)=>logs.push(v);
 const secret='private-fixture-password';const dsn='postgresql://fixture:'+secret+'@127.0.0.1:5432/buyeros_test_only';
 const body="require('node:fs').appendFileSync(process.argv[1],'attempt\\n');process.stderr.write(process.argv[2]);process.exit(13)";
 try{let failure;try{await run(process.execPath,['-e',body,marker,dsn],{cwd:root,timeout:10_000});}catch(error){failure=error;}
  assert.ok(failure);assert.equal(failure.code,13);assert.equal(readFileSync(marker,'utf8'),'attempt\n');assert.equal(logs.length,1);assert.equal(logs[0][0],'C61_FIXTURE_PROCESS_FAILURE');
  const diagnostic=JSON.parse(logs[0][1]);assert.equal(diagnostic.code,13);assert.ok(diagnostic.stderr.includes('[REDACTED_FIXTURE_DSN]'));
  for(const value of [failure.message,failure.stack,failure.stdout,failure.stderr,JSON.stringify(logs)])assert.ok(!String(value).includes(secret));
 }finally{console.error=original;const resolved=realpathSync(root);assert.equal(dirname(resolved),realpathSync(tmpdir()));assert.ok(basename(resolved).startsWith('c61-owned-fixture-'));rmSync(resolved,{recursive:true,force:true});}
});

test('owned fixture subprocess timeout preserves killed signal and never retries',async()=>{
 const run=await runner();const logs=[];const original=console.error;console.error=(...v)=>logs.push(v);
 try{let failure;try{await run(process.execPath,['-e','setInterval(()=>{},1000)'],{cwd:process.cwd(),timeout:100});}catch(error){failure=error;}
  assert.ok(failure);assert.equal(failure.killed,true);assert.ok(failure.signal);assert.equal(logs.length,1);const diagnostic=JSON.parse(logs[0][1]);assert.equal(diagnostic.killed,true);assert.equal(diagnostic.signal,failure.signal);
 }finally{console.error=original;}
});
