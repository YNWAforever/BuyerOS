// Read-only dev-bundler warmup for the owned fictional demo fixture only.
// Functional case assertions retain their original 5s bounds; this is not a latency/UAT pass.
import {chromium} from '@playwright/test';
import {readFileSync,writeFileSync} from 'node:fs';
import {execFileSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {resolve} from 'node:path';
export default async function warmDemo(){
 const owner=createHash('sha256').update(resolve('.')).digest('hex').slice(0,12);
 const meta=JSON.parse(readFileSync('test-results/audit-ui-container.json','utf8'));
 if(meta.owner!==owner||meta.name!==`buyeros-audit-ui-${owner}`||meta.mode!=='demo'||meta.runtime!=='dev'||meta.executionProfile!=='portable')throw new Error('Demo warmup requires exact owned demo fixture');
 const inspected=JSON.parse(execFileSync('docker',['inspect',meta.name],{encoding:'utf8',timeout:10_000}))[0];
 if(inspected.Config.Labels?.['buyeros.audit.owner']!==owner)throw new Error('Unowned demo fixture');
 const started=Date.now(),deadline=started+30_000;
 const remaining=()=>{const left=deadline-Date.now();if(left<=0)throw new Error('Demo fixture hydration setup exceeded30s');return left;};
 const browser=await chromium.launch({headless:true,timeout:remaining()});
 try{
  const page=await browser.newPage();
  await page.goto('http://localhost:5173/app/settings',{waitUntil:'domcontentloaded',timeout:remaining()});
  await page.locator('main[data-demo-ready="true"]').waitFor({state:'visible',timeout:remaining()});
  await page.getByRole('heading',{name:'Settings',exact:true}).waitFor({state:'visible',timeout:Math.min(5_000,remaining())});
  writeFileSync('test-results/q09-demo-warmup-proof.json',JSON.stringify({fixture_only:true,owner_label_verified:true,mode:'demo',runtime:'dev',executionProfile:'portable',url:'http://localhost:5173/app/settings',hydration_ready:true,elapsed_ms:Date.now()-started,fixture_startup_bound_ms:30_000,functional_assertion_timeouts_unchanged:true,employee_or_production_latency_acceptance:false},null,2));
 }finally{await browser.close();}
}
