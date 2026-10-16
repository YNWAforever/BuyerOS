import {expect,type Page,type APIRequestContext} from '@playwright/test';
import {signInWorkbench,workspace} from './workbench-auth';

export {workspace};
export const leadProject='e3100000-0000-4000-8000-000000000001';
export const leadBuyer='e3200000-0000-4000-8000-000000000001';
export const apiBase=`http://127.0.0.1:8000/v1/workspaces/${workspace}/projects/${leadProject}`;
export const entry=(path='/app/discover')=>`${path}${path.includes('?')?'&':'?'}workspace=${workspace}&project=${leadProject}`;
export const bearer={Authorization:'Bearer fixture-admin'};
export async function resetLead(request:APIRequestContext){
  const result=await request.post('http://127.0.0.1:8000/fixture/lead-reset');
  expect(result.ok(),await result.text()).toBe(true);
}
export async function signInLead(page:Page,path='/app/discover',actor:'admin'|'reviewer'|'viewer'|'access'='admin'){
  await signInWorkbench(page,false,actor,entry(path));
  await expect(page.getByRole('combobox',{name:/^(Project|專案)$/})).toHaveValue(leadProject,{timeout:30_000});
}
export async function openLeadBuyer(page:Page,index=1,tab:'Evidence'|'Contacts'='Evidence'){
  const row=page.locator('.live-buyer-row').filter({hasText:`Fixture Rice Buyer ${String(index).padStart(2,'0')}`});
  await expect(row).toBeVisible();
  await row.getByRole('button',{name:/^(Details|詳情)$/}).click();
  await page.getByRole('tab',{name:tab==='Evidence'?/^(Evidence|證據)$/:/^(Contacts|聯絡資料)$/}).click();
}
export async function fillLeadEvidence(page:Page,name='New Fixture Purchaser'){
  const panel=page.getByRole('region',{name:'Manual lead evidence'});
  await panel.getByLabel('Evidence person').selectOption('new');
  await panel.getByLabel('Person name').fill(name);
  await panel.getByLabel('Person role').fill('Rice Purchasing Manager');
  await panel.getByLabel('Evidence source title').fill('Official fixture team');
  await panel.getByLabel('Evidence source URL').fill('https://buyer1.example.test/team');
  await panel.getByLabel('Evidence excerpt').fill(`${name} is responsible for rice purchasing.`);
  await panel.getByLabel('Evidence rationale').fill('Official source identifies the current rice purchasing manager.');
}
export async function mutateCase(request:APIRequestContext,buyerId:string,version:number,nextAction:string,dueOn:string|null=null){
  const prepared=await request.post(`${apiBase}/lead-intents`,{headers:{...bearer,'Idempotency-Key':crypto.randomUUID()},
    data:{action:'case.update',buyer_id:buyerId,expected_version:version,
      payload:{priority:true,priority_reason:'Official fixture catalog',next_action:nextAction,due_on:dueOn}}});
  expect(prepared.status(),await prepared.text()).toBe(201);
  const intent=(await prepared.json()).data;
  const result=await request.post(`${apiBase}/lead-intents/${intent.id}/apply`,{
    headers:{...bearer,'Idempotency-Key':intent.submission_key,'If-Match':`"${version}"`},data:{}});
  expect(result.ok(),await result.text()).toBe(true);
}
