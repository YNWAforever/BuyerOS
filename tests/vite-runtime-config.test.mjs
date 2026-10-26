import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import test from 'node:test';

test('Vercel dev preserves the explicit API origin while deployment builds use the service proxy',()=>{
  for(const [command,expected] of [['serve','https://api.buyeros.test'],['build','/']]){
    const script=`import {loadConfigFromFile} from 'vite';
      const {config}=await loadConfigFromFile({command:${JSON.stringify(command)},mode:'development'},'vite.config.ts');
      console.log(JSON.stringify({api:JSON.parse(config.define['process.env.BUYEROS_API_BASE_URL']),
        authSettings:Object.keys(config.define).filter(key=>/AUTH_PROVIDER|NEON_|PUBLIC_ORIGIN/.test(key))}));`;
    const result=spawnSync(process.execPath,['--input-type=module','-e',script],{
      cwd:new URL('../',import.meta.url),encoding:'utf8',timeout:30_000,
      env:{...process.env,BUYEROS_DEPLOY_TARGET:'vercel',BUYEROS_API_BASE_URL:'https://api.buyeros.test'},
    });
    assert.equal(result.error,undefined);
    assert.equal(result.status,0,result.stderr);
    assert.deepEqual(JSON.parse(result.stdout.trim()),{api:expected,authSettings:[]});
  }
});
