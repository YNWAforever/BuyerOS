import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ts from 'typescript';
const js=ts.transpileModule(readFileSync('services/live/draft-grounding.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText;
const {prepareGroundingSegments,splitGroundingSegment}=await import('data:text/javascript;base64,'+Buffer.from(js).toString('base64'));
test('D03 Unicode code-point offsets retain emoji, CRLF, Chinese and unmodified text',()=>{
 const subject='邀請😀',body='您好👩‍💻\r\n\n產品事實\n謝謝';
 const segments=prepareGroundingSegments(subject,body);
 assert.equal(segments[0].end,3);assert.equal(segments[1].end,6);assert.equal(segments[2].start,8);
 for(const s of segments)assert.equal(Array.from(s.field==='subject'?subject:body).slice(s.start,s.end).join(''),s.exact_text);
 assert.equal(segments.length,4);assert.ok(segments.every(s=>s.classification===''&&s.evidence_refs.length===0));
});
test('D03 split code-point ranges reclassify both pieces without destroying text',()=>{
 const [s]=prepareGroundingSegments('😀甲乙','Body');const parts=splitGroundingSegment({...s,classification:'factual',reason:'old proof'},1);
 assert.deepEqual(parts.map(p=>[p.start,p.end,p.exact_text,p.classification]),[[0,1,'😀',''],[1,3,'甲乙','']]);
 assert.equal(parts.map(p=>p.exact_text).join(''),s.exact_text);assert.throws(()=>splitGroundingSegment(s,0));assert.throws(()=>splitGroundingSegment(s,3));assert.throws(()=>splitGroundingSegment(s,1.5));
});
