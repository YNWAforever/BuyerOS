import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,readdirSync} from 'node:fs';
import {registerHooks} from 'node:module';
import ts from 'typescript';
registerHooks({resolve(s,c,next){try{return next(s,c);}catch(error){if(s.startsWith('.'))for(const ext of ['.ts','.tsx'])try{return next(s+ext,c);}catch{}throw error;}},load(url,c,next){if(/\.tsx?$/.test(url))return {format:'module',shortCircuit:true,source:ts.transpileModule(readFileSync(new URL(url),'utf8'),{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText};return next(url,c);}});

/** Every user-facing literal in the conversation-first studio must have a zh-HK entry. */
const {liveZh}=await import('../features/live/locale.ts');
const {zh}=await import('../locales/index.ts');
const directory='features/live/conversation';
const files=readdirSync(directory).filter(name=>/\.tsx?$/.test(name)).sort().map(name=>directory+'/'+name);
assert.ok(files.length>=8,'the conversation studio modules are discovered');
const missing=new Map();
for(const file of files){
  const source=readFileSync(file,'utf8');
  for(const [,text] of source.matchAll(/\bt\('([^']+)'\)/g)){
    if(liveZh[text]||zh[text])continue;
    if(!missing.has(text))missing.set(text,[]);
    missing.get(text).push(file);
  }
}
test('conversation studio literals are fully localized in liveZh zh-HK',()=>{
  assert.deepEqual([...missing.entries()].map(([text,files])=>({text,files})),[],
    'add every missing conversation string to features/live/locale.ts liveZh (and locales/index.ts zh)');
  // A live-only surface must not resolve through an English-only fallback key.
  for(const [,text] of readFileSync(directory+'/studio.tsx','utf8').matchAll(/\bt\('([^']+)'\)/g))
    assert.equal(typeof liveZh[text]==='string',true,text);
});
