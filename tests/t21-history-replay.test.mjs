import test from 'node:test';
import assert from 'node:assert/strict';
import {loadModule} from './ts-loader.mjs';
const {SessionScope}=await loadModule('services/live/session.ts');
const {bindHistoryTransitions}=await loadModule('services/live/history-transition.ts');
const settle=()=>new Promise(resolve=>setImmediate(resolve));
function environment(){
 const source={key:'source-key',url:'https://app.example.test/app/outreach?workspace=A&project=P',index:2};
 const target={key:'target-key',url:'https://app.example.test/app?workspace=A&project=P',index:1};
 const nav=new EventTarget(),browser=new EventTarget(),calls={go:[],traverse:0};
 nav.currentEntry=source;nav.rows=[{key:'other-key',url:'https://app.example.test/app/runs',index:0},target,source];
 nav.entries=()=>nav.rows;
 nav.traverseTo=()=>{calls.traverse++;return {finished:Promise.reject(new DOMException('synthetic canceled traversal tracker','AbortError'))};};
 browser.navigation=nav;browser.location={origin:'https://app.example.test',href:source.url,pathname:'/app/outreach'};
 function event(){
   const value=new Event('navigate',{cancelable:true});
   Object.defineProperties(value,{navigationType:{value:'traverse'},destination:{value:{sameDocument:true,key:target.key,url:target.url,index:target.index}}});
   return value;
 }
 browser.history={length:3,go:delta=>{
   calls.go.push(delta);const replay=event();nav.dispatchEvent(replay);
   if(replay.defaultPrevented)return;
   nav.currentEntry=target;browser.location.href=target.url;browser.location.pathname='/app';
   browser.dispatchEvent(new Event('popstate'));nav.dispatchEvent(new Event('navigatesuccess'));
 }};
 return {nav,browser,calls,event,source,target};
}
test('T21 approved same-document traversal replays one verified history delta without reusing an aborted API tracker',async()=>{
 const e=environment(),session=new SessionScope({mode:'live'});let allow;
 const decision=new Promise(resolve=>{allow=resolve;});
 session.registerTransitionGuard(async proceed=>{await decision;await proceed();return true;});
 const dispose=bindHistoryTransitions(session,e.browser);
 try{
   const original=e.event();e.nav.dispatchEvent(original);assert.equal(original.defaultPrevented,true);
   assert.deepEqual(e.calls.go,[]);allow();await settle();
   assert.deepEqual(e.calls.go,[-1]);assert.equal(e.calls.traverse,0);assert.equal(e.browser.location.href,e.target.url);
 }finally{dispose();}
});
test('T21 Cancel never replays a canceled history traversal',async()=>{
 const e=environment(),session=new SessionScope({mode:'live'});
 session.registerTransitionGuard(async()=>false);
 const dispose=bindHistoryTransitions(session,e.browser);
 try{e.nav.dispatchEvent(e.event());await settle();assert.deepEqual(e.calls.go,[]);assert.equal(e.calls.traverse,0);assert.equal(e.browser.location.href,e.source.url);}
 finally{dispose();}
});
test('T21 a changed target entry cannot receive a previously approved replay',async()=>{
 const e=environment(),session=new SessionScope({mode:'live'});let allow;
 const decision=new Promise(resolve=>{allow=resolve;});
 session.registerTransitionGuard(async proceed=>{await decision;await proceed();return true;});
 const dispose=bindHistoryTransitions(session,e.browser);
 try{
   e.nav.dispatchEvent(e.event());
   e.nav.rows=e.nav.rows.map(row=>row.key===e.target.key?{...row,url:'https://app.example.test/app?workspace=foreign'}:row);
   allow();await settle();assert.deepEqual(e.calls.go,[]);assert.equal(e.calls.traverse,0);
 }finally{dispose();}
});
test('T21 a confirmed arrival is not replayed a second time',async()=>{
 const e=environment(),session=new SessionScope({mode:'live'});let allow;
 const decision=new Promise(resolve=>{allow=resolve;});
 session.registerTransitionGuard(async proceed=>{await decision;await proceed();return true;});
 const dispose=bindHistoryTransitions(session,e.browser);
 try{
   e.nav.dispatchEvent(e.event());e.nav.currentEntry=e.target;e.browser.location.href=e.target.url;e.browser.location.pathname='/app';
   allow();await settle();assert.deepEqual(e.calls.go,[]);assert.equal(e.calls.traverse,0);
 }finally{dispose();}
});

test('T21 an unexpected replay destination is canceled before it can change scope',async()=>{
 const e=environment(),session=new SessionScope({mode:'live'});let blocked=false;
 session.registerTransitionGuard(async proceed=>{await proceed();return true;});
 e.browser.history.go=delta=>{
   e.calls.go.push(delta);const wrong=new Event('navigate',{cancelable:true});
   Object.defineProperties(wrong,{navigationType:{value:'traverse'},destination:{value:{sameDocument:true,key:'foreign-key',url:'https://app.example.test/app?workspace=foreign'}}});
   e.nav.dispatchEvent(wrong);blocked=wrong.defaultPrevented;
 };
 const dispose=bindHistoryTransitions(session,e.browser);
 try{e.nav.dispatchEvent(e.event());await settle();assert.equal(blocked,true);assert.equal(e.browser.location.href,e.source.url);assert.equal(e.calls.traverse,0);}
 finally{dispose();}
});
for(const proceed of [false,true]){
 test(`T21 known WebKit restores the current history entry before ${proceed?'approved replay':'Cancel'}`,async()=>{
   const e=environment(),session=new SessionScope({mode:'live'});let decide;
   e.browser.navigator={vendor:'Apple Computer, Inc.',userAgent:'fixture AppleWebKit/owned'};
   const entries=e.nav.rows.map(row=>({...row,state:{__vinext_historyIndex:row.index}}));
   class OwnedHistory{
     cursor=2;length=entries.length;
     get state(){return entries[this.cursor].state;}
     replaceState(state,unused,url){entries[this.cursor].state=state;if(url){entries[this.cursor].url=new URL(url,e.browser.location.href).href;e.browser.location.href=entries[this.cursor].url;e.browser.location.pathname=new URL(e.browser.location.href).pathname;}}
     pushState(){throw Error('No push is needed for guarded traversal');}
     go(delta){e.calls.go.push(delta);this.cursor+=delta;assert.ok(this.cursor>=0&&this.cursor<this.length);
       const row=entries[this.cursor];e.browser.location.href=row.url;e.browser.location.pathname=new URL(row.url).pathname;e.nav.currentEntry=row;
       const pop=new Event('popstate');Object.defineProperty(pop,'state',{value:row.state});e.browser.dispatchEvent(pop);
       e.nav.dispatchEvent(new Event('navigatesuccess'));
     }
   }
   e.browser.history=new OwnedHistory();
   const decision=new Promise(resolve=>{decide=resolve;});
   session.registerTransitionGuard(async next=>{const accepted=await decision;if(accepted)await next();return accepted;});
   const navigated=[];
   const dispose=bindHistoryTransitions(session,e.browser,path=>{
     navigated.push(path);e.browser.history.replaceState(e.browser.history.state,'',path);
   });
   try{
     e.browser.history.go(-1);await settle();
     assert.equal(e.browser.location.href,e.source.url,'the dirty editor must keep its original URL while deciding');
     assert.deepEqual(e.calls.go,[-1,1]);
     decide(proceed);await settle();
     assert.equal(e.browser.location.href,proceed?e.target.url:e.source.url);
     assert.deepEqual(e.calls.go,proceed?[-1,1,-1]:[-1,1]);
     assert.equal(navigated.length,proceed?1:0);
   }finally{dispose();}
 });
}
