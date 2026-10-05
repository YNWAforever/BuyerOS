import {test,expect,type BrowserContext} from '@playwright/test';
import {createServer} from 'node:http';
import {createAuthClient} from '@neondatabase/auth';
import {RealRunJournal} from '../../scripts/neon-real-preflight.mjs';
import {createFixtureExecutionBoundary,createFixtureExecutionGateway,runFixtureCli} from '../../scripts/neon-execution-boundary.mjs';
import {executionFixture,listen} from '../fixtures/neon-execution/fixture.mjs';
const nonce='fictional-browser-owner-'.padEnd(43,'x');
// Dedicated loopback fixture only; broader native/provider containment stays open.
async function containBrowser(context:BrowserContext,allowed:Set<string>,onRefused=()=>{}) {
 // No fixture flow needs WebSockets; never connect routed sockets to a server.
 await context.routeWebSocket('**/*',socket=>socket.close({code:1008,reason:'N00 fixture WebSockets refused'}));
 await context.route('**/*',route=>{
  if(allowed.has(new URL(route.request().url()).origin))return route.continue();
  onRefused();return route.abort();
 });
}


test('NA01 accounting: actual browser, pinned SDK and fixed CLI share the same durable HTTP budget',async({page},testInfo)=>{
 const fixture=await executionFixture(undefined);
 try{const execution=createFixtureExecutionBoundary({backend:fixture.backend,journal:fixture.journal}),gateway=createFixtureExecutionGateway({execution,nonce});fixture.servers.push(gateway);const url=await listen(gateway);
  await containBrowser(page.context(),new Set([url]));await page.goto(url);await expect(page.getByRole('heading',{name:'N00 accounting fixture'})).toBeVisible();
  const results=await page.evaluate(async({nonce})=>{const call=async(path:string)=>{const response=await fetch('/dispatch',{method:'POST',headers:{'Content-Type':'application/json','x-n00-owner':nonce},body:JSON.stringify({channel:'browser',method:'GET',path,body:''})});const value:unknown=await response.json();if(!value||typeof value!=='object'||!('status' in value)||typeof value.status!=='number'||!('location' in value)||(typeof value.location!=='string'&&value.location!==null)||!('fixture_only' in value)||typeof value.fixture_only!=='boolean'||!('external_verified' in value)||typeof value.external_verified!=='boolean')throw new Error('Invalid fixture receipt');return {status:value.status,location:value.location,fixture_only:value.fixture_only,external_verified:value.external_verified};};const first=await call('/fixture/auth/redirect');if(typeof first.location!=='string')throw new Error('Missing manual redirect');const second=await call(first.location);document.body.appendChild(Object.assign(document.createElement('output'),{textContent:`Browser hops: 2; fixture only: ${second.fixture_only}`}));return [first.status,second.status,second.external_verified];},{nonce});
  expect(results).toEqual([302,200,false]);const token=await createAuthClient(url+'/sdk/auth').token({fetchOptions:{headers:{'x-n00-owner':nonce}}});expect(token.data?.token).toBe('fictional.a.b');
  const cli=await runFixtureCli({gateway,nonce,request:{channel:'cli',method:'GET',path:'/fixture/auth/token'},parentEnvironment:{...process.env,NEON_API_KEY:'fictional-forbidden-secret'}});expect(cli.environment_clean).toBe(true);
  expect(fixture.model.hits).toHaveLength(4);expect(fixture.journal.snapshot().requests.map((value:{outcome:string})=>value.outcome)).toEqual(['accepted','accepted','accepted','accepted']);
  await page.screenshot({path:testInfo.outputPath('accounting-fixture.png')});await testInfo.attach('receipt',{body:JSON.stringify({fixture_only:true,external_verified:false,http_requests:4,channels:['browser','browser','sdk','cli'],canonical_database_connected:false}),contentType:'application/json'});await testInfo.attach('journal',{body:JSON.stringify(fixture.journal.snapshot()),contentType:'application/json'});
 }finally{const proof=await fixture.cleanup();await testInfo.attach('owned-cleanup',{body:JSON.stringify(proof),contentType:'application/json'});}
});
test('NA01 accounting: browser origin and direct-network refusals dispatch no provider HTTP',async({page},testInfo)=>{
 const fixture=await executionFixture(undefined);
 try{const execution=createFixtureExecutionBoundary({backend:fixture.backend,journal:fixture.journal}),gateway=createFixtureExecutionGateway({execution,nonce});fixture.servers.push(gateway);const url=await listen(gateway);let blocked=0;
  await containBrowser(page.context(),new Set([url]),()=>{blocked++;});await page.goto(url);
  const result=await page.evaluate(async()=>{let direct=false;try{await fetch('https://execution.fixture.invalid/auth/token');}catch{direct=true;}const response=await fetch('/dispatch',{method:'POST',headers:{'x-n00-owner':'wrong'},body:JSON.stringify({channel:'browser',method:'GET',path:'/fixture/auth/token'})});return {direct,status:response.status};});expect(result).toEqual({direct:true,status:403});expect(blocked).toBe(1);expect(fixture.model.hits).toHaveLength(0);expect(fixture.journal.snapshot().requests).toHaveLength(0);
 }finally{const proof=await fixture.cleanup();await testInfo.attach('owned-cleanup',{body:JSON.stringify(proof),contentType:'application/json'});}
});
test('NA01 accounting: browser refresh and a reconstructed journal cannot replay an unknown write',async({page},testInfo)=>{
 const fixture=await executionFixture(undefined);
 try{let execution=createFixtureExecutionBoundary({backend:fixture.backend,journal:fixture.journal});const first=createFixtureExecutionGateway({execution,nonce});fixture.servers.push(first);const firstUrl=await listen(first);const allowed=new Set([firstUrl]);await containBrowser(page.context(),allowed);await page.goto(firstUrl);
  const call=()=>page.evaluate(async({nonce})=>{const response=await fetch('/dispatch',{method:'POST',headers:{'x-n00-owner':nonce},body:JSON.stringify({channel:'browser',method:'POST',path:'/fixture/auth/commit',body:'{"one":"intent"}'})});const result:unknown=await response.json();if(!result||typeof result!=='object')throw new Error('Invalid fixture result');return {status:response.status,result:{outcome:'outcome' in result?result.outcome:null,code:'code' in result?result.code:null}};},{nonce});
  expect((await call()).result.outcome).toBe('unknown');expect(fixture.model.commits).toBe(1);
  execution=createFixtureExecutionBoundary({backend:fixture.backend,journal:new RealRunJournal(fixture.root)});const restarted=createFixtureExecutionGateway({execution,nonce});fixture.servers.push(restarted);const secondUrl=await listen(restarted);allowed.add(secondUrl);await page.goto(secondUrl);await page.reload();const retry=await call();expect(retry.status).toBe(403);expect(retry.result.code).toBe('N00_EXECUTION_HELD_INTENT');expect(fixture.model.commits).toBe(1);expect(fixture.journal.snapshot().requests).toHaveLength(1);
 }finally{const proof=await fixture.cleanup();await testInfo.attach('owned-cleanup',{body:JSON.stringify(proof),contentType:'application/json'});}
});


test('NA01 containment: native WebSockets cannot bypass HTTP routing before or after refresh',async({page,browser},testInfo)=>{
 const fixture=await executionFixture(undefined);
 let positiveContext:BrowserContext|undefined;
 try {
  const execution=createFixtureExecutionBoundary({backend:fixture.backend,journal:fixture.journal}),gateway=createFixtureExecutionGateway({execution,nonce});fixture.servers.push(gateway);const url=await listen(gateway);
  let gatewayUpgrades=0,sinkUpgrades=0;
  gateway.on('upgrade',(_request,socket)=>{gatewayUpgrades++;socket.end('HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n');});
  const sink=createServer((_request,response)=>{response.end('<!doctype html><title>Owned socket sink</title>');});fixture.servers.push(sink);
  sink.on('upgrade',(_request,socket)=>{sinkUpgrades++;socket.end('HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n');});
  const sinkUrl=await listen(sink);
  // Positive control: the actual Chromium socket must physically reach this sink.
  positiveContext=await browser.newContext({serviceWorkers:'block'});const controlPage=await positiveContext.newPage();await controlPage.goto(sinkUrl);
  const attempt=(p:typeof page,targets:string[])=>p.evaluate(async targets=>Promise.all(targets.map(target=>new Promise<string>(resolve=>{
   const socket=new WebSocket(target);socket.onerror=()=>resolve('error');socket.onclose=()=>resolve('closed');
  }))),targets);
  await attempt(controlPage,[sinkUrl.replace('http:','ws:')+'/positive-control']);expect(sinkUpgrades).toBe(1);await positiveContext.close();positiveContext=undefined;
  await containBrowser(page.context(),new Set([url]));await page.goto(url);
  const targets=[url.replace('http:','ws:')+'/direct',sinkUrl.replace('http:','ws:')+'/direct'];
  expect(await attempt(page,targets)).toHaveLength(2);await page.reload();expect(await attempt(page,targets)).toHaveLength(2);
  await testInfo.attach('native-socket-observations',{body:JSON.stringify({fixture_only:true,external_verified:false,positive_control_physical_upgrades:1,guarded_attempts:4,guarded_gateway_upgrades:gatewayUpgrades,guarded_foreign_sink_upgrades:sinkUpgrades-1,auth_hops:fixture.model.hits.length,reservations:fixture.journal.snapshot().requests.length}),contentType:'application/json'});
  expect(sinkUpgrades).toBe(1);expect(gatewayUpgrades).toBe(0);expect(fixture.model.hits).toHaveLength(0);expect(fixture.journal.snapshot().requests).toHaveLength(0);
 }finally{await positiveContext?.close();const proof=await fixture.cleanup();await testInfo.attach('owned-cleanup',{body:JSON.stringify(proof),contentType:'application/json'});}
});

test('NA01 containment: blocked service workers issue no physical script request',async({page},testInfo)=>{
 const fixture=await executionFixture(undefined);
 try {
  const execution=createFixtureExecutionBoundary({backend:fixture.backend,journal:fixture.journal}),gateway=createFixtureExecutionGateway({execution,nonce});fixture.servers.push(gateway);const url=await listen(gateway);let scriptRequests=0;
  gateway.on('request',request=>{if(request.url==='/worker.js')scriptRequests++;});
  await containBrowser(page.context(),new Set([url]));await page.goto(url);
  const result=await page.evaluate(async()=>{try{return await navigator.serviceWorker.register('/worker.js')?'registered':'blocked';}catch{return 'blocked';}});
  expect(result).toBe('blocked');expect(page.context().serviceWorkers()).toHaveLength(0);expect(scriptRequests).toBe(0);expect(fixture.model.hits).toHaveLength(0);expect(fixture.journal.snapshot().requests).toHaveLength(0);
  await testInfo.attach('service-worker-observations',{body:JSON.stringify({fixture_only:true,external_verified:false,registration:result,physical_script_requests:scriptRequests,auth_hops:0,reservations:0}),contentType:'application/json'});
 }finally{const proof=await fixture.cleanup();await testInfo.attach('owned-cleanup',{body:JSON.stringify(proof),contentType:'application/json'});}
});
