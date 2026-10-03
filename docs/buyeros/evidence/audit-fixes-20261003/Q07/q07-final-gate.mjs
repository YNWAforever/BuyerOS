import {readFileSync} from 'node:fs';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
for(const [path,expected] of [['test-results/q07-api-final.xml',47],['test-results/q07-worker-final.xml',11],['test-results/q07-ui-final.xml',12]]){
 const xml=readFileSync(path,'utf8'),suites=[...xml.matchAll(/<testsuite\s([^>]+)>/g)];assert.ok(suites.length>0);
 const totals={tests:0,failures:0,errors:0,skipped:0};for(const [,raw] of suites){const attr=Object.fromEntries([...raw.matchAll(/([a-zA-Z_]+)="([^"]*)"/g)].map(([,k,v])=>[k,v]));for(const k of Object.keys(totals))totals[k]+=Number(attr[k]??0);}
 assert.deepEqual(totals,{tests:expected,failures:0,errors:0,skipped:0});console.log(path,JSON.stringify(totals));
}
const a02=JSON.parse(readFileSync('test-results/q07-A02-output.json','utf8'));assert.equal(a02.fixture_only,true);assert.equal(a02.first.subject,a02.second.subject);assert.equal(a02.first.body,a02.second.body);assert.notEqual(a02.first.objective,a02.second.objective);
const a07=JSON.parse(readFileSync('test-results/q07-A07-output.json','utf8'));const copy=readFileSync('test-results/q07-A07-export.txt','utf8').replace(/\r\n/g,'\n');assert.equal(a07.fixture_only,true);assert.ok(copy.includes(a07.draft.body.replace(/\r\n/g,'\n')));assert.ok(copy.includes('Fixture public catalog lists industrial sensors.'));assert.equal(a07.viewer_export,403);assert.equal(a07.delivery,403);
for(const m of [...a02.materialization,a07.materialization]){assert.equal(m.result,'done');assert.equal(m.duplicate,'duplicate');assert.equal(m.revisions,1);assert.deepEqual(m.paid_before,[0,0]);assert.deepEqual(m.paid_after,[0,0]);}
console.log('PASS actual DB output/copy, fenced replay and zero paid intents/holds');
const checks=[['--test','tests/audit-draft-guard.test.mjs','tests/audit-research-intent.test.mjs','tests/live-adapter-checks.mjs','tests/live-auth-checks.mjs'],['scripts/generate-api-types.mjs','--check'],['node_modules/typescript/bin/tsc','--noEmit'],['node_modules/eslint/bin/eslint.js','features/live/drafts.tsx','tests/e2e/audit-template-copy.spec.ts']];
for(const args of checks){const r=spawnSync(process.execPath,args,{encoding:'utf8',timeout:180_000});process.stdout.write(r.stdout??'');process.stderr.write(r.stderr??'');assert.equal(r.error,undefined);assert.equal(r.status,0,args.join(' '));console.log('PASS node '+args.join(' '));}
const patch=spawnSync('git',['apply','--check','docs/buyeros/evidence/audit-fixes-20261003/Q07/generation-pause-rollback.patch'],{encoding:'utf8'});assert.equal(patch.status,0);console.log('PASS generation-pause rollback applicability (no browser rehearsal)');
