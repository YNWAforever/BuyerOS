import cleanup from '../../tests/e2e/audit-teardown';
import {readFileSync,writeFileSync,existsSync} from 'node:fs';
import {spawnSync} from 'node:child_process';
export default function(){
 const names:string[]=[];
 const db='test-results/e2e-db-container.txt',ui='test-results/audit-ui-container.json';
 if(existsSync(db)){const name=readFileSync(db,'utf8').trim();if(!/^buyeros-test-[a-z0-9]+$/.test(name))throw new Error('unrecognized DB marker');names.push(name);}
 if(existsSync(ui)){const proof=JSON.parse(readFileSync(ui,'utf8'));if(!/^buyeros-audit-ui-[0-9a-f]{12}$/.test(proof.name)||proof.name!==`buyeros-audit-ui-${proof.owner}`)throw new Error('unrecognized UI marker');names.push(proof.name);}
 // Execute the unchanged actual teardown with its original ownership guards.
 cleanup();
 const checks=names.map(name=>{const result=spawnSync('docker',['inspect',name],{encoding:'utf8',timeout:30000});const absent=result.status!==0&&/no such (object|container)/i.test(result.stderr);if(!absent)throw new Error(`fixture cleanup not proven ${name}`);return {name,absent};});
 if(existsSync(db)||existsSync(ui))throw new Error('fixture marker remains');
 writeFileSync('test-results/q11-capability-guidance/ui-cleanup.json',JSON.stringify({checks,markersAbsent:true,actualTeardown:true},null,2)+'\n');
}

