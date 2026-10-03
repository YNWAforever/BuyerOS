import {readFileSync,writeFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {spawnSync} from 'node:child_process';
import assert from 'node:assert/strict';
const source=JSON.parse(readFileSync('docs/buyeros/evidence/audit-fixes-20261003/Q14/q14-tested-source.json','utf8'));
for(const item of source.files)assert.equal(createHash('sha256').update(readFileSync(item.path)).digest('hex'),item.sha256,`Source changed: ${item.path}`);
const checks=[['node',[process.execPath,'--test','tests/audit-job-query.test.mjs','tests/live-adapter-checks.mjs','tests/live-auth-checks.mjs','tests/job-poller-checks.mjs']],['generated',[process.execPath,'scripts/generate-api-types.mjs','--check']],['type',[process.execPath,'node_modules/typescript/bin/tsc','--noEmit']],['lint',[process.execPath,'node_modules/eslint/bin/eslint.js','features/live/overview.tsx','features/live/operations.tsx','features/live/locale.ts','services/live/job-query.ts','tests/e2e/audit-job-scope.spec.ts']]];
for(const [name,[cmd,...args]] of checks){const r=spawnSync(cmd,args,{encoding:'utf8'});writeFileSync(`test-results/q14-gate-${name}.log`,(r.stdout??'')+(r.stderr??''));assert.equal(r.status,0,`${name} failed: ${r.stdout} ${r.stderr}`);console.log(`${name}: exit0`);}
const script=`import json,xml.etree.ElementTree as E
results={}
for label,path,expected in [('api','test-results/q14-api-final.xml',18),('ui','test-results/q14-ui-second.xml',10)]:
 cases=list(E.parse(path).getroot().iter('testcase'));f=sum(c.find('failure')is not None for c in cases);err=sum(c.find('error')is not None for c in cases);s=sum(c.find('skipped')is not None for c in cases)
 assert len(cases)==expected and f==err==s==0,(label,len(cases),f,err,s)
 results[label]={'pass':len(cases),'fail':f,'error':err,'skip':s,'cases':[{'class':c.get('classname'),'name':c.get('name'),'seconds':c.get('time')}for c in cases]}
print(json.dumps(results))
`;
const r=spawnSync('services/api/.venv/Scripts/python.exe',['-c',script],{encoding:'utf8'});assert.equal(r.status,0,r.stderr);writeFileSync('test-results/q14-final-counts.json',JSON.stringify(JSON.parse(r.stdout),null,2));
console.log('Q14 gate PASS:8 source hashes match; fresh Node16/generated/type/lint; actual strict API18/UI10 readback, zero fail/error/skip. Readback is not a new DB/UI run.');
