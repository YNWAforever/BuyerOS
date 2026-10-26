import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {moduleUrl} from './ts-loader.mjs';
import ts from 'typescript';
import React from 'react';
import {renderToString} from 'react-dom/server';
import * as jsxRuntime from 'react/jsx-runtime';
// Render the actual callback consumer at the server/hydration boundary.
// Router/context stand-ins avoid a browser and do not simulate successful login.
let source=ts.transpileModule(fs.readFileSync('app/(product)/auth/callback/page.tsx','utf8'),{compilerOptions:{
  module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText;
source=source.replace(/from ["']@\/services\/live\/auth-session["']/g,`from ${JSON.stringify(moduleUrl('services/live/auth-session.ts'))}`).replace(/from ["']react["']/g,`from ${JSON.stringify(import.meta.resolve('react'))}`)
 .replace(/from ["']react\/jsx-runtime["']/g,`from ${JSON.stringify(import.meta.resolve('react/jsx-runtime'))}`)
 .replace(/import \{ useRouter \} from ["']next\/navigation["'];/,`const useRouter=()=>({replace(){}});`)
 .replace(/import \{ useWorkspaceSession \} from ["']@\/features\/providers\/workspace-session["'];/,
   `const useWorkspaceSession=()=>({auth:null,authBootstrap:{kind:'initializing'},session:{}});`);
source=source.replace(/from ["']@\/services\/live\/sign-in-failure["']/g, `from ${JSON.stringify(moduleUrl('services/live/sign-in-failure.ts'))}`);
source=source.replace(/import.*useAuthLocale.*from[^;]+;/,
 `const useAuthLocale=()=>({t:value=>value,picker:null,locale:'en'});`);
const {default:Callback}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
test('U13 actual callback render during initializing is status, never configuration alert',()=>{
  const html=renderToString(React.createElement(Callback));
  assert.match(html,/role="status"/);assert.doesNotMatch(html,/not configured|role="alert"/);
});

test('sign-in retry clears stale custom validity before checking native constraints',async()=>{
  const elements=[];
  // Capture the real page's handlers while retaining React's render and hooks.
  globalThis.__signInTestJsx={...jsxRuntime};
  for(const name of ['jsx','jsxs'])globalThis.__signInTestJsx[name]=(type,props,...rest)=>{
    elements.push({type,props});return jsxRuntime[name](type,props,...rest);
  };
  let page=ts.transpileModule(fs.readFileSync('app/(product)/auth/sign-in/page.tsx','utf8'),{compilerOptions:{
    module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText;
  page=page.replace(/import \{([^}]+)\} from ["']react\/jsx-runtime["'];/,(_,names)=>
    `const {${names.replace(/ as /g,':')}}=globalThis.__signInTestJsx;`)
    .replace(/from ["']react["']/g,`from ${JSON.stringify(import.meta.resolve('react'))}`)
    .replace(/from ["']@\/services\/live\/(neon-auth|sign-in-failure)["']/g,(_,name)=>`from ${JSON.stringify(moduleUrl(`services/live/${name}.ts`))}`)
    .replace(/import.*useWorkspaceSession.*from[^;]+;/,`const useWorkspaceSession=()=>({auth:{provider:'neon'},authBootstrap:{kind:'ready'}});`)
    .replace(/import.*useAuthLocale.*from[^;]+;/,`const useAuthLocale=()=>({t:value=>value,picker:null,locale:'en'});`)
    .replace(/import.*LiveBrand.*from[^;]+;/,`const LiveBrand=()=>null;`);
  const {default:SignIn}=await import('data:text/javascript;base64,'+Buffer.from(page).toString('base64'));
  class Input {
    constructor(type){this.type=type;this.value='';this.validationMessage='';}
    setCustomValidity(message){this.validationMessage=message;}
    get validity(){
      const valueMissing=!this.value,typeMismatch=this.type==='email'&&!!this.value&&!this.value.includes('@');
      return {valueMissing,typeMismatch,valid:!valueMissing&&!typeMismatch&&!this.validationMessage};
    }
  }
  const previousDocument=globalThis.document,previousInput=globalThis.HTMLInputElement;
  try{
    renderToString(React.createElement(SignIn));
    const prepare=elements.find(({type,props})=>type==='button'&&props.type==='submit').props.onMouseDown;
    const email=new Input('email'),password=new Input('password');
    globalThis.HTMLInputElement=Input;
    globalThis.document={getElementById:id=>id==='sign-in-email'?email:password};
    prepare();
    assert.equal(email.validationMessage,'Enter the work email on your invitation.');
    assert.equal(password.validationMessage,'Enter the password for this BuyerOS account.');
    // Autofill can replace values without calling the page's onChange handlers.
    email.value='invited@example.test';password.value='synthetic-password';prepare();
    assert.equal(email.validity.valid,true);
    assert.equal(password.validity.valid,true);
    email.value='incomplete';prepare();
    assert.equal(email.validationMessage,'Enter a complete email address, such as name@company.com.');
    email.value='invited@example.test';prepare();
    assert.equal(email.validity.valid,true);
  }finally{
    globalThis.document=previousDocument;globalThis.HTMLInputElement=previousInput;delete globalThis.__signInTestJsx;
  }
});
