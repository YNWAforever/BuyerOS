import {readFileSync,writeFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {spawnSync} from 'node:child_process';
import assert from 'node:assert/strict';
const source=JSON.parse(readFileSync('docs/buyeros/evidence/audit-fixes-20261003/Q08/q08-tested-source.json','utf8'));
for(const item of source.files)assert.equal(createHash('sha256').update(readFileSync(item.path)).digest('hex'),item.sha256,`source changed: ${item.path}`);
const checks=[['node',[process.execPath,'--test','tests/audit-bulk-manifests.test.mjs','tests/audit-bulk-confirmation.test.mjs','tests/audit-member-contract.test.mjs','tests/live-adapter-checks.mjs','tests/job-poller-checks.mjs']],['generated',[process.execPath,'scripts/generate-api-types.mjs','--check']],['type',[process.execPath,'node_modules/typescript/bin/tsc','--noEmit']],['lint',[process.execPath,'node_modules/eslint/bin/eslint.js','features/live/bulk-manifest.tsx','services/live/bulk-manifests.ts','features/live/bulk-actions.tsx','features/live/buyer-results.tsx','tests/e2e/audit-bulk-manifest.spec.ts']]];
for(const [name,[cmd,...args]] of checks){const r=spawnSync(cmd,args,{encoding:'utf8'});writeFileSync(`test-results/q08-gate-${name}.log`,(r.stdout??'')+(r.stderr??''));assert.equal(r.status,0,`${name} failed: ${(r.stdout??'').slice(-1500)} ${(r.stderr??'').slice(-1500)}`);console.log(`${name}: exit0`);}
const xmlScript=`import xml.etree.ElementTree as E,json
reports=[('api','test-results/q08-api-sixth.xml',90),('ui','test-results/q08-ui-final.xml',17),('migrations','test-results/q08-migrations-final.xml',39)]
results={}
for label,path,expected in reports:
 cases=list(E.parse(path).getroot().iter('testcase'));fail=sum(c.find('failure') is not None for c in cases);errors=sum(c.find('error') is not None for c in cases);skip=sum(c.find('skipped') is not None for c in cases)
 assert len(cases)==expected and fail==errors==skip==0,(label,len(cases),fail,errors,skip)
 results[label]={'report':path,'pass':len(cases),'fail':fail,'error':errors,'skip':skip,'test_cases':[{'class':c.get('classname'),'name':c.get('name'),'seconds':c.get('time')} for c in cases]}
print(json.dumps(results))
`;
const p=spawnSync('services/api/.venv/Scripts/python.exe',['-c',xmlScript],{encoding:'utf8'});assert.equal(p.status,0,p.stderr);writeFileSync('test-results/q08-final-counts.json',JSON.stringify(JSON.parse(p.stdout),null,2));
console.log('Completed actual JUnit readback: strict API90/UI17/migrations39; zero fail/error/skip. Readback is not a new DB/UI run.');
const r=spawnSync('git',['apply','--check','docs/buyeros/evidence/audit-fixes-20261003/Q08/q08-pause-admission.patch'],{encoding:'utf8'});assert.equal(r.status,0,r.stderr);
console.log('Q08 gate PASS: source hashes match; fresh Node22/type/generated/lint/rollback; required strict reports90/17/39 confirmed.');
