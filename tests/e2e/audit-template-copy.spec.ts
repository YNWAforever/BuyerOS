import {expect,test,type Page} from '@playwright/test';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {resolve} from 'node:path';
import {readFile,writeFile} from 'node:fs/promises';
import {signInWorkbench,workspace,project,resetWorkbenchFixtureRateWindows} from './fixtures/workbench-auth';
const buyer='e2000000-0000-4000-8000-000000000001';
const source='Fixture public catalog lists industrial sensors.';
async function fixture(...args:string[]){const cwd=resolve('services/worker');return JSON.parse((await promisify(execFile)(resolve(cwd,process.platform==='win32'?'.venv/Scripts/python.exe':'.venv/bin/python'),['tests/fixtures/audit_template.py',...args],{cwd,timeout:60_000})).stdout);}
async function enter(page:Page){await resetWorkbenchFixtureRateWindows();const seeded=await fixture('prepare');await signInWorkbench(page,true,'access',`/app/outreach?workspace=${workspace}&project=${project}&buyer=${buyer}`);await page.getByRole('combobox',{name:/^(Language|語言)$/,exact:true}).first().selectOption('en');await expect(page.locator('html')).toHaveAttribute('lang','en');return {seeded,prepare:page.getByRole('region',{name:'Prepare grounded draft',exact:true})};}
async function generate(page:Page,prepare:ReturnType<Page['getByRole']>,objective:string,addressed=false){
  await prepare.getByRole('textbox',{name:/^(Internal work objective|內部工作目的)/}).fill(objective);
  const pending=page.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname.endsWith(`/projects/${project}/drafts`));
  await prepare.getByRole('button',{name:addressed?/^(Generate addressed draft|產生已指定收件人的草稿)$/:/^(Generate unaddressed draft|產生未指定收件人的草稿)$/}).click();
  const response=await pending;expect(response.status(),await response.text()).toBe(202);
  const command=response.request().postDataJSON();expect(command.tone).toBe('professional');expect(command.objective).toBe(objective);expect(command.max_cost).toEqual({amount:'0.000000',currency:'USD'});
  const job=(await response.json()).data;const materialized=await fixture('materialize',job.id);expect(materialized.duplicate).toBe('duplicate');expect(materialized.paid_after).toEqual(materialized.paid_before);
  await page.getByRole('button',{name:/^(Refresh job|重新整理工作)$/,exact:true}).click();
  const editor=page.getByRole('region',{name:/^(Open draft|開啟草稿)$/,exact:true});await expect(editor).toBeVisible();
  const read=await page.request.get(`http://127.0.0.1:8000/v1/workspaces/${workspace}/drafts/${materialized.draft}`,{headers:{Authorization:'Bearer fixture-access'}});expect(read.status()).toBe(200);
  const draft=(await read.json()).data;expect(await editor.getByRole('textbox',{name:/^(Body|內容)$/,exact:true}).inputValue()).toBe(draft.body);
  return {draft,editor,command,materialized};
}
test('A02 fixed-template promise matches two actual outputs; manual edits keep Q15 dirty protection',async({page})=>{
  const {prepare}=await enter(page);
  await expect(prepare.getByRole('combobox',{name:'Tone',exact:true})).toHaveCount(0);
  await expect(prepare).toContainText('Free fixed template');
  await expect(prepare).toContainText('Internal work objective — does not change the template body');
  await expect(prepare).toContainText('Edit the draft manually after generation; changes need a new grounding review before approval.');
  const first=await generate(page,prepare,'Request a demonstration');const second=await generate(page,prepare,'Discuss procurement');
  expect(second.draft.subject).toBe(first.draft.subject);expect(second.draft.body).toBe(first.draft.body);expect(second.draft.objective).not.toBe(first.draft.objective);expect(second.draft.body).toContain(source);
  await second.editor.getByRole('textbox',{name:'Subject',exact:true}).fill('Q07 manual subject');await second.editor.getByRole('textbox',{name:'Body',exact:true}).fill('Q07 manual content pending grounding review');
  await page.getByRole('button',{name:'Refresh draft',exact:true}).click();await page.getByRole('dialog').getByRole('button',{name:'Cancel',exact:true}).click();await expect(second.editor).toHaveAttribute('data-live-unsaved','true');await expect(second.editor.getByRole('textbox',{name:'Body',exact:true})).toHaveValue('Q07 manual content pending grounding review');
  await page.getByRole('button',{name:'Save revision',exact:true}).click();await expect(second.editor).not.toHaveAttribute('data-live-unsaved','true');await expect(second.editor).toContainText('Human edits require a new grounding review before approval.');await expect(second.editor.getByRole('button',{name:'Request exact review',exact:true})).toHaveCount(0);
  await page.screenshot({path:'test-results/q07-template-en-edited.png',fullPage:true});await writeFile('test-results/q07-A02-output.json',JSON.stringify({fixture_only:true,first:first.draft,second:second.draft,materialization:[first.materialized,second.materialized]},null,2));
});
test('A07 zh-HK mobile template keeps original English citations through exact approval and authorized export',async({page,browser})=>{
  await page.setViewportSize({width:390,height:844});const {seeded,prepare:englishPrepare}=await enter(page);
  await page.getByRole('combobox',{name:'Language',exact:true}).first().selectOption('zh-HK');const prepare=page.getByRole('region',{name:'準備有證據草稿',exact:true});
  await expect(englishPrepare).toHaveCount(0);await expect(prepare).toContainText('免費固定模板');await expect(prepare).toContainText('內部工作目的，不會改變模板正文');await expect(prepare).toContainText('模板語言只改變固定標題、開場及結尾；產品事實與來源引用保留原語言，不會自動翻譯。');await expect(prepare.getByRole('combobox',{name:'語氣',exact:true})).toHaveCount(0);
  await prepare.getByRole('combobox',{name:'收件人（可選）',exact:true}).selectOption(seeded.contact);await prepare.getByRole('combobox',{name:'模板語言',exact:true}).selectOption('zh-HK');
  const generated=await generate(page,prepare,'內部跟進工作',true);expect(generated.draft.body).toContain('你好，');expect(generated.draft.body).toContain(source);expect(generated.draft.body).toContain('Fictional industrial sensors');expect(generated.draft.body).toContain('[evidence:');
  await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);await page.screenshot({path:'test-results/q07-template-zh-mobile.png',fullPage:true});
  await page.getByRole('button',{name:'要求審核此版本',exact:true}).click();
  const context=await browser.newContext({viewport:{width:390,height:844}});const reviewer=await context.newPage();
  try{
    await signInWorkbench(reviewer,true,'reviewer',`/app/outreach?workspace=${workspace}&project=${project}&draft=${generated.draft.id}`);
    await reviewer.getByRole('combobox',{name:/^(Language|語言)$/,exact:true}).first().selectOption('zh-HK');await expect(reviewer.locator('html')).toHaveAttribute('lang','zh-HK');
    await reviewer.getByRole('checkbox',{name:/我確認以上精確收件人/}).check();await reviewer.getByRole('button',{name:'批准此精確版本',exact:true}).click();
    const exports=reviewer.getByRole('region',{name:'授權匯出',exact:true});await exports.getByRole('button',{name:'準備已批准副本',exact:true}).click();await expect(exports).toContainText('允許: 1');
    const downloaded=reviewer.waitForEvent('download');await exports.getByRole('button',{name:'下載文字',exact:true}).click();const copy=await readFile((await (await downloaded).path())!,'utf8');expect(copy).toContain(source);expect(copy).toContain('你好，');expect(copy).toContain('recipient@fixture.example.test');
    await writeFile('test-results/q07-A07-export.txt',copy);await reviewer.screenshot({path:'test-results/q07-template-zh-approved-export.png',fullPage:true});
    const exportId=new URL(reviewer.url()).searchParams.get('export');const denied=await reviewer.request.get(`http://127.0.0.1:8000/v1/workspaces/${workspace}/exports/${exportId}/content`,{headers:{Authorization:'Bearer fixture-viewer'}});expect(denied.status()).toBe(403);
    const deliver=await reviewer.request.post(`http://127.0.0.1:8000/v1/workspaces/${workspace}/drafts/${generated.draft.id}/deliver`,{headers:{Authorization:'Bearer fixture-reviewer','Idempotency-Key':'q07-disabled-delivery'}});expect(deliver.status()).toBe(403);expect((await deliver.json()).code).toBe('DELIVERY_DISABLED');
    await writeFile('test-results/q07-A07-output.json',JSON.stringify({fixture_only:true,draft:generated.draft,materialization:generated.materialized,viewer_export:denied.status(),delivery:deliver.status()},null,2));
  }finally{await reviewer.getByRole('combobox',{name:/^(Language|語言)$/,exact:true}).first().selectOption('en');await expect(reviewer.locator('html')).toHaveAttribute('lang','en');await context.close();await page.getByRole('combobox',{name:'語言',exact:true}).first().selectOption('en');await expect(page.locator('html')).toHaveAttribute('lang','en');}
});
