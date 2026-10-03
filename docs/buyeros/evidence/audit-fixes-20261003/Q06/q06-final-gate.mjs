import {readFileSync} from 'node:fs';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
for(const [path,expected] of [['test-results/q06-api-final.xml',24],['test-results/q06-ui-final.xml',44]]){
 const xml=readFileSync(path,'utf8'),suites=[...xml.matchAll(/<testsuite\s([^>]+)>/g)];assert.ok(suites.length>0);
 const totals={tests:0,failures:0,errors:0,skipped:0};for(const [,raw] of suites){const attr=Object.fromEntries([...raw.matchAll(/([a-zA-Z_]+)="([^"]*)"/g)].map(([,k,v])=>[k,v]));for(const k of Object.keys(totals))totals[k]+=Number(attr[k]??0);}
 assert.deepEqual(totals,{tests:expected,failures:0,errors:0,skipped:0});console.log(path,JSON.stringify(totals));
}
const checks=[['--test','tests/job-poller-checks.mjs','tests/audit-bulk-confirmation.test.mjs','tests/audit-member-contract.test.mjs','tests/audit-research-intent.test.mjs','tests/audit-draft-guard.test.mjs','tests/audit-auth-render.test.mjs'],['--test','tests/live-adapter-checks.mjs','tests/live-auth-checks.mjs'],['scripts/generate-api-types.mjs','--check'],['node_modules/typescript/bin/tsc','--noEmit'],['node_modules/eslint/bin/eslint.js','features/live/bulk-actions.tsx','features/live/buyer-results.tsx','features/live/operations.tsx','services/live/client.ts','services/live/job-poller.ts','tests/e2e/audit-operations.spec.ts']];
for(const args of checks){const r=spawnSync(process.execPath,args,{encoding:'utf8',timeout:180_000});process.stdout.write(r.stdout??'');process.stderr.write(r.stderr??'');assert.equal(r.error,undefined);assert.equal(r.status,0,args.join(' '));console.log('PASS node '+args.join(' '));}
