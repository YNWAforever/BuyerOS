import assert from 'node:assert/strict';
import {loadModule} from './ts-loader.mjs';

const {BuyerImportWorkflow}=await loadModule('services/live/buyer-import.ts');
const {SessionScope}=await loadModule('services/live/session.ts');
const {LiveCancelled}=await loadModule('services/live/client.ts');
const session=()=>{const s=new SessionScope({mode:'live',actor:'operator',workspace:'workspace',project:'project'});s.setToken('fixture');return s;};
const preview={id:'import-1',preview_digest:'sha256:abc',status:'previewed'};
let checks=0;
async function test(name,work){await work();checks++;console.log('PASS '+name);}

await test('only bounded CSV/XLSX reaches staging',async()=>{
  let requests=0;const workflow=new BuyerImportWorkflow({request:async()=>{requests++;}},session());
  for(const file of [new File(['x'],'sheet.xlsm'),new File([],'empty.csv'),new File([new Uint8Array(5*1024*1024+1)],'large.xlsx')]){
    await assert.rejects(()=>workflow.preview(file));
  }
  assert.equal(requests,0);
});
await test('a lost preview response retains the original key and exact file',async()=>{
  const calls=[];let keys=0;const workflow=new BuyerImportWorkflow({request:async request=>{calls.push(request);if(calls.length===1)throw Error('connection lost');return preview;}},session(),()=>`key-${++keys}`);
  const file=new File(['Company,Website\nExample,https://example.test'],'buyers.csv');
  await assert.rejects(()=>workflow.preview(file));
  assert.equal(await workflow.preview(file),preview);
  assert.equal(calls[0].idempotencyKey,calls[1].idempotencyKey);
  assert.equal(await calls[1].formData.get('file').text(),await file.text());
  assert.equal(calls[0].path,'/v1/workspaces/workspace/projects/project/buyer-imports/preview');
});
await test('confirmation retries keep digest and key after ambiguous failure',async()=>{
  const calls=[];let keys=0;const workflow=new BuyerImportWorkflow({request:async request=>{calls.push(request);if(calls.length===1)throw Error('lost response');return {id:'import-1',status:'completed',imported_rows:2};}},session(),()=>`key-${++keys}`);
  await assert.rejects(()=>workflow.confirm(preview));
  await workflow.confirm(preview);
  assert.equal(calls[0].idempotencyKey,calls[1].idempotencyKey);
  assert.deepEqual(calls[1].body,{preview_digest:'sha256:abc',confirmation:true});
  assert.match(calls[1].path,/buyer-imports\/import-1\/confirm$/);
});
await test('lookup is read-only and scoped to the original workspace and project',async()=>{
  let observed;const workflow=new BuyerImportWorkflow({request:async request=>{observed=request;return preview;}},session());
  await workflow.lookup('import-1');
  assert.equal(observed.path,'/v1/workspaces/workspace/projects/project/buyer-imports/import-1');
  assert.equal(observed.method,undefined);assert.equal(observed.body,undefined);assert.equal(observed.idempotencyKey,undefined);
});
await test('scope changes reject late confirmation instead of updating the new project',async()=>{
  const s=session();let release;
  const workflow=new BuyerImportWorkflow({request:()=>new Promise(resolve=>{release=resolve;})},s);
  const pending=workflow.confirm(preview);await new Promise(resolve=>setImmediate(resolve));
  s.next({project:'other-project'});release({id:'import-1',status:'completed'});
  await assert.rejects(pending,LiveCancelled);
});
console.log(`${checks} buyer import checks passed`);
