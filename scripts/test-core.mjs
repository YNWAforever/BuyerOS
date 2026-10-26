/** Fast, deterministic client contracts; no server, database, browser or provider. */
import {mkdirSync,readdirSync} from 'node:fs';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const root=fileURLToPath(new URL('../',import.meta.url));
mkdirSync(new URL('../test-results/',import.meta.url),{recursive:true});
const files=readdirSync(new URL('../tests/',import.meta.url))
  .filter(name=>name.startsWith('core-')&&name.endsWith('.test.mjs'))
  .sort().map(name=>`tests/${name}`);
if(!files.length)throw new Error('No core client tests discovered');
// In-process isolation preserves named node:test cases on the supported runtime.
// Tests replace global fetch only within a test and restore it via t.mock.
const result=spawnSync(process.execPath,['--test','--experimental-test-isolation=none',
  ...process.argv.slice(2),...files,'tests/audit-research-intent.test.mjs'],{cwd:root,stdio:'inherit'});
if(result.error)throw result.error;
process.exit(result.status??1);
