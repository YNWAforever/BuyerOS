import test from 'node:test';
import assert from 'node:assert/strict';
import ts from 'typescript';
import {readFileSync} from 'node:fs';
const load = async path => import('data:text/javascript;base64,'+Buffer.from(ts.transpileModule(readFileSync(path,'utf8'),{compilerOptions:{module:ts.ModuleKind.ESNext,jsx:ts.JsxEmit.React}}).outputText).toString('base64'));
test('all 17 displayed English and zh-HK titles select the same bounded skill',async()=>{
 const {suggestSkill,skillTitles}=await load('features/live/sales-skills/task-cards.tsx');
 const {liveZh}=await load('features/live/locale.ts');
 const skills=Object.keys(skillTitles).map(id=>({id}));
 assert.equal(skills.length,17);
 for(const skill of skills){
  const title=skillTitles[skill.id];assert.ok(liveZh[title],title);
  assert.equal(suggestSkill(title,skills,s=>s),skill.id);
  assert.equal(suggestSkill(liveZh[title],skills,s=>liveZh[s]??s),skill.id);
 }
 assert.equal(suggestSkill('unknown',skills,s=>liveZh[s]??s),'');
 assert.equal(suggestSkill('準備會議',[],s=>liveZh[s]??s),'');
});
