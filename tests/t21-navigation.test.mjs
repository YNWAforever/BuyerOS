import test from 'node:test';
import assert from 'node:assert/strict';
import {loadModule} from './ts-loader.mjs';
const navigation=await loadModule('services/live/navigation-state.ts');
async function inBrowser(run){
 const previous=globalThis.window;
 globalThis.window={location:{origin:'https://app.example.test',pathname:'/app/outreach'}};
 try{await run();}finally{navigation.clearNavigationPresentation();if(previous===undefined)delete globalThis.window;else globalThis.window=previous;}
}
test('T21 navigation keeps the old editor unmounted until an actual new route commits',async()=>inBrowser(async()=>{
 navigation.startNavigation('/app/runs');
 assert.equal(typeof navigation.completeNavigationAt,'function');
 assert.equal(navigation.completeNavigationAt('/app/outreach','/app/outreach'),false);
 assert.ok(navigation.navigationSnapshot());
 assert.equal(navigation.completeNavigationAt('/app/runs','/app/outreach'),false);
 assert.ok(navigation.navigationSnapshot());
 assert.equal(navigation.completeNavigationAt('/app/runs','/app/runs'),true);
 assert.equal(navigation.navigationSnapshot(),null);
}));
test('T21 a committed research detail route completes a superseded pending list navigation',async()=>inBrowser(async()=>{
 navigation.startNavigation('/app/runs');
 assert.equal(typeof navigation.completeNavigationAt,'function');
 assert.equal(navigation.completeNavigationAt('/app/discover/synthetic-run','/app/discover/synthetic-run'),true);
 assert.equal(navigation.navigationSnapshot(),null);
}));
test('T21 a retained old route cannot complete a different current route',async()=>inBrowser(async()=>{
 navigation.startNavigation('/app/runs');
 assert.equal(typeof navigation.completeNavigationAt,'function');
 assert.equal(navigation.completeNavigationAt('/app/outreach','/app/discover/synthetic-run'),false);
 assert.ok(navigation.navigationSnapshot());
}));
