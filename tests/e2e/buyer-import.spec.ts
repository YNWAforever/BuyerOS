import {expect,test,type Page} from '@playwright/test';
import {installNeonFixture} from './fixtures/neon-sign-in';

const workspace='e0000000-0000-4000-8000-000000000001',project='e1000000-0000-4000-8000-000000000001';
async function signIn(page:Page,subject='fixture-access',count:number|null=24){
  const auth=await installNeonFixture(page,{accessToken:subject});
  await page.goto(`/app/discover?workspace=${workspace}&project=${project}`);
  await auth.signIn();
  await expect(page.getByRole('combobox',{name:'Project',exact:true})).toHaveValue(project);
  if(count!==null)await expect(page.getByText(`${count} in snapshot`)).toBeVisible();
}
for(const role of ['viewer','reviewer'])test(`${role} cannot open buyer import controls`,async({page})=>{
  await signIn(page,`fixture-${role}`);
  await expect(page.getByText('Import buyers from Excel or CSV',{exact:true})).toHaveCount(0);
});
test('private attachments become ready and the complete profile saves with scheduling disabled',async({page})=>{
  test.setTimeout(120_000);await signIn(page,'fixture-access',null);
  await page.getByRole('button',{name:'New project',exact:true}).click();
  await page.getByLabel('Company name',{exact:true}).fill('Private Attachment Fixture');
  await page.getByLabel('Product / service',{exact:true}).fill('Proposed rice supply');
  await page.getByLabel('Value proposition',{exact:true}).fill('Trial proposal awaiting product approval.');
  await page.getByRole('button',{name:'Continue',exact:true}).click();
  await page.getByLabel('Markets (country codes or names)',{exact:true}).fill('GB');
  await page.getByLabel('Languages (codes or names)',{exact:true}).fill('en');
  await page.getByRole('checkbox',{name:'Importer',exact:true}).check();
  await page.getByRole('button',{name:'Continue',exact:true}).click();
  await page.getByLabel('Must have',{exact:true}).fill('Has a relevant wholesale channel');
  await page.getByRole('checkbox',{name:/I confirm these buyer requirements/}).check();
  await page.getByRole('button',{name:'Continue',exact:true}).click();
  await page.getByRole('button',{name:'Save profile',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Profile version 1 · saved',exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Edit offer',exact:true}).click();
  await page.getByLabel('Offer file',{exact:true}).setInputFiles({name:'source.txt',mimeType:'text/plain',buffer:Buffer.from('Product: Proposed rice supply\nValue proposition: Trial proposal awaiting product approval.\n')});
  await page.getByRole('button',{name:'Upload document',exact:true}).click();
  await expect(page.getByText('source.txt',{exact:true})).toBeVisible();
  await expect(page.getByRole('checkbox',{name:'Use in profile',exact:true})).toBeVisible();
  await page.getByRole('checkbox',{name:'Use in profile',exact:true}).check();
  await page.getByRole('button',{name:'Continue',exact:true}).click();
  await page.getByRole('button',{name:'Continue',exact:true}).click();
  await page.getByRole('checkbox',{name:/I confirm these buyer requirements/}).check();
  await page.getByRole('button',{name:'Continue',exact:true}).click();
  await page.getByRole('button',{name:'Save profile',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Profile version 2 · saved',exact:true})).toBeVisible();
  await expect(page.getByText('Sources: —',{exact:true})).toHaveCount(0);
  await page.getByRole('button',{name:'Edit offer',exact:true}).click();
  await expect(page.getByText('source.txt',{exact:true})).toBeVisible();
  await expect(page.getByRole('checkbox',{name:'Use in profile',exact:true})).toBeChecked();
  await page.screenshot({path:'test-results/private-attachment-profile-readback.png',fullPage:true});
});
test('CSV preview, lost-response recovery, provenance and duplicate reimport use the real database',async({page})=>{
  test.setTimeout(120_000);await signIn(page);
  const paidRequests:string[]=[];page.on('request',request=>{if(request.method()==='POST'&&/\/(?:research-runs|draft-generations|send|quotes)(?:\?|$)/.test(request.url()))paidRequests.push(request.url());});
  await page.getByText('Import buyers from Excel or CSV',{exact:true}).click();
  const invalid='Company,Website\n,https://bad-import.example.test\n';
  await page.getByLabel('Buyer spreadsheet').setInputFiles({name:'invalid.csv',mimeType:'text/csv',buffer:Buffer.from(invalid)});
  await page.getByRole('button',{name:'Preview import',exact:true}).click();
  await expect(page.getByText(/Invalid rows: 1/)).toBeVisible();
  await expect(page.getByRole('button',{name:'Confirm buyer import',exact:true})).toBeDisabled();
  await page.getByRole('button',{name:'Choose another file',exact:true}).click();
  const csv='Company,Website,Source URL,Source date,Wave,Notes\nImport Fixture Alpha,https://alpha-import.example.test,https://alpha-import.example.test/about,2026-09-18,Wave 1,Source claim only\nImport Fixture Beta,https://beta-import.example.test,https://beta-import.example.test/about,2026-09-18,Wave 2,Unverified prospect\nImport Fixture Alpha,https://alpha-import.example.test,,,,duplicate\n';
  const file={name:'candidates.csv',mimeType:'text/csv',buffer:Buffer.from(csv)};
  await page.getByLabel('Buyer spreadsheet').setInputFiles(file);
  await page.getByRole('button',{name:'Preview import',exact:true}).click();
  await expect(page.getByText(/Ready to import: 2.*Duplicates skipped: 1/)).toBeVisible();
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
  await page.getByRole('checkbox',{name:'I checked these source rows and want to add the eligible candidates as unreviewed buyers.'}).check();
  // Commit the real API request once, then lose only the browser response.
  await page.route('**/buyer-imports/*/confirm',async route=>{const response=await route.fetch();expect(response.status()).toBe(200);await route.abort('connectionreset');},{times:1});
  await page.getByRole('button',{name:'Confirm buyer import',exact:true}).click();
  await expect(page.getByText(/The import result is unconfirmed/)).toBeVisible();
  const recoverableUrl=page.url();
  expect(new URL(recoverableUrl).searchParams.get('buyer_import')).toBeTruthy();
  expect(new URL(recoverableUrl).searchParams.get('buyer_import_project')).toBe(project);
  await page.getByRole('button',{name:'Check import status',exact:true}).click();
  await expect(page.getByRole('status').filter({hasText:'Imported 2 buyers; skipped 1 duplicates.'})).toBeVisible();
  await expect(page.getByText('26 in snapshot')).toBeVisible();
  let releaseRecovery!:()=>void;
  const recoveryGate=new Promise<void>(resolve=>{releaseRecovery=resolve;});
  const importId=new URL(recoverableUrl).searchParams.get('buyer_import');
  await page.route(`**/buyer-imports/${importId}`,async route=>{await recoveryGate;await route.continue();},{times:1});
  await page.reload();
  try{
    await page.getByText('Import buyers from Excel or CSV',{exact:true}).click();
    await expect(page.getByLabel('Buyer spreadsheet',{exact:true})).toBeDisabled();
    await expect(page.getByRole('button',{name:'Preview import',exact:true})).toBeDisabled();
  }finally{releaseRecovery();}
  await expect(page.getByRole('status').filter({hasText:'Imported 2 buyers; skipped 1 duplicates.'})).toBeVisible();
  await expect(page.getByText('26 in snapshot')).toBeVisible();
  // A failed reload lookup must retain the original import instead of allowing
  // another preview to overwrite the only recoverable identity.
  await page.route(`**/buyer-imports/${importId}`,route=>route.abort('connectionreset'),{times:1});
  await page.reload();
  await expect(page.getByText(/The import result is unconfirmed/)).toBeVisible();
  await expect(page.getByLabel('Buyer spreadsheet',{exact:true})).toBeDisabled();
  await expect(page.getByRole('button',{name:'Preview import',exact:true})).toBeDisabled();
  expect(new URL(page.url()).searchParams.get('buyer_import')).toBe(importId);
  await page.getByRole('button',{name:'Check import status',exact:true}).click();
  await expect(page.getByRole('status').filter({hasText:'Imported 2 buyers; skipped 1 duplicates.'})).toBeVisible();
  await page.getByLabel('Search buyers',{exact:true}).fill('Import Fixture Alpha');
  await page.getByRole('button',{name:'Apply filters',exact:true}).click();
  await expect(page.getByText('1 in snapshot')).toBeVisible();
  await page.getByRole('button',{name:'Details',exact:true}).click();
  await page.getByRole('button',{name:'Load imported source',exact:true}).click();
  await expect(page.getByText(/File: candidates.csv/)).toBeVisible();
  await page.getByText('Original spreadsheet fields',{exact:true}).click();
  await expect(page.getByText('Source claim only',{exact:true})).toBeVisible();
  await expect(page.getByText('Wave 1',{exact:true})).toBeVisible();
  await expect(page.getByText('Fit: Not assessed',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Close details',exact:true}).click();
  await page.getByRole('button',{name:'Import another file',exact:true}).click();
  await page.getByLabel('Buyer spreadsheet').setInputFiles(file);
  await page.getByRole('button',{name:'Preview import',exact:true}).click();
  await expect(page.getByText(/Ready to import: 0.*Duplicates skipped: 3/)).toBeVisible();
  await expect(page.getByRole('button',{name:'Confirm buyer import',exact:true})).toBeDisabled();
  expect(paidRequests).toEqual([]);
  await page.screenshot({path:'test-results/buyer-import-duplicate-readback.png',fullPage:true});
});
