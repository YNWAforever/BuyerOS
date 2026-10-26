import {expect,test,type Page} from '@playwright/test';
import {resolve} from 'node:path';
import {signIn} from './fixtures/staff-journey';
import {runOwnedFixtureProcess} from './fixtures/owned-fixture-process';
import type {Draft} from '@/services/live/drafts';

const workspace='e0000000-0000-4000-8000-000000000001';
const seededProject='e1000000-0000-4000-8000-000000000001';
const seededDraft='ec000000-0000-4000-8000-000000000001';
const api='http://127.0.0.1:8000';
const headers={Authorization:'Bearer fixture-access'};

test.beforeEach(async({context,page})=>{
  page.setDefaultTimeout(15_000);
  // Page-level synthetic OIDC routes take precedence; all other HTTPS is refused.
  await context.route('https://**/*',route=>route.abort('blockedbyclient'));
  await context.route('**/v1/**/deliver',route=>route.abort('blockedbyclient'));
  page.on('request',request=>{
    if(new URL(request.url()).pathname.endsWith('/deliver'))throw new Error('This acceptance must never request delivery');
  });
});

async function worker(...args:string[]){
  const cwd=resolve('services/worker');
  const result=await runOwnedFixtureProcess(resolve(cwd,'.venv/bin/python'),args,{cwd,timeout:180_000,maxBuffer:1024*1024});
  return JSON.parse(result.stdout.trim().split(/\r?\n/).at(-1)!);
}
async function reloadSignedIn(page:Page){
  await page.reload();
  await expect(page.getByRole('combobox',{name:'Project',exact:true})).not.toHaveValue('');
}

test('committed draft save retries the same command after a lost acknowledgement',async({page,request})=>{
  await signIn(page,'fixture-access',`/app/outreach?workspace=${workspace}&project=${seededProject}&draft=${seededDraft}`);
  const editor=page.getByRole('region',{name:'Open draft',exact:true});
  const before=await request.get(`${api}/v1/workspaces/${workspace}/drafts/${seededDraft}`,{headers});
  expect(before.status()).toBe(200);const original=(await before.json()).data;
  const body=`Saved synthetic recovery revision ${original.revision_number+1}`;
  await editor.getByRole('textbox',{name:'Body',exact:true}).fill(body);
  const posted:{key:string;body:unknown;status:number}[]=[];
  let rejectNext=false;
  await page.route(`**/v1/workspaces/${workspace}/drafts/${seededDraft}`,async route=>{
    if(route.request().method()!=='PATCH')return route.continue();
    if(rejectNext){
      rejectNext=false;
      posted.push({key:route.request().headers()['idempotency-key'],body:route.request().postDataJSON(),status:503});
      return route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({code:'SERVICE_UNAVAILABLE',
        message:'Synthetic pre-commit failure',retryable:true,request_id:'11111111-1111-4111-8111-111111111111'})});
    }
    const response=await route.fetch();
    posted.push({key:route.request().headers()['idempotency-key'],body:route.request().postDataJSON(),status:response.status()});
    if(posted.length===1){expect(response.status()).toBe(200);return route.abort('failed');}
    await route.fulfill({response});
  });
  const save=editor.getByRole('button',{name:'Save revision',exact:true});
  await save.click();await expect(page.getByRole('alert').last()).toBeVisible();
  await expect(editor).toHaveAttribute('data-live-unsaved','true');
  await expect(save).toBeEnabled();await save.click();
  await expect.poll(()=>posted.length).toBe(2);
  expect(posted[1]).toEqual(posted[0]);
  await expect(editor).not.toHaveAttribute('data-live-unsaved','true');
  const read=await request.get(`${api}/v1/workspaces/${workspace}/drafts/${seededDraft}`,{headers});
  const persisted=(await read.json()).data;
  expect(persisted.body).toBe(body);expect(persisted.revision_number).toBe(original.revision_number+1);
  // A rejected pre-commit save retains its intent; edited content must rotate it
  // while this same editor remains mounted, before reload resets its refs.
  rejectNext=true;
  await editor.getByRole('textbox',{name:'Body',exact:true}).fill(body+' changed');
  await save.click();await expect.poll(()=>posted.length).toBe(3);
  await expect(page.getByRole('alert').last()).toBeVisible();
  await expect(editor.getByRole('textbox',{name:'Body',exact:true})).toHaveValue(body+' changed');
  expect(posted[2].key).not.toBe(posted[1].key);
  await editor.getByRole('textbox',{name:'Body',exact:true}).fill(body+' revised after failure');
  await save.click();await expect.poll(()=>posted.length).toBe(4);
  expect(posted[3].key).not.toBe(posted[2].key);expect(posted[3].status).toBe(200);
  await expect(editor).not.toHaveAttribute('data-live-unsaved','true');
  const recovered=await request.get(`${api}/v1/workspaces/${workspace}/drafts/${seededDraft}`,{headers});
  const latest=(await recovered.json()).data;
  expect(latest.body).toBe(body+' revised after failure');expect(latest.revision_number).toBe(original.revision_number+2);
  await reloadSignedIn(page);await expect(editor.getByRole('textbox',{name:'Body',exact:true})).toHaveValue(latest.body);
});

test('synthetic requirement to research results and persisted unsent draft',async({page,browser,request})=>{
  test.setTimeout(360_000);
  await signIn(page,'fixture-access',`/app?workspace=${workspace}&project=${seededProject}`);
  await page.getByRole('region',{name:'Project selection'}).getByRole('button',{name:'New project',exact:true}).click();
  await page.getByLabel('Company name').fill('T30 Fictional Seller');
  await page.getByLabel('Product / service').fill('Industrial sensors');
  await page.getByLabel('Value proposition').fill('Fictional monitoring lowers production downtime.');
  await page.getByRole('button',{name:'Continue',exact:true}).click();
  await page.getByLabel('Markets (country codes or names)').fill('US');
  await page.getByLabel('Languages (codes or names)').fill('en');
  await page.getByRole('checkbox',{name:'Distributor',exact:true}).check();
  await page.getByRole('button',{name:'Continue',exact:true}).click();
  await page.getByRole('textbox',{name:'Must have',exact:true}).fill('industrial sensors');
  await page.getByRole('checkbox',{name:/I confirm these buyer requirements/}).check();
  await page.getByRole('button',{name:'Continue',exact:true}).click();
  await page.getByRole('button',{name:'Save profile',exact:true}).click();
  await expect(page.getByRole('heading',{name:/^Profile version 1/})).toBeVisible();
  const project=new URL(page.url()).searchParams.get('project')!;
  expect(project).toMatch(/^[0-9a-f-]{36}$/);expect(project).not.toBe(seededProject);
  expect((await worker('tests/fixtures/prepare_browser_project.py','prepare',project)).fixture_prerequisites).toBe(true);
  const reviewerContext=await browser.newContext();
  await reviewerContext.route('https://**/*',route=>route.abort('blockedbyclient'));
  const reviewer=await reviewerContext.newPage();
  reviewer.setDefaultTimeout(15_000);
  await signIn(reviewer,'fixture-reviewer',`/app?workspace=${workspace}&project=${project}`);
  await reviewer.getByRole('checkbox',{name:/Confirm approval of this exact version v1/}).check();
  await reviewer.getByRole('button',{name:'Approve profile',exact:true}).click();
  await expect(reviewer.getByText('Current approved: v1')).toBeVisible();
  await reviewer.getByRole('button',{name:'Drafts',exact:true}).click();
  const sender=reviewer.getByRole('region',{name:'Sender identity'});
  await sender.getByLabel('Display name').fill('Fixture Alex');await sender.getByLabel('Organization').fill('T30 Fictional Seller');
  await sender.getByLabel('Business email').fill('alex@example.test');await sender.getByLabel('Reason for change').fill('Synthetic acceptance only');
  await sender.getByRole('checkbox',{name:'I confirm this sender identity'}).check();await sender.getByRole('button',{name:'Save sender'}).click();
  await expect(sender.getByText(/Reviewed sender:/)).toBeVisible();
  await reloadSignedIn(page);await expect(page.getByText('Current approved: v1')).toBeVisible();
  await page.getByRole('button',{name:'Research runs',exact:true}).click();
  await page.getByLabel('Target companies').fill('1');await page.getByLabel('Maximum research cost (USD)').fill('2.000000');
  const admissions:{key:string;body:unknown;id:string}[]=[];
  const runPath=`${api}/v1/workspaces/${workspace}/projects/${project}/runs`;
  await page.route(runPath,async route=>{
    if(route.request().method()!=='POST')return route.continue();
    const response=await route.fetch();expect(response.status()).toBe(202);const value=await response.json();
    admissions.push({key:route.request().headers()['idempotency-key'],body:route.request().postDataJSON(),id:value.data.id});
    if(admissions.length===1)return route.abort('failed');await route.fulfill({response});
  });
  const start=page.getByRole('button',{name:'Start research',exact:true});
  await expect(start).toBeEnabled();
  await start.evaluate(button=>{(button as HTMLButtonElement).click();(button as HTMLButtonElement).click();});
  await expect(page.getByRole('alert').last()).toBeVisible();expect(admissions).toHaveLength(1);
  await page.getByRole('button',{name:/^(Start research|Retry same research)$/}).click();
  await expect.poll(()=>admissions.length).toBe(2);expect(admissions[1]).toEqual(admissions[0]);
  const run=admissions[0].id;await expect(page).toHaveURL(new RegExp(`/app/discover/${run}`));
  const research=await worker('tests/fixtures/run_browser_research.py',run,project);
  console.info('CORE_STAGE research completed',run);
  expect(research.status).toBe('completed');expect(research.buyers).toBe(1);expect(research.evidence).toBeGreaterThan(0);
  await reloadSignedIn(page);
  const runs=await request.get(runPath,{headers});expect(runs.status()).toBe(200);expect((await runs.json()).data.items).toHaveLength(1);
  const contact=await worker('tests/fixtures/prepare_browser_project.py','contact',project,run);
  console.info('CORE_STAGE existing synthetic contact prepared');
  await reviewer.getByRole('button',{name:'Buyers',exact:true}).click();
  await expect(reviewer.getByText('T30 Fictional Industrial Buyer',{exact:true})).toBeVisible();
  await reviewer.getByRole('button',{name:'Details',exact:true}).first().click();
  const review=reviewer.getByRole('dialog',{name:'Buyer details: T30 Fictional Industrial Buyer'});
  await review.getByRole('tab',{name:'Evidence',exact:true}).click();
  await expect(review).toContainText('Fictional distributor lists industrial sensors');
  await review.getByRole('tab',{name:'Overview',exact:true}).click();
  await review.getByRole('textbox',{name:'Individual review reason'}).fill('Synthetic cited result reviewed');
  await review.getByRole('button',{name:/^Save review/}).click();
  console.info('CORE_STAGE buyer review submitted');
  await page.getByRole('button',{name:'Buyers',exact:true}).click();
  await page.getByRole('button',{name:'Details',exact:true}).first().click();
  const dossier=page.getByRole('dialog',{name:'Buyer details: T30 Fictional Industrial Buyer'});
  await expect(dossier).toContainText('Human review: accepted');
  await dossier.getByRole('button',{name:'Prepare grounded draft'}).click();
  await page.getByRole('combobox',{name:'Recipient (optional)'}).selectOption(contact.contact_id);
  await page.getByRole('button',{name:'Generate addressed draft'}).click();
  console.info('CORE_STAGE draft generation submitted');
  await expect.poll(()=>new URL(page.url()).searchParams.get('draft_job')).toMatch(/^[0-9a-f-]{36}$/);
  const job=new URL(page.url()).searchParams.get('draft_job')!;
  const generated=await worker('tests/fixtures/run_browser_research.py',run,project,job);
  expect(generated.status).toBe('completed');expect(generated.grounding_status).toBe('grounded');
  await page.getByRole('button',{name:'Refresh job',exact:true}).click();
  const editor=page.getByRole('region',{name:'Open draft',exact:true});
  await expect(editor.getByRole('textbox',{name:'Body',exact:true})).toContainText('Industrial sensors');
  const savedBody='Synthetic unsent outreach draft. Industrial sensors. No message was sent.';
  await editor.getByRole('textbox',{name:'Body',exact:true}).fill(savedBody);
  await editor.getByRole('button',{name:'Save revision',exact:true}).click();
  await expect(editor).not.toHaveAttribute('data-live-unsaved','true');
  await reloadSignedIn(page);await expect(editor.getByRole('textbox',{name:'Body',exact:true})).toHaveValue(savedBody);
  const persisted=await request.get(`${api}/v1/workspaces/${workspace}/drafts/${generated.draft_id}`,{headers});
  expect(persisted.status()).toBe(200);const draft:Draft=(await persisted.json()).data;
  expect(draft.body).toBe(savedBody);expect(draft.revision_number).toBe(2);expect(draft.delivery_enabled).toBe(false);
  await test.info().attach('isolated-core-result',{body:JSON.stringify({fixture_only:true,real_auth:false,real_provider:false,real_messages:0,workspace,project,run,job,draft:generated.draft_id,research}),contentType:'application/json'});
  await reviewerContext.close();
});
