import test from 'node:test';
import assert from 'node:assert/strict';
import {loadModule} from './ts-loader.mjs';
const {SessionScope}=await loadModule('services/live/session.ts');
test('T21-03 two editors both guard a transition; cancellation never navigates',async()=>{
 const session=new SessionScope({mode:'live'}),calls=[];
 session.registerTransitionGuard(async()=>{calls.push('preparation');return false;});
 session.registerTransitionGuard(async proceed=>{calls.push('draft');await proceed();return true;});
 const changed=await session.transition(async()=>calls.push('navigated'));
 assert.equal(changed,false);assert.deepEqual(calls,['preparation']);
});
test('T21-03 unregistering one editor retains the other guard',async()=>{
 const session=new SessionScope({mode:'live'}),calls=[];
 session.registerTransitionGuard(async()=>{calls.push('preparation');return false;});
 const remove=session.registerTransitionGuard(async proceed=>{await proceed();return true;});
 remove();assert.equal(await session.transition(async()=>calls.push('navigated')),false);
 assert.deepEqual(calls,['preparation']);
});
test('T21-03 all guards must allow before the actual navigation; concurrent clicks do not duplicate',async()=>{
 const session=new SessionScope({mode:'live'}),calls=[];
 let release;const wait=new Promise(resolve=>{release=resolve;});
 session.registerTransitionGuard(async proceed=>{calls.push('first');await wait;await proceed();return true;});
 session.registerTransitionGuard(async proceed=>{calls.push('second');await proceed();return true;});
 const first=session.transition(async()=>calls.push('navigated'));
 assert.equal(await session.transition(async()=>calls.push('duplicate')),false);release();
 assert.equal(await first,true);assert.deepEqual(calls,['first','second','navigated']);
});

test('T21-03 retained clean trees cannot intercept the active dirty history guard',async()=>{
 const session=new SessionScope({mode:'live'});let dirty=false;
 session.registerTransitionGuard(async()=>false,()=>dirty);
 assert.equal(session.hasTransitionGuards(),true);
 assert.equal(typeof session.hasBlockingTransitionGuards,'function');
 assert.equal(session.hasBlockingTransitionGuards(),false);
 assert.equal(await session.transition(async()=>{}),false);
 dirty=true;assert.equal(session.hasBlockingTransitionGuards(),true);
});

test('T21-03 expiry notice carries only a generic flag and clears for a newly authenticated identity',()=>{
 const session=new SessionScope({mode:'live',actor:'synthetic-first',workspace:'A',project:'P'});
 assert.equal(typeof session.preparationEditsWereCleared,'function');
 assert.equal(session.preparationEditsWereCleared(),false);
 session.setToken('synthetic-first-token');
 session.subscribeBeforeClear(()=>session.markPreparationEditsCleared());
 session.setToken(undefined);
 assert.equal(session.preparationEditsWereCleared(),true);
 assert.deepEqual(session.current(),{mode:'live',actor:'',workspace:null,project:null});
 session.setToken(undefined);assert.equal(session.preparationEditsWereCleared(),true);
 session.next({actor:'synthetic-second'});session.setToken('synthetic-second-token');
 assert.equal(session.preparationEditsWereCleared(),false);
});
test('T21-03 a clean logout never invents an unsaved preparation notice',()=>{
 const session=new SessionScope({mode:'live',actor:'synthetic-first'});
 assert.equal(typeof session.preparationEditsWereCleared,'function');
 session.setToken('synthetic-first-token');session.setToken(undefined);
 assert.equal(session.preparationEditsWereCleared(),false);
});
