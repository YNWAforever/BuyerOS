// Invoke the real component callback; the HTTP request is handled by the owned API test.
import ts from 'typescript';
import {readFileSync} from 'node:fs';
const output=JSON.parse(readFileSync(0,'utf8'));
const emitted=[];let index=0;
const values=[output.native_refs.find(r=>r.surface==='buyer').id,'Reviewed same-buyer note',true,false,''];
const jsx=(type,props)=>({type,props});
const exports={};
const require=name=>name==='react'?{useState:()=>[values[index++],()=>{}]}:name==='react/jsx-runtime'?{jsx,jsxs:jsx}:{salesError:e=>{throw e;}};
const code=ts.transpileModule(readFileSync('features/live/sales-skills/native-action.tsx','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX}}).outputText;
new Function('require','exports',code)(require,exports);
const tree=exports.NativeAction({output,t:v=>v,onSaved:()=>{},api:{actionId:()=> '11111111-1111-4111-8111-111111111111',apply:async(payload,version)=>emitted.push({payload,version})}});
function find(node){if(!node||typeof node!=='object')return;if(node?.type==='button')return node;for(const child of [node?.props?.children].flat(Infinity)){const found=find(child);if(found)return found;}}
find(tree).props.onClick();
await new Promise(resolve=>setTimeout(resolve,0));
console.log(JSON.stringify(emitted[0]));
