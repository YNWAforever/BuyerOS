/** Read-only local gap observation, not a containment acceptance test. */
import assert from 'node:assert/strict';
import {createServer,get} from 'node:http';
import {chromium} from '@playwright/test';
import {installProbeFetchGuard} from '../../scripts/neon-runtime-probe.mjs';
let physical=0,httpRoutes=0;
const sink=createServer((_request,response)=>{physical++;response.setHeader('Content-Type','application/json');response.end('{"fixture_only":true}');});
await new Promise(resolve=>sink.listen(0,'127.0.0.1',resolve));
const url='http://127.0.0.1:'+sink.address().port;
let browser,context;
try {
 const guard=installProbeFetchGuard();await assert.rejects(fetch(url),/N00_PROBE_FETCH_DISABLED/);assert.equal(physical,0);
 await new Promise((resolve,reject)=>{const request=get(url,response=>{response.resume();response.on('end',resolve);});request.on('error',reject);request.setTimeout(1000,()=>request.destroy(new Error('owned probe timeout')));});
 assert.equal(physical,1);assert.equal(guard.metrics().forwarded,0);
 browser=await chromium.launch();context=await browser.newContext({serviceWorkers:'block'});
 await context.route('**/*',route=>{httpRoutes++;return route.abort();});
 const response=await context.request.get(url,{timeout:1000,maxRetries:0});assert.equal(response.status(),200);assert.equal(physical,2);assert.equal(httpRoutes,0);
 console.log(JSON.stringify({fixture_only:true,external_verified:false,external_http_requests:0,auth_hops:0,journal_reservations:0,fetch_guard:guard.metrics(),node_native_http_physical_requests:1,browser_APIRequestContext_physical_requests:1,context_http_route_callbacks:httpRoutes,all_native_contained:false,arbitrary_provider_cli_contained:false},null,2));
}finally {await context?.close();await browser?.close();sink.closeAllConnections();await new Promise(resolve=>sink.close(resolve));assert.equal(sink.listening,false);}
