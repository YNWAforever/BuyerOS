import {existsSync,readFileSync} from 'node:fs';
import {resolve,join} from 'node:path';
export default async function teardown(config){
 const {n00Target:target,n00RunId:runId,n00ProbeScenario:scenario}=config.metadata;
 if(!['portable','vercel'].includes(target)||!['valid','missing','mismatch','expired'].includes(scenario)||!/^[a-f0-9]{12}$/.test(runId??''))throw new Error('N00_PROBE_CLEANUP_SCOPE');
 const folder=resolve('test-results/neon-runtime-built/runs',`${target}-${scenario}-${runId}`),path=join(folder,'runtime.json');
 if(!existsSync(path))return; // Startup failure before ownership is not accepted verification.
 const owner=JSON.parse(readFileSync(path,'utf8'));if(owner.fixture_only!==true||owner.runId!==runId||owner.target!==target||owner.scenario!==scenario)throw new Error('N00_PROBE_CLEANUP_OWNER');
 const response=await fetch('http://127.0.0.1:44901/n00-runtime-stop',{method:'POST',headers:{'X-N00-Owner':runId},redirect:'manual',signal:AbortSignal.timeout(1500)});
 if(response.status!==200||(await response.json()).fixture_only!==true)throw new Error('N00_PROBE_CLEANUP_ACK');
 const deadline=Date.now()+35000;while(!existsSync(join(folder,'cleanup.json'))&&Date.now()<deadline)await new Promise(ok=>setTimeout(ok,100));
 if(!existsSync(join(folder,'cleanup.json')))throw new Error('N00_PROBE_CLEANUP_EVIDENCE');
 const proof=JSON.parse(readFileSync(join(folder,'cleanup.json'),'utf8'));
 if(proof.private_root_removed!==true||proof.runtime_configuration_removed!==true||proof.owned_children_absent!==true||existsSync(owner.private_root))throw new Error('N00_PROBE_CLEANUP_INCOMPLETE');
}
