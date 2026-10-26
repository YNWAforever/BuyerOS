import {expect,test,type Page} from '@playwright/test';
import {installNeonFixture} from './fixtures/neon-sign-in';

async function signIn(page:Page) {const auth=await installNeonFixture(page,{subject:'cors-actor',accessToken:'fixture-access'});await page.goto('/app');await auth.signIn();}

test('browser preflight and bearer read reach disposable API with readable request ID',async({page})=>{
  await signIn(page);
  await expect(page.getByRole('combobox',{name:'Workspace'})).toHaveValue('e0000000-0000-4000-8000-000000000001');
  await expect(page.getByText('No projects yet.')).toBeVisible();
  const result=await page.evaluate(async()=>{
    const response=await fetch('http://127.0.0.1:8000/v1/workspaces?offset=0&limit=20',{headers:{Authorization:'Bearer fixture-access','Idempotency-Key':'read-fixture-key'}});
    return {status:response.status,requestId:response.headers.get('X-Request-ID'),body:await response.json()};
  });
  expect(result.status).toBe(200);expect(result.requestId).toBeTruthy();
  expect(result.body).toMatchObject({data:{items:[{name:'E2E fixture workspace'}]}});
  await page.screenshot({path:'test-results/t06-cors-disposable-db.png',fullPage:true});
});

test('browser can read 422 envelope and correlation header across origins',async({page})=>{
  await signIn(page);
  const result=await page.evaluate(async()=>{
    const response=await fetch('http://127.0.0.1:8000/v1/workspaces?limit=0',{headers:{Authorization:'Bearer fixture-access'}});
    return {status:response.status,requestId:response.headers.get('X-Request-ID'),body:await response.json()};
  });
  expect(result.status).toBe(422);expect(result.requestId).toBeTruthy();
  expect(result.body).toMatchObject({code:'INVALID_REQUEST',request_id:result.requestId});
});

test('network failure stays an error and never reveals demo fixtures',async({page})=>{
  const auth=await installNeonFixture(page,{subject:'cors-actor',accessToken:'fixture-access'});
  await page.route('http://127.0.0.1:8000/v1/workspaces?**',route=>route.abort('failed'));
  await page.goto('/app');await auth.signIn();
  await expect(page.getByRole('alert')).toContainText('Service temporarily unavailable');
  await expect(page.getByText('HarbourSense Instruments')).toHaveCount(0);
});
