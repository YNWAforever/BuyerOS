# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: audit-neon-execution.spec.ts >> NA01 counted APIRequestContext: private cookies and two manual hops through the original journal
- Location: tests\e2e\audit-neon-execution.spec.ts:84:1

# Error details

```
Error: expect(received).toBe(expected) // Object.is equality

Expected: "function"
Received: "undefined"
```

# Test source

```ts
  1  | import {test,expect,type BrowserContext} from '@playwright/test';
  2  | import {createServer} from 'node:http';
  3  | import {createAuthClient} from '@neondatabase/auth';
  4  | import {RealRunJournal} from '../../scripts/neon-real-preflight.mjs';
  5  | import {createFixtureExecutionBoundary,createFixtureExecutionGateway,runFixtureCli} from '../../scripts/neon-execution-boundary.mjs';
  6  | import {executionFixture,listen} from '../fixtures/neon-execution/fixture.mjs';
  7  | const nonce='fictional-browser-owner-'.padEnd(43,'x');
  8  | // Dedicated loopback fixture only; broader native/provider containment stays open.
  9  | async function containBrowser(context:BrowserContext,allowed:Set<string>,onRefused=()=>{}) {
  10 |  // No fixture flow needs WebSockets; never connect routed sockets to a server.
  11 |  await context.routeWebSocket('**/*',socket=>socket.close({code:1008,reason:'N00 fixture WebSockets refused'}));
  12 |  await context.route('**/*',route=>{
  13 |   if(allowed.has(new URL(route.request().url()).origin))return route.continue();
  14 |   onRefused();return route.abort();
  15 |  });
  16 | }
  17 | 
  18 | 
  19 | test('NA01 accounting: actual browser, pinned SDK and fixed CLI share the same durable HTTP budget',async({page},testInfo)=>{
  20 |  const fixture=await executionFixture(undefined);
  21 |  try{const execution=createFixtureExecutionBoundary({backend:fixture.backend,journal:fixture.journal}),gateway=createFixtureExecutionGateway({execution,nonce});fixture.servers.push(gateway);const url=await listen(gateway);
  22 |   await containBrowser(page.context(),new Set([url]));await page.goto(url);await expect(page.getByRole('heading',{name:'N00 accounting fixture'})).toBeVisible();
  23 |   const results=await page.evaluate(async({nonce})=>{const call=async(path:string)=>{const response=await fetch('/dispatch',{method:'POST',headers:{'Content-Type':'application/json','x-n00-owner':nonce},body:JSON.stringify({channel:'browser',method:'GET',path,body:''})});const value:unknown=await response.json();if(!value||typeof value!=='object'||!('status' in value)||typeof value.status!=='number'||!('location' in value)||(typeof value.location!=='string'&&value.location!==null)||!('fixture_only' in value)||typeof value.fixture_only!=='boolean'||!('external_verified' in value)||typeof value.external_verified!=='boolean')throw new Error('Invalid fixture receipt');return {status:value.status,location:value.location,fixture_only:value.fixture_only,external_verified:value.external_verified};};const first=await call('/fixture/auth/redirect');if(typeof first.location!=='string')throw new Error('Missing manual redirect');const second=await call(first.location);document.body.appendChild(Object.assign(document.createElement('output'),{textContent:`Browser hops: 2; fixture only: ${second.fixture_only}`}));return [first.status,second.status,second.external_verified];},{nonce});
  24 |   expect(results).toEqual([302,200,false]);const token=await createAuthClient(url+'/sdk/auth').token({fetchOptions:{headers:{'x-n00-owner':nonce}}});expect(token.data?.token).toBe('fictional.a.b');
  25 |   const cli=await runFixtureCli({gateway,nonce,request:{channel:'cli',method:'GET',path:'/fixture/auth/token'},parentEnvironment:{...process.env,NEON_API_KEY:'fictional-forbidden-secret'}});expect(cli.environment_clean).toBe(true);
  26 |   expect(fixture.model.hits).toHaveLength(4);expect(fixture.journal.snapshot().requests.map((value:{outcome:string})=>value.outcome)).toEqual(['accepted','accepted','accepted','accepted']);
  27 |   await page.screenshot({path:testInfo.outputPath('accounting-fixture.png')});await testInfo.attach('receipt',{body:JSON.stringify({fixture_only:true,external_verified:false,http_requests:4,channels:['browser','browser','sdk','cli'],canonical_database_connected:false}),contentType:'application/json'});await testInfo.attach('journal',{body:JSON.stringify(fixture.journal.snapshot()),contentType:'application/json'});
  28 |  }finally{const proof=await fixture.cleanup();await testInfo.attach('owned-cleanup',{body:JSON.stringify(proof),contentType:'application/json'});}
  29 | });
  30 | test('NA01 accounting: browser origin and direct-network refusals dispatch no provider HTTP',async({page},testInfo)=>{
  31 |  const fixture=await executionFixture(undefined);
  32 |  try{const execution=createFixtureExecutionBoundary({backend:fixture.backend,journal:fixture.journal}),gateway=createFixtureExecutionGateway({execution,nonce});fixture.servers.push(gateway);const url=await listen(gateway);let blocked=0;
  33 |   await containBrowser(page.context(),new Set([url]),()=>{blocked++;});await page.goto(url);
  34 |   const result=await page.evaluate(async()=>{let direct=false;try{await fetch('https://execution.fixture.invalid/auth/token');}catch{direct=true;}const response=await fetch('/dispatch',{method:'POST',headers:{'x-n00-owner':'wrong'},body:JSON.stringify({channel:'browser',method:'GET',path:'/fixture/auth/token'})});return {direct,status:response.status};});expect(result).toEqual({direct:true,status:403});expect(blocked).toBe(1);expect(fixture.model.hits).toHaveLength(0);expect(fixture.journal.snapshot().requests).toHaveLength(0);
  35 |  }finally{const proof=await fixture.cleanup();await testInfo.attach('owned-cleanup',{body:JSON.stringify(proof),contentType:'application/json'});}
  36 | });
  37 | test('NA01 accounting: browser refresh and a reconstructed journal cannot replay an unknown write',async({page},testInfo)=>{
  38 |  const fixture=await executionFixture(undefined);
  39 |  try{let execution=createFixtureExecutionBoundary({backend:fixture.backend,journal:fixture.journal});const first=createFixtureExecutionGateway({execution,nonce});fixture.servers.push(first);const firstUrl=await listen(first);const allowed=new Set([firstUrl]);await containBrowser(page.context(),allowed);await page.goto(firstUrl);
  40 |   const call=()=>page.evaluate(async({nonce})=>{const response=await fetch('/dispatch',{method:'POST',headers:{'x-n00-owner':nonce},body:JSON.stringify({channel:'browser',method:'POST',path:'/fixture/auth/commit',body:'{"one":"intent"}'})});const result:unknown=await response.json();if(!result||typeof result!=='object')throw new Error('Invalid fixture result');return {status:response.status,result:{outcome:'outcome' in result?result.outcome:null,code:'code' in result?result.code:null}};},{nonce});
  41 |   expect((await call()).result.outcome).toBe('unknown');expect(fixture.model.commits).toBe(1);
  42 |   execution=createFixtureExecutionBoundary({backend:fixture.backend,journal:new RealRunJournal(fixture.root)});const restarted=createFixtureExecutionGateway({execution,nonce});fixture.servers.push(restarted);const secondUrl=await listen(restarted);allowed.add(secondUrl);await page.goto(secondUrl);await page.reload();const retry=await call();expect(retry.status).toBe(403);expect(retry.result.code).toBe('N00_EXECUTION_HELD_INTENT');expect(fixture.model.commits).toBe(1);expect(fixture.journal.snapshot().requests).toHaveLength(1);
  43 |  }finally{const proof=await fixture.cleanup();await testInfo.attach('owned-cleanup',{body:JSON.stringify(proof),contentType:'application/json'});}
  44 | });
  45 | 
  46 | 
  47 | test('NA01 containment: native WebSockets cannot bypass HTTP routing before or after refresh',async({page,browser},testInfo)=>{
  48 |  const fixture=await executionFixture(undefined);
  49 |  let positiveContext:BrowserContext|undefined;
  50 |  try {
  51 |   const execution=createFixtureExecutionBoundary({backend:fixture.backend,journal:fixture.journal}),gateway=createFixtureExecutionGateway({execution,nonce});fixture.servers.push(gateway);const url=await listen(gateway);
  52 |   let gatewayUpgrades=0,sinkUpgrades=0;
  53 |   gateway.on('upgrade',(_request,socket)=>{gatewayUpgrades++;socket.end('HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n');});
  54 |   const sink=createServer((_request,response)=>{response.end('<!doctype html><title>Owned socket sink</title>');});fixture.servers.push(sink);
  55 |   sink.on('upgrade',(_request,socket)=>{sinkUpgrades++;socket.end('HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n');});
  56 |   const sinkUrl=await listen(sink);
  57 |   // Positive control: the actual Chromium socket must physically reach this sink.
  58 |   positiveContext=await browser.newContext({serviceWorkers:'block'});const controlPage=await positiveContext.newPage();await controlPage.goto(sinkUrl);
  59 |   const attempt=(p:typeof page,targets:string[])=>p.evaluate(async targets=>Promise.all(targets.map(target=>new Promise<string>(resolve=>{
  60 |    const socket=new WebSocket(target);socket.onerror=()=>resolve('error');socket.onclose=()=>resolve('closed');
  61 |   }))),targets);
  62 |   await attempt(controlPage,[sinkUrl.replace('http:','ws:')+'/positive-control']);expect(sinkUpgrades).toBe(1);await positiveContext.close();positiveContext=undefined;
  63 |   await containBrowser(page.context(),new Set([url]));await page.goto(url);
  64 |   const targets=[url.replace('http:','ws:')+'/direct',sinkUrl.replace('http:','ws:')+'/direct'];
  65 |   expect(await attempt(page,targets)).toHaveLength(2);await page.reload();expect(await attempt(page,targets)).toHaveLength(2);
  66 |   await testInfo.attach('native-socket-observations',{body:JSON.stringify({fixture_only:true,external_verified:false,positive_control_physical_upgrades:1,guarded_attempts:4,guarded_gateway_upgrades:gatewayUpgrades,guarded_foreign_sink_upgrades:sinkUpgrades-1,auth_hops:fixture.model.hits.length,reservations:fixture.journal.snapshot().requests.length}),contentType:'application/json'});
  67 |   expect(sinkUpgrades).toBe(1);expect(gatewayUpgrades).toBe(0);expect(fixture.model.hits).toHaveLength(0);expect(fixture.journal.snapshot().requests).toHaveLength(0);
  68 |  }finally{await positiveContext?.close();const proof=await fixture.cleanup();await testInfo.attach('owned-cleanup',{body:JSON.stringify(proof),contentType:'application/json'});}
  69 | });
  70 | 
  71 | test('NA01 containment: blocked service workers issue no physical script request',async({page},testInfo)=>{
  72 |  const fixture=await executionFixture(undefined);
  73 |  try {
  74 |   const execution=createFixtureExecutionBoundary({backend:fixture.backend,journal:fixture.journal}),gateway=createFixtureExecutionGateway({execution,nonce});fixture.servers.push(gateway);const url=await listen(gateway);let scriptRequests=0;
  75 |   gateway.on('request',request=>{if(request.url==='/worker.js')scriptRequests++;});
  76 |   await containBrowser(page.context(),new Set([url]));await page.goto(url);
  77 |   const result=await page.evaluate(async()=>{try{return await navigator.serviceWorker.register('/worker.js')?'registered':'blocked';}catch{return 'blocked';}});
  78 |   expect(result).toBe('blocked');expect(page.context().serviceWorkers()).toHaveLength(0);expect(scriptRequests).toBe(0);expect(fixture.model.hits).toHaveLength(0);expect(fixture.journal.snapshot().requests).toHaveLength(0);
  79 |   await testInfo.attach('service-worker-observations',{body:JSON.stringify({fixture_only:true,external_verified:false,registration:result,physical_script_requests:scriptRequests,auth_hops:0,reservations:0}),contentType:'application/json'});
  80 |  }finally{const proof=await fixture.cleanup();await testInfo.attach('owned-cleanup',{body:JSON.stringify(proof),contentType:'application/json'});}
  81 | });
  82 | 
  83 | 
  84 | test('NA01 counted APIRequestContext: private cookies and two manual hops through the original journal',async({page},testInfo)=>{
> 85 |  const adapter=await import('../../scripts/neon-api-request-context.mjs').catch(error=>{if(error.code!=='ERR_MODULE_NOT_FOUND')throw error;return null;});expect(typeof adapter?.createFixtureApiRequestContext).toBe('function');if(!adapter)throw new Error('Missing counted API request context');
     |                                                                                                                                                                                                                  ^ Error: expect(received).toBe(expected) // Object.is equality
  86 |  const fixture=await executionFixture(undefined);let client:Awaited<ReturnType<typeof adapter.createFixtureApiRequestContext>>|undefined;
  87 |  try {
  88 |   const execution=createFixtureExecutionBoundary({backend:fixture.backend,journal:fixture.journal}),gateway=createFixtureExecutionGateway({execution,nonce});fixture.servers.push(gateway);const url=await listen(gateway);const cookies:(string|null)[]=[];gateway.on('request',req=>{if(req.url==='/dispatch')cookies.push(req.headers.cookie??null);});
  89 |   await page.context().addCookies([{name:'fictional-browser-session',value:'fictional-private-browser-cookie',url}]);await containBrowser(page.context(),new Set([url]));await page.goto(url);
  90 |   client=await adapter.createFixtureApiRequestContext({gateway,execution,journal:fixture.journal,nonce});const first=await client.dispatch({method:'GET',path:'/fixture/auth/redirect'});expect(first.status).toBe(302);expect(fixture.model.hits).toHaveLength(1);expect(first.location).toBe('/fixture/auth/token');if(!first.location)throw new Error('Missing manual hop');const second=await client.dispatch({method:'GET',path:first.location});expect(second.status).toBe(200);expect(fixture.model.hits).toHaveLength(2);expect(fixture.journal.snapshot().requests.map(v=>v.outcome)).toEqual(['accepted','accepted']);expect(cookies).toEqual([null,null]);
  91 |   await page.evaluate(()=>document.body.appendChild(Object.assign(document.createElement('output'),{textContent:'Counted API context hops: 2; private cookie isolation: true; fixture only: true'})));await expect(page.locator('output')).toContainText('Counted API context hops: 2');await page.screenshot({path:testInfo.outputPath('api-context-fixture.png')});await testInfo.attach('api-context-receipt',{body:JSON.stringify({fixture_only:true,external_verified:false,http_requests:2,reservations:2,private_cookie_isolation:true,raw_context_os_contained:false}),contentType:'application/json'});
  92 |  }finally {if(client)await testInfo.attach('owned-api-context-cleanup',{body:JSON.stringify(await client.dispose()),contentType:'application/json'});const proof=await fixture.cleanup();await testInfo.attach('owned-cleanup',{body:JSON.stringify(proof),contentType:'application/json'});}
  93 | });
  94 | 
```