import {expect,test,type Page} from '@playwright/test';
import {createHash} from 'node:crypto';
import {readFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {signInWorkbench,workspace} from './fixtures/workbench-auth';
import {runOwnedFixtureProcess} from './fixtures/owned-fixture-process';

const fixtures=resolve('test-results/native-attachments');
test.beforeAll(async()=>{
  const cwd=resolve('services/api'),python=resolve(cwd,process.platform==='win32'?'.venv/Scripts/python.exe':'.venv/bin/python');
  await runOwnedFixtureProcess(python,['tests/native_browser_fixture.py',fixtures],{cwd,timeout:30_000});
});
test.beforeEach(async()=>{
  const cwd=resolve('services/api'),python=resolve(cwd,process.platform==='win32'?'.venv/Scripts/python.exe':'.venv/bin/python');
  await runOwnedFixtureProcess(python,['tests/native_browser_fixture.py','reset'],{cwd,timeout:30_000});
});
async function editor(page:Page){
  await signInWorkbench(page,true,'access');
  await page.getByRole('button',{name:'New project',exact:true}).click();
  await page.getByLabel('Company name',{exact:true}).fill('Native Attachment Fixture');
  await page.getByLabel('Product / service',{exact:true}).fill('Fixture rice');
  await page.getByLabel('Value proposition',{exact:true}).fill('Proposed wholesale supply awaiting review.');
  await page.getByRole('button',{name:'Continue',exact:true}).click();
  await page.getByLabel('Markets (country codes or names)',{exact:true}).fill('GB');
  await page.getByLabel('Languages (codes or names)',{exact:true}).fill('en');
  await page.getByRole('checkbox',{name:'Importer',exact:true}).check();
  await page.getByRole('button',{name:'Continue',exact:true}).click();
  await page.getByLabel('Must have',{exact:true}).fill('Public rice portfolio\nA documented wholesale channel');
  await page.getByLabel('Nice to have',{exact:true}).fill('Foodservice distribution');
  await page.getByLabel('Exclude',{exact:true}).fill('No online resale pitch');
  await page.getByRole('checkbox',{name:/I confirm these buyer requirements/}).check();
  await page.getByRole('button',{name:'Continue',exact:true}).click();
  await page.getByRole('button',{name:'Save profile',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Profile version 1 · saved',exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Edit offer',exact:true}).click();
  await expect(page.getByLabel('Offer file')).toHaveAttribute('accept',/\.pptx/);
}
const row=(page:Page,name:string)=>page.locator('.live-offer-docs li').filter({has:page.getByText(name,{exact:true})});
async function upload(page:Page,name='native-large.pptx'){
  await page.getByLabel('Offer file').setInputFiles(resolve(fixtures,name));
  await page.getByRole('button',{name:'Upload document',exact:true}).click();
  await expect(row(page,name).getByRole('checkbox',{name:'Use in profile'})).toBeVisible();
}

test('native large PPTX original, literal slide text and complete profile survive save and reload',async({page,request})=>{
  const paid:string[]=[];page.on('request',r=>{if(r.method()==='POST'&&/\/(?:runs|lookup-quotes|draft-generations|send)(?:\?|$)/.test(r.url()))paid.push(r.url());});
  await editor(page);await upload(page);
  const attached=row(page,'native-large.pptx');
  await attached.getByRole('button',{name:'View slide text'}).click();
  await expect(attached.getByText('Literal <markup> 中文 source',{exact:true})).toBeVisible();
  await expect(attached.getByText('Slide 1: Product: Native fixture rice',{exact:true})).toBeVisible();
  const download=page.waitForEvent('download');await attached.getByRole('button',{name:'Download original'}).click();
  const downloaded=await download;expect(downloaded.suggestedFilename()).toBe('native-large.pptx');
  const actual=await readFile((await downloaded.path())!),expected=await readFile(resolve(fixtures,'native-large.pptx'));
  expect(createHash('sha256').update(actual).digest('hex')).toBe(createHash('sha256').update(expected).digest('hex'));
  await attached.getByRole('checkbox',{name:'Use in profile'}).check();
  await page.getByRole('button',{name:'Continue',exact:true}).click();await page.getByRole('button',{name:'Continue',exact:true}).click();
  await expect(page.getByRole('textbox',{name:'Must have',exact:true})).toHaveValue('Public rice portfolio\nA documented wholesale channel');
  await page.getByRole('checkbox',{name:/I confirm these buyer requirements/}).check();await page.getByRole('button',{name:'Continue',exact:true}).click();
  await page.getByRole('button',{name:'Save profile',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Profile version 2 · saved',exact:true})).toBeVisible();
  const project=new URL(page.url()).searchParams.get('project');expect(project).toBeTruthy();
  await page.reload();await page.getByRole('button',{name:'Edit offer',exact:true}).click();
  await expect(row(page,'native-large.pptx').getByRole('checkbox',{name:'Use in profile'})).toBeChecked();
  const profiles=await request.get(`http://localhost:5173/v1/workspaces/${workspace}/projects/${project}/icp-versions`,{headers:{Authorization:'Bearer fixture-access'}});
  expect(profiles.ok()).toBe(true);const values=(await profiles.json()).data.items;
  const saved=values.find((value:{number:number})=>value.number===2);expect(saved).toBeTruthy();
  expect(saved.requirements).toHaveLength(4);expect(saved.offer_document_ids).toHaveLength(1);
  expect(paid).toEqual([]);
  await page.screenshot({path:'test-results/native-attachments/source-profile-readback.png',fullPage:true});
});

test('lost chunk response reload resumes the same manifest without duplicate attachment',async({page})=>{
  await editor(page);let lost=false;const indices:number[]=[];
  await page.route('**/offer-document-uploads/*/chunks/*',async route=>{
    if(route.request().method()!=='PUT'){await route.continue();return;}
    indices.push(Number(new URL(route.request().url()).pathname.split('/').at(-1)));
    if(!lost){lost=true;const response=await route.fetch();expect(response.ok()).toBe(true);await route.abort('failed');}
    else await route.continue();
  });
  await page.getByLabel('Offer file').setInputFiles(resolve(fixtures,'native-large.pptx'));await page.getByRole('button',{name:'Upload document',exact:true}).click();
  await expect(page.getByText(/Upload paused\. Reselect the same file to resume:/)).toBeVisible();
  await page.reload();await page.getByRole('button',{name:'Edit offer',exact:true}).click();
  await expect(page.getByText(/Upload paused\. Reselect the same file to resume:/)).toBeVisible();
  await upload(page);expect(indices).toEqual([0,1,2]);
  await upload(page);await expect(row(page,'native-large.pptx')).toHaveCount(1);
});

test('lost complete response resolves one receipt and image-only source is explicit in Chinese',async({page})=>{
  await editor(page);let completions=0;
  await page.route('**/offer-document-uploads/*/complete',async route=>{completions++;const response=await route.fetch();expect(response.status()).toBe(202);await route.abort('failed');});
  await upload(page,'native-image.pptx');expect(completions).toBe(1);
  await expect(page.getByText(/This presentation contains images without editable slide text/)).toBeVisible();
  await page.locator('header select').selectOption('zh-HK');await page.setViewportSize({width:390,height:844});
  await expect(page.getByText(/此簡報由圖片組成/)).toBeVisible();expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.screenshot({path:'test-results/native-attachments/image-only-zh-mobile.png',fullPage:true});
});

test('corrupt original transfer produces no browser download and foreign actor cannot resume',async({page,request})=>{
  await editor(page);let uploadId='';page.on('response',r=>{if(r.request().method()==='PUT')uploadId=new URL(r.url()).pathname.split('/').at(-3)??'';});
  await upload(page);
  const foreign=await request.get(`http://localhost:5173/v1/workspaces/${workspace}/offer-document-uploads/${uploadId}`,{headers:{Authorization:'Bearer fixture-admin'}});expect(foreign.status()).toBe(404);
  let downloads=0;page.on('download',()=>downloads++);
  await page.route('**/offer-documents/*/content-chunks/*',async route=>{const response=await route.fetch(),body=await response.json();body.data.body_base64='AAAA';await route.fulfill({response,json:body});});
  await row(page,'native-large.pptx').getByRole('button',{name:'Download original'}).click();
  await expect(page.getByRole('alert')).toContainText('hash mismatch');expect(downloads).toBe(0);
});
