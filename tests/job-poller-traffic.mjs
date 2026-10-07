// Q06 logical60s/10-view workload; HTTP/DB costs are measured by pytest replay.
import assert from 'node:assert/strict';
import {readFileSync,writeFileSync} from 'node:fs';
import {execFileSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import ts from 'typescript';
import {loadModule} from './ts-loader.mjs';
import {fixtureClock,flush} from './fixtures/job-clock.mjs';
const {startJobPoller}=await loadModule('services/live/job-poller.ts');
const [samplePath,outputPath]=process.argv.slice(2);assert.ok(samplePath&&outputPath);
const samples=JSON.parse(readFileSync(samplePath,'utf8'));
const base='b083ea43988ed73e9d8e9ab112ba3d6305f2c941';
const original=execFileSync('git',['show',`${base}:features/live/bulk-actions.tsx`],{encoding:'utf8'});
const a=original.indexOf('const first=await op.requestOperation',original.indexOf('export function BulkJobPanel'));
const b=original.indexOf('        if(active)',a);assert.ok(a>0&&b>a);
const body=original.slice(a,b);
const js=ts.transpileModule(`async function baseline(op,ctx,scope,jobId){${body}\nreturn first;}`,{compilerOptions:{target:ts.ScriptTarget.ES2022}}).outputText;
const baseline=new Function(js+'\nreturn baseline;')();
const runs=[];
for(const mode of ['before','after']){
 const f=fixtureClock(),origin=f.clock.now(),requests=[];let inFlight=0,maxInFlight=0,active=true;
 const controllers=[],intervals=[];const perView=Array.from({length:10},()=>({inFlight:0,maxInFlight:0}));
 function request(view,kind,query,signal){
  if(!active)return Promise.reject(new DOMException('experiment ended','AbortError'));
  const row={view,at_ms:f.clock.now()-origin,kind,offset:query?.offset??0,limit:query?.limit??0};requests.push(row);inFlight++;maxInFlight=Math.max(maxInFlight,inFlight);perView[view].maxInFlight=Math.max(perView[view].maxInFlight,++perView[view].inFlight);
  const value=kind==='summary'?samples.summary.data:samples.pages[String(row.offset)].data;
  return f.latency(2500,value,signal).finally(()=>{inFlight--;perView[view].inFlight--;});
 }
 for(let view=0;view<10;view++){
  if(mode==='before'){
   const op={requestOperation:(_id,input)=>request(view,'detail',input.query)};
   const run=()=>baseline(op,{}, {workspace:'fixture'},'fixture-job').catch(()=>{});
   const interval=()=>{intervals[view]=f.clock.setTimeout(()=>{if(active){void run();interval();}},2000);};
   void run().then(()=>{if(active)interval();});
  }else{
   const controller=new AbortController();controllers.push(controller);
   startJobPoller({signal:controller.signal,clock:f.clock,isVisible:()=>active,fetchSummary:signal=>request(view,'summary',null,signal),onValue:()=>{},onError:assert.fail});
  }
 }
 await f.advance(60_000);active=false;for(const id of intervals)f.clock.clearTimeout(id);for(const c of controllers)c.abort();await f.advance(30_000);await flush();
 if(mode==='after'){assert.equal(maxInFlight,10);assert.ok(perView.every(v=>v.maxInFlight===1));assert.ok(requests.every(r=>r.kind==='summary'));}
 runs.push({mode,logical_window_ms:60_000,rtt_ms:2500,views:10,results:1000,max_in_flight:maxInFlight,per_view:perView,requests});
}
writeFileSync(outputPath,JSON.stringify({fixture_only:true,clock:'deterministic logical time; not wall-clock/live performance',baseline_sha:base,baseline_source_sha256:createHash('sha256').update(original).digest('hex'),baseline_reader_fragment_sha256:createHash('sha256').update(body).digest('hex'),runs},null,2)+'\n');
console.log(JSON.stringify(runs.map(r=>({mode:r.mode,requests:r.requests.length,max_in_flight:r.max_in_flight,max_per_view:Math.max(...r.per_view.map(v=>v.maxInFlight))}))));
