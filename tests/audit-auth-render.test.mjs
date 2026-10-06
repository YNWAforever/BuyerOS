import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';
import React from 'react';
import {renderToString} from 'react-dom/server';
// Render the actual callback consumer at the server/hydration boundary.
// Router/context stand-ins avoid a browser and do not simulate successful login.
let source=ts.transpileModule(fs.readFileSync('app/auth/callback/page.tsx','utf8'),{compilerOptions:{
  module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText;
source=source.replace(/from ["']react["']/g,`from ${JSON.stringify(import.meta.resolve('react'))}`)
 .replace(/from ["']react\/jsx-runtime["']/g,`from ${JSON.stringify(import.meta.resolve('react/jsx-runtime'))}`)
 .replace(/import \{ useRouter \} from ["']next\/navigation["'];/,`const useRouter=()=>({replace(){}});`)
 .replace(/import \{ useWorkspaceSession \} from ["']@\/features\/providers\/workspace-session["'];/,
   `const useWorkspaceSession=()=>({auth:null,authBootstrap:{kind:'initializing'},session:{}});`);
const {default:Callback}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
test('U13 actual callback render during initializing is status, never configuration alert',()=>{
  const html=renderToString(React.createElement(Callback));
  assert.match(html,/role="status"/);assert.doesNotMatch(html,/not configured|role="alert"/);
});
