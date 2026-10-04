import {test} from 'node:test';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {fixtureChildEnvironment} from '../scripts/neon-compatibility-harness.mjs';
function discovered(config){
 const result=spawnSync(process.execPath,['node_modules/@playwright/test/cli.js','test','--config',config,'--list','--reporter=json'],{encoding:'utf8',timeout:60_000,env:{...fixtureChildEnvironment(process.env),BUYEROS_N00_TARGET:'portable'}});
 assert.equal(result.status,0,result.stderr||result.error?.message);
 const files=[];function visit(suite){for(const spec of suite.specs??[])files.push(spec.file);for(const child of suite.suites??[])visit(child);}
 for(const suite of JSON.parse(result.stdout).suites)visit(suite);return files;
}
for(const config of ['playwright.audit-fixes.config.ts','playwright.audit-regression.config.ts'])test(`N00 built fixture is isolated from ${config}`,()=>{const files=discovered(config);assert.ok(files.some(file=>file.endsWith('audit-auth-entry.spec.ts')),'existing Q01 tests stay selected');assert.equal(files.filter(file=>file.endsWith('audit-neon-compat.spec.ts')).length,0,'different runtime/upstream ports must not enter the DB workbench');});
test('N00 dedicated config discovers all seven built-output cases',()=>{const files=discovered('playwright.neon-auth.config.ts');assert.equal(files.length,7);assert.ok(files.every(file=>file.endsWith('audit-neon-compat.spec.ts')));});

test('N00 counted config discovers the same seven cases with separate producer outputs',()=>{const files=discovered('playwright.neon-counted.config.ts');assert.equal(files.length,7);assert.ok(files.every(file=>file.endsWith('audit-neon-compat.spec.ts')));});

for(const config of ['playwright.audit-fixes.config.ts','playwright.audit-regression.config.ts'])test(`all N00 output profiles stay isolated from ${config}`,()=>{const files=discovered(config);assert.ok(files.some(file=>file.endsWith('audit-auth-entry.spec.ts')));assert.equal(files.filter(file=>file.includes('audit-neon-')).length,0);});
test('runtime flow config discovers five actual-output cases',()=>{const files=discovered('playwright.neon-runtime-flow.config.ts');assert.equal(files.length,5);assert.ok(files.every(file=>file.endsWith('audit-neon-runtime-flow.spec.ts')));});
