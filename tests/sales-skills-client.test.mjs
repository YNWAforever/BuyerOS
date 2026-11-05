import test from 'node:test';
import assert from 'node:assert/strict';
import {registerHooks} from 'node:module';
import {readFileSync,existsSync} from 'node:fs';
import ts from 'typescript';
registerHooks({resolve(s,c,next){try{return next(s,c);}catch(e){if(s.startsWith('.'))for(const ext of ['.ts','.tsx'])try{return next(s+ext,c);}catch{}throw e;}},load(u,c,next){if(/\.tsx?$/.test(u))return {format:'module',shortCircuit:true,source:ts.transpileModule(readFileSync(new URL(u),'utf8'),{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText};return next(u,c);}});
test('typed sales clients exist',()=>assert.ok(existsSync('services/live/sales-tasks.ts')));
test('exact uncertain mutation retries its key; scope switch cancels and clears drafts',async()=>{
 const {SalesTasks}=await import('../services/live/sales-tasks.ts');
 const {SessionScope}=await import('../services/live/session.ts');
 const session=new SessionScope({mode:'live',actor:'a',workspace:'w',project:'p'});session.setToken('test');
 const requests=[];let fail=true;
 const api=new SalesTasks({request:async input=>{requests.push(input);if(fail){fail=false;throw Error('lost response');}return {id:'t',revision:1};}},session);
 const input={thread_id:'thread',skill_id:'first-project',skill_version:'1',user_message:'Set up',source_refs:[],arguments:{}};
 await assert.rejects(api.start(input,3));await api.start(input,3);
 assert.equal(requests[0].idempotencyKey,requests[1].idempotencyKey);assert.equal(requests[0].ifMatch,'"3"');
 api.drafts.set('thread',{text:'private'});session.next({project:'other'});
 assert.equal(api.drafts.size,0);assert.equal(requests[0].signal.aborted,true);await assert.rejects(api.get('t'));
});
test('reads and cancellation remain reachable without entry flag; exact revisions and cursor',async()=>{
 const {SalesTasks}=await import('../services/live/sales-tasks.ts');const {SalesOutputs}=await import('../services/live/sales-outputs.ts');const {SessionScope}=await import('../services/live/session.ts');
 const s=new SessionScope({mode:'live',actor:'a',workspace:'w',project:'p'});s.setToken('test');const seen=[];const c={request:async x=>{seen.push(x);return {};}};
 await new SalesTasks(c,s).events('t',12);await new SalesOutputs(c,s).get('o',2);
 assert.match(seen[0].path,/after=12/);assert.match(seen[1].path,/versions\/2$/);assert.ok(seen.every(x=>!x.idempotencyKey));
});


test('fix1 current workspace capability and native source reads are scoped and cancellable',async()=>{
 const {SalesTasks}=await import('../services/live/sales-tasks.ts');const {SessionScope}=await import('../services/live/session.ts');
 const session=new SessionScope({mode:'live',actor:'a',workspace:'w',project:'p'});session.setToken('test');const requests=[];
 const api=new SalesTasks({request:async q=>{requests.push(q);return q.path.endsWith('capability')?{admission_enabled:false}:{items:[]};}},session);
 assert.equal((await api.capability()).admission_enabled,false);assert.deepEqual(await api.nativeSources(),{items:[]});
 assert.ok(requests.every(q=>q.method==='GET'&&q.scope===session.identity()&&!q.idempotencyKey));
 session.next({project:'other'});await assert.rejects(api.nativeSources());assert.ok(requests.every(q=>q.signal.aborted));
});
