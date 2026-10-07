import test from 'node:test';
import assert from 'node:assert/strict';
import {registerHooks} from 'node:module';
import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import ts from 'typescript';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
const root=resolve('.'),rootUrl=pathToFileURL(root+'/').href;
const stub='data:text/javascript,export function useWorkspaceSession(){return {client:null,session:{identity:()=> \'fixture\',isCurrent:()=>true}};}';
registerHooks({resolve(specifier,context,next){
 if(specifier==='@/features/providers/workspace-session')return {url:stub,shortCircuit:true};
 if(specifier.startsWith('@/'))specifier=pathToFileURL(resolve(root,specifier.slice(2))).href;
 try{return next(specifier,context);}catch(error){
  if(error.code!=='ERR_MODULE_NOT_FOUND'||!(specifier.startsWith('file:')||specifier.startsWith('.'))||!context.parentURL?.startsWith(rootUrl))throw error;
  for(const ext of ['.ts','.tsx']){try{return next(specifier+ext,context);}catch{}}
  throw error;
 }
},load(url,context,next){
 if(url.startsWith(rootUrl)&&/\.tsx?$/.test(url))return {format:'module',shortCircuit:true,source:ts.transpileModule(readFileSync(new URL(url),'utf8'),{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText};
 return next(url,context);
}});
const {DraftGroundingReview,DraftSourceCard}=await import(pathToFileURL(resolve('features/live/draft-grounding-review.tsx')).href);
const draft={id:'fixture',buyer_id:'fixture',subject:'中😀é文',body:'Greeting',revision_number:3,revision_id:'revision',content_hash:'sha256:fixture',evidence_refs:[],value_proposition_fact_ids:[]};
const view=()=>renderToStaticMarkup(React.createElement(DraftGroundingReview,{draft,canReview:true,busy:false,dirty:false,t:x=>x,onBusy:()=>{},onReviewed:()=>{}}));
test('C61T-10 current source-review segments expose keyboard text selection without editing exact text',()=>{
 const html=view();assert.match(html,/<textarea[^>]*aria-label="Select segment text"[^>]*readonly/i);assert.match(html,/Use selected text/);assert.match(html,/Shift/);assert.match(html,/中😀é文/);
});
test('D03 source card retains source title, URL, dates and actual company; unsafe links stay text',()=>{
 assert.equal(typeof DraftSourceCard,'function');
 const evidence={id:'source-id',version:2,company_id:'company',title:'Original catalog',source_url:'https://example.test/catalog',retrieved_at:'2026-10-06T12:00:00Z',observed_at:'2026-10-05T12:00:00Z',excerpt:'Industrial sensors',status:'available'};
 const props={evidence,company:'Source company',t:x=>x};
 const html=renderToStaticMarkup(React.createElement(DraftSourceCard,props));
 for(const value of ['Original catalog','https://example.test/catalog','2026-10-06T12:00:00Z','2026-10-05T12:00:00Z','Source company'])assert.ok(html.includes(value),value);
 assert.match(html,/<details/);assert.match(html,/source-id/);
 const unsafe=renderToStaticMarkup(React.createElement(DraftSourceCard,{...props,evidence:{...evidence,source_url:'javascript:alert(1)'}}));
 assert.doesNotMatch(unsafe,/<a[^>]+href="javascript:/);
});
