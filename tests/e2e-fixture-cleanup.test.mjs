import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readdir,readFile} from 'node:fs/promises';

const configs=(await readdir(new URL('../',import.meta.url)))
  .filter(name=>/^playwright(?:\.[a-z-]+)?\.config\.ts$/.test(name));

test('every Playwright config that starts the disposable API fixture runs its container teardown',async()=>{
  const missing=[];
  for(const name of configs){
    const source=await readFile(new URL(`../${name}`,import.meta.url),'utf8');
    if(source.includes('serve_e2e_fixture.py')&&!/globalTeardown\s*:\s*[\'"]\.\/tests\/e2e\/teardown\.ts[\'"]/.test(source)) missing.push(name);
  }
  assert.deepEqual(missing,[]);
});