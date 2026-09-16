// tests/ts-loader.mjs
import fs from 'node:fs';
import path from 'node:path';
import ts from 'typescript';

const cache=new Map();

/** Transpile a .ts file (and its `@/` and relative imports) into a data: URL. Synchronous. */
export function moduleUrl(file){
  const abs=path.resolve(file);
  if(cache.has(abs))return cache.get(abs);
  let js=ts.transpileModule(fs.readFileSync(abs,'utf8'),{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText;
  js=js.replace(/from\s*(['"])([^'"]+)\1/g,(all,q,spec)=>{
    let f=spec.startsWith('@/')?path.resolve(spec.slice(2)):path.resolve(path.dirname(abs),spec);
    if(!path.extname(f))f+='.ts';
    return 'from '+JSON.stringify(moduleUrl(f));
  });
  const u='data:text/javascript;base64,'+Buffer.from(js).toString('base64');
  cache.set(abs,u);
  return u;
}

/** Import a .ts module by path. */
export async function loadModule(file){ return import(moduleUrl(file)); }
