import cleanupDatabase from './teardown';
import {readFileSync,rmSync} from 'node:fs';
import {spawnSync} from 'node:child_process';
export default function cleanupAuditFixtures(){
  cleanupDatabase();
  const marker='test-results/audit-ui-container.json';
  let proof:{name:string;owner:string};
  try{proof=JSON.parse(readFileSync(marker,'utf8'));}catch{return;}
  if(!/^buyeros-audit-ui-[0-9a-f]{12}$/.test(proof.name)||proof.name!==`buyeros-audit-ui-${proof.owner}`)throw new Error('unrecognized UI fixture');
  const inspect=spawnSync('docker',['inspect',proof.name],{encoding:'utf8'});
  if(inspect.status===0){const item=JSON.parse(inspect.stdout)[0];
    if(item.Config.Labels?.['buyeros.audit.owner']!==proof.owner)throw new Error('unowned UI fixture');
    const removed=spawnSync('docker',['rm','-f',proof.name],{encoding:'utf8'});if(removed.status!==0)throw new Error(removed.stderr);
  }
  rmSync(marker);
}
