import {expect,test,type Page} from '@playwright/test';
import {signInWorkbench,workspace} from './fixtures/workbench-auth';

const project='e9100000-0000-4000-8000-000000000001';
const entry=`/app/runs?workspace=${workspace}&project=${project}`;
const envelope=(data:unknown)=>({data,request_id:'synthetic-admission-ui',data_mode:'live'});
const capabilities=(status='ready',reason_codes:string[]=[])=>({items:
  ['research','contact_enrichment','draft_generation','mailbox','crm'].map(name=>({name,
    status:name==='research'?status:'disabled',reason_codes:name==='research'?reason_codes:['CAPABILITY_DISABLED'],
    checked_at:'2026-10-14T00:00:00Z',billable:false})),offset:0,limit:5,total:5});
// Real compiled UI; only capability/unknown response transport is controlled.
// Native admission, authenticated HTTP and DB invariants have separate API tests.
async function open(page:Page){
  await signInWorkbench(page,false,'access',entry);
  await page.getByRole('combobox',{name:/^(Language|語言)$/}).selectOption('en');
  const panel=page.getByRole('region',{name:'Research runs',exact:true});
  await expect(panel.getByText('Actual runs:',{exact:false})).toBeVisible();
  await expect(panel.getByText('Approve the current buyer profile before research.',{exact:true})).toHaveCount(0);
  return panel;
}

test('paid admission stays closed while loading or paused and refresh requires an unblocked ready response',async({page})=>{
  let respond:()=>void=()=>{};const pending=new Promise<void>(resolve=>respond=resolve);
  let body=capabilities('disabled',['PAID_ADMISSION_DISABLED']),reads=0;const posts:string[]=[];
  page.on('request',r=>{if(r.method()==='POST'&&r.url().endsWith('/runs'))posts.push(r.url());});
  await page.route('**/capabilities',async route=>{reads++;if(reads===1)await pending;await route.fulfill({json:envelope(body)});});
  const panel=await open(page),start=panel.getByRole('button',{name:'Start research',exact:true});
  await expect(start).toBeDisabled();await expect(panel.getByText('Checking research availability…',{exact:true})).toBeVisible();
  respond();await expect(panel.getByText('Paid research is disabled. You can still review existing buyers and results.',{exact:true})).toBeVisible();
  await expect(start).toBeDisabled();await start.evaluate(button=>(button as HTMLButtonElement).click());expect(posts).toEqual([]);
  await page.getByRole('combobox',{name:'Language'}).selectOption('zh-HK');
  await expect(page.getByText('付費研究已停用。你仍可查看現有買家及結果。',{exact:true})).toBeVisible();
  await page.getByRole('combobox',{name:'語言'}).selectOption('en');
  body=capabilities('ready',['PROVIDER_UNSELECTED']);await panel.getByRole('button',{name:'Refresh research availability',exact:true}).click();
  await expect(panel.getByText('Research is unavailable. Ask a workspace administrator to check its configuration.',{exact:true})).toBeVisible();await expect(start).toBeDisabled();
  body=capabilities();await panel.getByRole('button',{name:'Refresh research availability',exact:true}).click();await expect(start).toBeEnabled();
  expect(reads).toBe(3);expect(posts).toEqual([]);
});

test('capability read failure closes research and can be recovered by a read-only refresh',async({page})=>{
  let fail=true;await page.route('**/capabilities',route=>route.fulfill(fail?{status:503,json:{code:'TEMPORARILY_UNAVAILABLE',message:'Fixture read unavailable',request_id:'fixture'}}:{json:envelope(capabilities())}));
  const panel=await open(page);await expect(panel.getByText('Research availability could not be confirmed. Refresh before starting research.',{exact:true})).toBeVisible();
  await expect(panel.getByRole('button',{name:'Start research',exact:true})).toBeDisabled();
  fail=false;await panel.getByRole('button',{name:'Refresh research availability',exact:true}).click();await expect(panel.getByRole('button',{name:'Start research',exact:true})).toBeEnabled();
});

for(const malformed of ['missing research','duplicate research','invalid reasons'])test(`incomplete capabilities fail closed: ${malformed}`,async({page})=>{
  const body=capabilities();
  if(malformed==='missing research')body.items=body.items.filter(item=>item.name!=='research');
  if(malformed==='duplicate research')body.items[1]={...body.items[0]};
  if(malformed==='invalid reasons')Object.assign(body.items[0],{reason_codes:null});
  await page.route('**/capabilities',route=>route.fulfill({json:envelope(body)}));const panel=await open(page);
  await expect(panel.getByText('Research availability could not be confirmed. Refresh before starting research.',{exact:true})).toBeVisible();
  await expect(panel.getByRole('button',{name:'Start research',exact:true})).toBeDisabled();
});

test('paused capability retains an unknown original research key and body across navigation',async({page})=>{
  let body=capabilities();const posted:{key:string|undefined;body:unknown}[]=[];
  await page.route('**/capabilities',route=>route.fulfill({json:envelope(body)}));
  await page.route(`**/projects/${project}/runs`,async route=>{
    if(route.request().method()!=='POST')return route.continue();
    posted.push({key:route.request().headers()['idempotency-key'],body:route.request().postDataJSON()});await route.abort('failed');
  });
  let panel=await open(page);await panel.getByLabel('Target companies').fill('35');
  await panel.getByRole('button',{name:'Start research',exact:true}).click();await expect(panel.getByRole('button',{name:'Retry same research',exact:true})).toBeEnabled();
  expect(posted).toHaveLength(1);expect(posted[0].key).toBeTruthy();
  body=capabilities('disabled',['PAID_ADMISSION_DISABLED']);await panel.getByRole('button',{name:'Refresh research availability',exact:true}).click();
  await expect(panel.getByRole('button',{name:'Retry same research',exact:true})).toBeDisabled();
  await page.getByRole('button',{name:'Overview',exact:true}).click();await page.getByRole('button',{name:'Research runs',exact:true}).click();
  panel=page.getByRole('region',{name:'Research runs',exact:true});await expect(panel.getByRole('button',{name:'Retry same research',exact:true})).toBeDisabled();
  await expect(panel.getByLabel('Target companies')).toHaveValue('35');expect(posted).toHaveLength(1);
  body=capabilities();await panel.getByRole('button',{name:'Refresh research availability',exact:true}).click();
  await panel.getByRole('button',{name:'Retry same research',exact:true}).click();await expect.poll(()=>posted.length).toBe(2);
  expect(posted[1]).toEqual(posted[0]);
});

test('late capabilities from an old project cannot open research in the new project',async({page})=>{
  let reads=0,release:()=>void=()=>{};const pending=new Promise<void>(resolve=>release=resolve);
  await page.route('**/capabilities',async route=>{reads++;const own=reads;if(own===1)await pending;
    await route.fulfill({json:envelope(own===1?capabilities():capabilities('disabled',['PAID_ADMISSION_DISABLED']))});});
  const panel=await open(page);await expect(panel.getByRole('button',{name:'Start research',exact:true})).toBeDisabled();
  await page.getByRole('combobox',{name:'Project',exact:true}).selectOption('e1000000-0000-4000-8000-000000000001');
  await expect(page.getByText('Paid research is disabled. You can still review existing buyers and results.',{exact:true})).toBeVisible();
  release();await expect(page.getByRole('button',{name:'Start research',exact:true})).toBeDisabled();
});
