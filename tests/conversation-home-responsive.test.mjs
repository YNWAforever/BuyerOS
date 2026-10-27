import test from 'node:test';
import assert from 'node:assert/strict';
import {registerHooks} from 'node:module';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {readFileSync,readdirSync} from 'node:fs';
import ts from 'typescript';
import {renderToStaticMarkup} from 'react-dom/server';
const root=resolve('.'),rootUrl=pathToFileURL(root+'/').href;
registerHooks({resolve(specifier,context,next){
 if(specifier.startsWith('@/'))specifier=pathToFileURL(resolve(root,specifier.slice(2))).href;
 try{return next(specifier,context);}catch(error){
  if(error.code!=='ERR_MODULE_NOT_FOUND'||!context.parentURL?.startsWith(rootUrl))throw error;
  for(const ext of ['.ts','.tsx']){try{return next(specifier+ext,context);}catch{}}
  throw error;
 }
},load(url,context,next){
 if(url.startsWith(rootUrl)&&/\.tsx?$/.test(url))return {format:'module',shortCircuit:true,source:ts.transpileModule(readFileSync(new URL(url),'utf8'),{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText};
 return next(url,context);
}});
const {chromium}=await import('@playwright/test');
const {LiveNavigation}=await import('../features/live/navigation.tsx');
const {LiveFrame}=await import('../features/live/shell.tsx');
const cssDir='.vercel/output/static/_next/static/css';
const css=readFileSync(cssDir+'/'+readdirSync(cssDir).find(name=>/^layout\..*\.css$/.test(name)),'utf8');
for(const conversationHome of [false,true])test(`conversation navigation fits desktop, tablet and mobile (flag ${conversationHome?'ON':'OFF'})`,async()=>{
 const browser=await chromium.launch({...(process.env.BUYEROS_CORE_CHROMIUM?{executablePath:process.env.BUYEROS_CORE_CHROMIUM}:{}),headless:true});
 try{
  const navigation=LiveNavigation({t:x=>x,navigate:()=>{},pathname:'/app',authorized:true,projectKnown:true,canEdit:true,projectActive:true,canCreate:true,conversationHome});
  const frame=LiveFrame({t:x=>x,pathname:'/app',navigation,footer:null,header:null,children:null,conversationHome});
  const page=await browser.newPage();await page.setContent('<style>'+css+'</style>'+renderToStaticMarkup(frame));
  for(const width of [320,390,480,481,600,768,820,1023,1024,1440]){
   await page.setViewportSize({width,height:1000});
   const pageWidth=await page.evaluate(()=>document.documentElement.scrollWidth);
   assert.ok(pageWidth<=width,`viewport ${width}px overflows to ${pageWidth}px`);
   assert.equal(await page.getByRole('button',{name:'Operations',exact:true}).count(),1);
  }
 }finally{await browser.close();}
});
