import test from 'node:test';
import assert from 'node:assert/strict';
import {registerHooks} from 'node:module';
import {readFileSync,readdirSync} from 'node:fs';
import ts from 'typescript';
registerHooks({resolve(s,c,next){try{return next(s,c);}catch(e){if(s.startsWith('.'))for(const ext of ['.ts','.tsx'])try{return next(s+ext,c);}catch{}throw e;}},load(u,c,next){if(/\.tsx?$/.test(u))return {format:'module',shortCircuit:true,source:ts.transpileModule(readFileSync(new URL(u),'utf8'),{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText};return next(u,c);}});

const {nextTabIndex,tabSequenceIndex}=await import('../features/live/conversation/a11y.ts');
const {ConversationTranscript}=await import('../features/live/conversation/transcript.tsx');
const {liveZh}=await import('../features/live/locale.ts');
const {createElement}=await import('react');
const {renderToStaticMarkup}=await import('react-dom/server');

test('the tablist keyboard model wraps and jumps with Home/End',()=>{
  assert.equal(nextTabIndex('ArrowRight',0,3),1);
  assert.equal(nextTabIndex('ArrowRight',2,3),0,'ArrowRight wraps to the first tab');
  assert.equal(nextTabIndex('ArrowLeft',0,3),2,'ArrowLeft wraps to the last tab');
  assert.equal(nextTabIndex('ArrowLeft',1,3),0);
  assert.equal(nextTabIndex('Home',2,3),0);
  assert.equal(nextTabIndex('End',0,3),2);
  for(const key of ['Enter',' ','Tab','ArrowUp','a'])assert.equal(nextTabIndex(key,1,3),null,`${key} is not owned by the tablist`);
  assert.equal(nextTabIndex('ArrowRight',1,0),null,'an empty tablist has no target');
  assert.equal(tabSequenceIndex(1,1),0);
  assert.equal(tabSequenceIndex(1,0),-1,'only the selected tab is in the tab sequence');
});

test('the transcript status line is visible but never a second live region',()=>{
  const statusLine='Workspace discussions are unavailable. Your unsaved text is still here.';
  const actions={t:value=>value,decide:()=>{},onToggleSource:()=>{},onRemoveDrive:()=>{},onRetryAttachment:()=>{}};
  const html=renderToStaticMarkup(createElement(ConversationTranscript,{t:value=>value,locale:'en',entries:[],actions,
    busy:false,statusLine,emptyTitle:'Start'}));
  assert.match(html,/class="conversation-status" aria-hidden="true"/,'the visible status copy is presentation-only');
  assert.ok(html.includes(statusLine),'the status text stays visible');
  assert.equal((html.match(/role="status"/g)??[]).length,0,'the idle transcript has no live region');
  const busyHtml=renderToStaticMarkup(createElement(ConversationTranscript,{t:value=>value,locale:'en',entries:[],actions,
    busy:true,statusLine,emptyTitle:'Start'}));
  assert.equal((busyHtml.match(/role="status"/g)??[]).length,1,'only the typing indicator announces while sending');
});

test('every literal studio string exists in the zh-HK catalogue',()=>{
  const root=new URL('../features/live/',import.meta.url);
  const files=readdirSync(new URL('conversation/',root)).filter(name=>/\.tsx?$/.test(name)).map(name=>new URL('conversation/'+name,root));
  files.push(new URL('discussion-sharing.tsx',root));
  const keys=new Map();
  const collect=file=>{
    const source=ts.createSourceFile(file.pathname,readFileSync(file,'utf8'),ts.ScriptTarget.ES2022,true,ts.ScriptKind.TSX);
    const add=value=>{if(typeof value==='string'&&value.trim()&&!keys.has(value))keys.set(value,file.pathname.split(/[\\/]/).at(-1));};
    const visit=node=>{
      if(ts.isCallExpression(node)&&ts.isIdentifier(node.expression)&&node.expression.text==='t'){
        for(const arg of node.arguments){
          if(ts.isStringLiteral(arg)||ts.isNoSubstitutionTemplateLiteral(arg))add(arg.text);
          else if(ts.isConditionalExpression(arg)){
            const walk=expr=>{if(ts.isStringLiteral(expr)||ts.isNoSubstitutionTemplateLiteral(expr))add(expr.text);
              else if(ts.isConditionalExpression(expr)){walk(expr.whenTrue);walk(expr.whenFalse);}};
            walk(arg);
          }
        }
      }
      ts.forEachChild(node,visit);
    };
    visit(source);
  };
  for(const file of files)collect(file);
  assert.ok(keys.size>100,`the scan found the studio literals (${keys.size})`);
  const missing=[...keys].filter(([key])=>!(key in liveZh)).map(([key,file])=>`${file}: ${JSON.stringify(key)}`);
  assert.deepEqual(missing,[],'a visible or announced studio string must have a zh-HK translation');
  for(const key of ['Send','Remove','Approved','Cancel','Close'])assert.ok(key in liveZh,`${key} is translated`);
});
