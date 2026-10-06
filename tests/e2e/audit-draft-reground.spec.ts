import {expect,test,type Page} from '@playwright/test';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {resolve} from 'node:path';
import {readFile,writeFile} from 'node:fs/promises';
import {signInWorkbench,workspace,project,resetWorkbenchFixtureRateWindows} from './fixtures/workbench-auth';
const buyer='e2000000-0000-4000-8000-000000000001';
const subject='邀請😀了解產品';
const body='您好👩‍💻\nFictional industrial sensors\nFixture public catalog lists industrial sensors.\n謝謝！';
async function fixture(...args:string[]){const cwd=resolve('services/worker');return JSON.parse((await promisify(execFile)(resolve(cwd,process.platform==='win32'?'.venv/Scripts/python.exe':'.venv/bin/python'),['tests/fixtures/audit_template.py',...args],{cwd,timeout:60_000})).stdout);}
async function editedDraft(page:Page){
 await resetWorkbenchFixtureRateWindows();const seed=await fixture('prepare');
 await signInWorkbench(page,true,'access',`/app/outreach?workspace=${workspace}&project=${project}&buyer=${buyer}`);
 await page.getByRole('combobox',{name:/^(Language|語言)$/,exact:true}).first().selectOption('en');await expect(page.locator('html')).toHaveAttribute('lang','en');
 const prepare=page.getByRole('region',{name:'Prepare grounded draft',exact:true});await prepare.getByRole('combobox',{name:'Recipient (optional)',exact:true}).selectOption(seed.contact);
 const pending=page.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname.endsWith(`/projects/${project}/drafts`));
 await prepare.getByRole('button',{name:'Generate addressed draft',exact:true}).click();const response=await pending;expect(response.status()).toBe(202);
 const materialized=await fixture('materialize',(await response.json()).data.id);expect(materialized.duplicate).toBe('duplicate');
 await page.getByRole('button',{name:'Refresh job',exact:true}).click();const editor=page.getByRole('region',{name:'Open draft',exact:true});await expect(editor).toBeVisible();
 await editor.getByRole('textbox',{name:'Subject',exact:true}).fill(subject);await editor.getByRole('textbox',{name:'Body',exact:true}).fill(body);await editor.getByRole('combobox',{name:'Language',exact:true}).selectOption('zh-HK');
 await editor.getByRole('button',{name:'Save revision',exact:true}).click();await expect(editor).not.toHaveAttribute('data-live-unsaved','true');
 return {id:materialized.draft,editor,materialized};
}
test('D01/D03 manual Unicode draft exposes a source review and operator cannot attest',async({page})=>{
 const {editor}=await editedDraft(page);await expect(editor).toContainText('Human edits require a new grounding review before approval.');
 const grounding=editor.getByRole('region',{name:'Manual source review',exact:true});await expect(grounding).toBeVisible();
 await expect(grounding).toContainText('A reviewer must submit this source review.');
 await expect(grounding.getByRole('button',{name:'Submit source review',exact:true})).toHaveCount(0);
 await expect(editor.getByRole('textbox',{name:'Body',exact:true})).toHaveValue(body);
});

async function reviewerPage(page:Page,id:string,locale='en'){
 await signInWorkbench(page,true,'reviewer',`/app/outreach?workspace=${workspace}&project=${project}&draft=${id}`);
 await page.getByRole('combobox',{name:/^(Language|語言)$/,exact:true}).first().selectOption(locale);await expect(page.locator('html')).toHaveAttribute('lang',locale);
 return page.getByRole('region',{name:/^(Open draft|開啟草稿)$/,exact:true});
}
async function classify(page:Page,split=false){
 const grounding=page.getByRole('region',{name:/^(Manual source review|人工來源覆核)$/,exact:true});await expect(grounding).toBeVisible();await expect(grounding.getByRole('group')).toHaveCount(5);await expect(grounding.getByRole('status')).toHaveCount(0);
 if(split){const first=grounding.getByRole('group').first();await first.getByRole('spinbutton').fill('2');await first.getByRole('button',{name:'分開段落',exact:true}).click();}
 const groups=grounding.getByRole('group');const count=await groups.count();expect(count).toBe(split?6:5);
 for(let i=0;i<count;i++){
  const group=groups.nth(i),text=await group.locator('pre').innerText();const factual=text==='Fictional industrial sensors'||text.startsWith('Fixture public');
  await group.getByRole('combobox').selectOption(factual?'factual':'non_factual');await group.getByRole('textbox').fill(factual?'Read original retained source':'Greeting, invitation or closing; no factual assertion');
  if(factual)await group.getByRole('checkbox',{name:text.startsWith('Fixture')?/^(Evidence|證據)/:/^(Offer fact|產品事實)/}).check();
 }
 await grounding.getByRole('textbox',{name:/^(Overall review reason|整體覆核理由)$/,exact:true}).fill('Full message and every versioned source read');
 await grounding.getByRole('checkbox',{name:/^(I read the entire exact message|我已閱讀整篇精確訊息)/}).check();
 const submit=grounding.getByRole('button',{name:/^(Submit source review|提交來源覆核)$/,exact:true});await expect(submit).toBeEnabled();return {grounding,submit};
}
async function approveExport(page:Page,editor:ReturnType<Page['getByRole']>,id:string,label:string){
 await editor.getByRole('button',{name:/^(Request exact review|要求審核此版本)$/,exact:true}).click();
 await editor.getByRole('checkbox',{name:/^(I confirm the exact recipient|我確認以上精確收件人)/}).check();await editor.getByRole('button',{name:/^(Approve exact revision|批准此精確版本)$/,exact:true}).click();
 const exports=editor.getByRole('region',{name:/^(Authorized export|授權匯出)$/,exact:true});await exports.getByRole('button',{name:/^(Prepare approved copy|準備已批准副本)$/,exact:true}).click();
 const downloading=page.waitForEvent('download');await exports.getByRole('button',{name:/^(Download text|下載文字)$/,exact:true}).click();const text=await readFile((await (await downloading).path())!,'utf8');expect(text).toContain(body);expect(text).toContain(subject);await writeFile(`test-results/q12-${label}-export.txt`,text);
 const stored=await page.request.get(`http://127.0.0.1:8000/v1/workspaces/${workspace}/drafts/${id}`,{headers:{Authorization:'Bearer fixture-reviewer'}});expect(stored.status()).toBe(200);const draft=(await stored.json()).data;
 expect(draft.revision_number).toBe(3);expect(draft.body).toBe(body);expect(draft.grounding_review.reviewed_by).toBe('e0000000-0000-4000-8000-000000000004');
 const exportId=new URL(page.url()).searchParams.get('export');const viewer=await page.request.get(`http://127.0.0.1:8000/v1/workspaces/${workspace}/exports/${exportId}/content`,{headers:{Authorization:'Bearer fixture-viewer'}});expect(viewer.status()).toBe(403);
 const deliver=await page.request.post(`http://127.0.0.1:8000/v1/workspaces/${workspace}/drafts/${id}/deliver`,{headers:{Authorization:'Bearer fixture-reviewer','Idempotency-Key':`q12-${label}-delivery`}});expect(deliver.status()).toBe(403);expect((await deliver.json()).code).toBe('DELIVERY_DISABLED');
 await writeFile(`test-results/q12-${label}-output.json`,JSON.stringify({fixture_only:true,draft,viewer_export:viewer.status(),delivery:deliver.status()},null,2));
}
async function resetLocale(page:Page){await page.getByRole('combobox',{name:/^(Language|語言)$/,exact:true}).first().selectOption('en');await expect(page.locator('html')).toHaveAttribute('lang','en');}

test('D01/U09 reviewer failure retains preparation; lost committed response retries same key then exact approval/export',async({page,browser})=>{
 const created=await editedDraft(page);const ctx=await browser.newContext();const reviewer=await ctx.newPage();
 try{
  const editor=await reviewerPage(reviewer,created.id);const {grounding,submit}=await classify(reviewer);
  const path=`**/v1/workspaces/${workspace}/drafts/${created.id}/grounding-reviews`;let first=true;
  await reviewer.route(path,async route=>{if(!first)return route.continue();first=false;await route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({code:'PROVIDER_UNAVAILABLE',message:'Q12 isolated HTTP failure',request_id:'00000000-0000-4000-8000-000000000012',retryable:true})});});
  await submit.click();await expect(grounding.getByRole('alert')).toBeVisible();await expect(submit).toBeEnabled();await expect(grounding.getByRole('checkbox',{name:/I read the entire/})).toBeChecked();await expect(editor.getByRole('textbox',{name:'Body',exact:true})).toHaveValue(body);await reviewer.unroute(path);
  const requests:{key:string;body:unknown}[]=[];first=true;
  await reviewer.route(path,async route=>{requests.push({key:route.request().headers()['idempotency-key'],body:route.request().postDataJSON()});if(!first)return route.continue();first=false;const committed=await route.fetch();expect(committed.status(),await committed.text()).toBe(200);await route.abort('failed');});
  await submit.click();await expect(grounding.getByRole('alert')).toBeVisible();await expect(submit).toBeEnabled();await expect(editor.getByRole('textbox',{name:'Body',exact:true})).toHaveValue(body);
  await submit.click();await expect(reviewer.getByText('Source review recorded; request a new exact review.',{exact:true})).toBeVisible();expect(requests).toHaveLength(2);expect(requests[1]).toEqual(requests[0]);await reviewer.unroute(path);
  await reviewer.reload();await reviewerPage(reviewer,created.id);await expect(editor).toContainText('Reviewed by');await expect(editor.getByRole('textbox',{name:'Body',exact:true})).toHaveValue(body);await approveExport(reviewer,editor,created.id,'en');
  await reviewer.screenshot({path:'test-results/q12-en-approved-export.png',fullPage:true});await writeFile('test-results/q12-en-retry.json',JSON.stringify({fixture_only:true,synthetic_503:true,actual_committed_response_dropped:true,requests,materialization:created.materialized},null,2));
 }finally{await resetLocale(reviewer);await ctx.close();}
});

test('D03 zh-HK mobile code-point split reads every source and exports exact Unicode message',async({page,browser})=>{
 const created=await editedDraft(page);const ctx=await browser.newContext({viewport:{width:390,height:844}});const reviewer=await ctx.newPage();
 try{
  const editor=await reviewerPage(reviewer,created.id,'zh-HK');const {submit}=await classify(reviewer,true);
  await expect.poll(()=>reviewer.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);await reviewer.screenshot({path:'test-results/q12-zh-mobile-review.png',fullPage:true});
  const response=reviewer.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname.endsWith('/grounding-reviews'));await submit.click();const reviewed=await response;expect(reviewed.status(),await reviewed.text()).toBe(200);
  const proof=(await reviewed.json()).data.grounding_review;expect(proof.segments[0]).toMatchObject({start:0,end:2,exact_text:'邀請'});expect(proof.segments[1]).toMatchObject({start:2,end:Array.from(subject).length,exact_text:'😀了解產品'});expect(proof.segments[2].end).toBe(5);
  await approveExport(reviewer,editor,created.id,'zh');await expect.poll(()=>reviewer.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);await reviewer.screenshot({path:'test-results/q12-zh-mobile-approved-export.png',fullPage:true});
 }finally{await resetLocale(reviewer);await ctx.close();}
});

test('U09 real stale revision preserves source form and exact buffers; scope change rejects delayed review result',async({page,browser})=>{
 const created=await editedDraft(page);const ctx=await browser.newContext();const reviewer=await ctx.newPage();
 try{
  const editor=await reviewerPage(reviewer,created.id);let prepared=await classify(reviewer);
  const base=`http://127.0.0.1:8000/v1/workspaces/${workspace}/drafts/${created.id}`;
  const before=(await (await reviewer.request.get(base,{headers:{Authorization:'Bearer fixture-reviewer'}})).json()).data;
  const edit=await reviewer.request.patch(base,{headers:{Authorization:'Bearer fixture-access','Idempotency-Key':'q12-real-stale-edit','If-Match':`"${before.version}"`},data:{subject}});expect(edit.status()).toBe(200);
  await prepared.submit.click();await expect(prepared.grounding.getByRole('alert')).toBeVisible();await expect(prepared.grounding.getByRole('checkbox',{name:/I read the entire/})).toBeChecked();await expect(editor.getByRole('textbox',{name:'Subject',exact:true})).toHaveValue(subject);await expect(editor.getByRole('textbox',{name:'Body',exact:true})).toHaveValue(body);await expect(editor).not.toHaveAttribute('data-live-unsaved','true');
  await editor.getByRole('button',{name:'Refresh draft',exact:true}).click();await expect(editor).toHaveAttribute('data-baseline-revision',(await edit.json()).data.revision_id);prepared=await classify(reviewer);
  let release:()=>void=()=>{},received:()=>void=()=>{};const held=new Promise<void>(r=>release=r),started=new Promise<void>(r=>received=r);
  const path=`**/v1/workspaces/${workspace}/drafts/${created.id}/grounding-reviews`;
  await reviewer.route(path,async route=>{const response=await route.fetch();expect(response.status()).toBe(200);received();await held;await route.fulfill({response}).catch(()=>{});});
  await prepared.submit.click();await started;await reviewer.getByRole('combobox',{name:'Project',exact:true}).selectOption('e9100000-0000-4000-8000-000000000001');release();
  await expect(reviewer.getByRole('region',{name:'Open draft',exact:true})).toHaveCount(0);await reviewer.waitForTimeout(300);await expect(reviewer.getByRole('region',{name:'Open draft',exact:true})).toHaveCount(0);
 }finally{await resetLocale(reviewer);await ctx.close();}
});
