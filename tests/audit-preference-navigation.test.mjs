import test from 'node:test';
import assert from 'node:assert/strict';
import {EventEmitter} from 'node:events';
import {createDocumentReads,observeWorkspaceLocale} from './e2e/fixtures/journey-input.ts';

test('same-document route commit retains the actual current preference request and body',async()=>{
 const page=new EventEmitter(),frame={};page.mainFrame=()=>frame;
 const request=(url,navigation=false)=>({method:()=> 'GET',url:()=>url,isNavigationRequest:()=>navigation,frame:()=>frame,failure:()=>null});
 const stop=observeWorkspaceLocale(page,'w');let bodies=0;
 try{
  page.emit('request',request('http://localhost:5173/auth/callback',true));
  page.emit('framenavigated',frame); // New document committed.
  const current=request('http://localhost:5173/v1/workspaces/w/preferences');
  page.emit('request',current);
  page.emit('framenavigated',frame); // history replacement keeps this document.
  page.emit('response',{status:()=>200,request:()=>current,finished:async()=>null,json:async()=>{bodies++;return {data:{locale:'zh-HK'}};}});
  await new Promise(setImmediate);
  assert.equal(bodies,1,'the real current body must not be discarded by a same-document route event');
 }finally{stop.dispose();}
});

test('pending preference body releases when a later current response arrives',async()=>{
 const reads=createDocumentReads(),old={},current={};let finishOld;
 reads.start(old);reads.record(old,()=>new Promise(resolve=>{finishOld=resolve;}));
 const pending=reads.latest();
 reads.start(current);reads.record(current,async()=>({data:{locale:'zh-HK'}}));
 try{
  assert.equal(await Promise.race([pending.then(()=> 'released'),new Promise(setImmediate).then(()=> 'awaiting old response')]),'released');
  assert.deepEqual(await reads.latest(),{data:{locale:'zh-HK'}});
 }finally{finishOld({data:{locale:'en'}});}
});

test('pending preference body releases on replaced document without using the old body',async()=>{
 const reads=createDocumentReads(),old={},current={};let finishOld;
 reads.start(old);reads.record(old,()=>new Promise(resolve=>{finishOld=resolve;}));
 const pending=reads.latest();reads.advance();
 try{
  assert.equal(await Promise.race([pending.then(()=> 'released'),new Promise(setImmediate).then(()=> 'awaiting old response')]),'released');
  assert.equal(await reads.latest(),undefined);
  reads.start(current);reads.record(current,async()=>({data:{locale:'zh-HK'}}));
  assert.deepEqual(await reads.latest(),{data:{locale:'zh-HK'}});
 }finally{finishOld({data:{locale:'en'}});}
});
