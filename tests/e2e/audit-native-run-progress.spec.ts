import {expect,test,type Page} from '@playwright/test';
import {signInWorkbench,workspace,resetWorkbenchFixtureRateWindows} from './fixtures/workbench-auth';
const project='e9100000-0000-4000-8000-000000000001',run='e9400000-0000-4000-8000-000000000001';
const entry=`/app/discover/${run}?workspace=${workspace}&project=${project}`;
// Built UI contract only: run responses are synthetic; native DB/API proof is separate.
async function fixture(page:Page,status:string,retryable:boolean,pending:boolean){
 const posts:{headers:Record<string,string>;body:unknown}[]=[];
 const money=(amount:string)=>({amount,currency:'USD'});
 let current={id:run,workspace_id:workspace,project_id:project,icp_version_id:'e9200000-0000-4000-8000-000000000001',
 version:7,created_at:'2026-10-08T00:00:00Z',updated_at:'2026-10-08T00:01:00Z',data_mode:'live',status,
 stage:'fit_review_required',raw_count:2,company_count:1,assessed_count:1,target_companies:2,last_event_sequence:0,attempt:1,
 max_cost:money('2.000000'),spent:money('0.000000'),reserved:money('0.100000'),limits:{},retryable,reconciliation_pending:pending};
 const envelope=(data:unknown)=>({data,request_id:'synthetic-native-progress-ui',data_mode:'live'});
 await page.route(`**/v1/workspaces/${workspace}/runs/${run}`,route=>route.fulfill({json:envelope(current)}));
 await page.route(`**/v1/workspaces/${workspace}/runs/${run}/retry`,async route=>{
   posts.push({headers:route.request().headers(),body:route.request().postDataJSON()});
   current={...current,status:'queued',stage:'fit',version:8,attempt:2,retryable:false,reconciliation_pending:false};
   return route.fulfill({status:202,json:envelope(current)});
 });
 await page.route(`**/v1/workspaces/${workspace}/runs/${run}/candidates**`,route=>route.fulfill({json:envelope({items:[],offset:0,limit:20,total:0})}));
 await resetWorkbenchFixtureRateWindows();await signInWorkbench(page,false,'admin',entry);
 await page.getByRole('combobox',{name:/^(Language|語言)$/}).selectOption('en');
 const panel=page.getByRole('region',{name:'Research runs',exact:true});await expect(panel.getByText('Actual yield',{exact:false})).toBeVisible();
 return {panel,posts};
}
test('C61 native progress exposes waiting original reconciliation and preserves hold in both languages',async({page})=>{
 const f=await fixture(page,'awaiting_reconciliation',false,true);
 await expect(f.panel.getByText('Wait for provider reconciliation; the hold remains.',{exact:false})).toBeVisible();
 await expect(f.panel.getByText('Original provider work is awaiting reconciliation. Its hold and committed results remain.',{exact:true})).toBeVisible();
 await expect(f.panel.getByRole('button',{name:'Stop new work',exact:true})).toBeVisible();
 await expect(f.panel.getByRole('button',{name:'Retry safe work',exact:true})).toHaveCount(0);
 await page.getByRole('combobox',{name:'Language'}).selectOption('zh-HK');
 await expect(page.getByText('原供應商操作仍待核對；預留金額及已儲存結果會保留。',{exact:true})).toBeVisible();
 await page.setViewportSize({width:390,height:844});await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 expect(f.posts).toHaveLength(0);
});
test('C61 partial native run hides unsafe retry while committed results remain reviewable',async({page})=>{
 const f=await fixture(page,'partial',false,true);
 await expect(f.panel.getByRole('button',{name:'Retry safe work',exact:true})).toHaveCount(0);
 await expect(f.panel.getByText('Original provider work is awaiting reconciliation. Its hold and committed results remain.',{exact:true})).toBeVisible();
 await expect(f.panel.getByRole('button',{name:'Review committed buyers',exact:true})).toBeEnabled();expect(f.posts).toHaveLength(0);
});
test('C61 current native safe retry sends one versioned checkpoint request',async({page})=>{
 const f=await fixture(page,'partial',true,false);
 await f.panel.getByRole('textbox',{name:'Reason for action',exact:true}).fill('Review confirmed original checkpoint');
 const button=f.panel.getByRole('button',{name:'Retry safe work',exact:true});await expect(button).toBeEnabled();
 await button.evaluate(b=>{(b as HTMLButtonElement).click();(b as HTMLButtonElement).click();});
 await expect.poll(()=>f.posts.length).toBe(1);await expect(f.panel.getByText('Waiting for the worker to start.',{exact:false})).toBeVisible();
 expect(f.posts[0].headers['x-buyeros-if-match']).toBe('"7"');expect(f.posts[0].headers['idempotency-key']).toBeTruthy();
 expect(f.posts[0].body).toEqual({reason:'Review confirmed original checkpoint',resume_from_last_committed_checkpoint:true});
 await expect(f.panel.getByRole('button',{name:'Retry safe work',exact:true})).toHaveCount(0);
});
