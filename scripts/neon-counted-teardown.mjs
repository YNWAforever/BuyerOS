/** Public Playwright globalTeardown runs before webServer termination. */
import {existsSync,readFileSync} from 'node:fs';
import {resolve,join} from 'node:path';
export default async function teardown(config) {
 const {n00Target,n00RunId}=config.metadata;
 if(!['portable','vercel'].includes(n00Target)||!/^[a-f0-9]{12}$/.test(n00RunId??''))throw new Error('N00 fixture cleanup scope refused');
 const folder=resolve('test-results/neon-counted-transport',n00Target+'-'+n00RunId),path=join(folder,'runtime.json');
 if(!existsSync(path))return; // Startup failed before resource registration; not acceptance.
 const owner=JSON.parse(readFileSync(path,'utf8'));
 if(owner.fixture_only!==true||owner.runId!==n00RunId||owner.target!==n00Target)throw new Error('N00 fixture cleanup ownership refused');
 const response=await fetch('http://127.0.0.1:44891/n00-fixture-stop',{method:'POST',headers:{'X-N00-Owner':n00RunId},redirect:'manual',signal:AbortSignal.timeout(1500)});
 if(response.status!==200||(await response.json()).fixture_only!==true)throw new Error('N00 fixture cleanup acknowledgement failed');
 const deadline=Date.now()+10_000;
 while(!existsSync(join(folder,'cleanup.json'))&&Date.now()<deadline)await new Promise(ok=>setTimeout(ok,100));
 if(!existsSync(join(folder,'cleanup.json')))throw new Error('N00 fixture cleanup evidence missing');
 const proof=JSON.parse(readFileSync(join(folder,'cleanup.json'),'utf8'));
 if(proof.owned_journal_removed!==true||existsSync(owner.budget_root))throw new Error('N00 fixture journal cleanup incomplete');
}
