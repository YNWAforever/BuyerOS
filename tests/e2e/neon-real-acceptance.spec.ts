import {test,expect,type Page} from '@playwright/test';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
interface Target {schema:string;origin:string;rollback_origin:string;source_sha:string;rollback_source_sha:string;
  account_sha256:string;workspace_id:string;project_id:string;authorization_reference:string;}
function target():Target {
  const path=process.env.BUYEROS_NEON_REAL_TARGET_FILE;
  if(!path)throw new Error('BLOCKED: reviewed real Neon target/account/rollback packet missing');
  const value=JSON.parse(readFileSync(path,'utf8')) as Target;
  for(const key of ['origin','rollback_origin'] as const){
    const url=new URL(value[key]);
    if(url.protocol!=='https:'||url.username||url.password||url.pathname!=='/'||url.search||url.hash
      ||url.origin!==process.env[key==='origin'?'BUYEROS_NEON_REAL_ALLOWED_ORIGIN':'BUYEROS_NEON_REAL_ALLOWED_ROLLBACK_ORIGIN'])
      throw new Error('BLOCKED: exact isolated origin allowlist mismatch');
  }
  const email=process.env.BUYEROS_NEON_REAL_EMAIL,password=process.env.BUYEROS_NEON_REAL_PASSWORD;
  if(value.schema!=='buyeros.real-neon-target.v1'||!email||!password||!value.authorization_reference
    ||!/^([0-9a-f]{40})$/.test(value.source_sha)||!/^([0-9a-f]{40})$/.test(value.rollback_source_sha)
    ||createHash('sha256').update(email).digest('hex')!==value.account_sha256
    ||![value.workspace_id,value.project_id].every(id=>/^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$/i.test(id)))
    throw new Error('BLOCKED: bounded existing-account target packet is incomplete');
  return value;
}
async function signIn(page:Page,origin:string,packet:Target){
  await page.goto(origin+'/app');await page.getByRole('button',{name:/^(Sign in|登入)$/}).click();
  const email=page.getByRole('textbox',{name:'Email',exact:true}),password=page.getByLabel('Password',{exact:true});
  await expect(email).toBeVisible();await expect(password).toBeVisible();
  await email.fill(process.env.BUYEROS_NEON_REAL_EMAIL!);await password.fill(process.env.BUYEROS_NEON_REAL_PASSWORD!);
  await page.getByRole('button',{name:'Sign in with email',exact:true}).click();
  await expect(page.getByRole('combobox',{name:/^(Workspace|工作區)$/})).toHaveValue(packet.workspace_id);
  await expect(page.getByRole('combobox',{name:/^(Project|專案)$/})).toHaveValue(packet.project_id);
}
test('N11-05 N11-07 real existing Neon login, reload and two-tab logout without protocol mocks',async({browser})=>{
  const packet=target(),context=await browser.newContext(),page=await context.newPage();
  try {
    await signIn(page,packet.origin,packet);
    const cookies=await context.cookies();
    expect(cookies.some(cookie=>cookie.name.startsWith('__Secure-')&&cookie.httpOnly&&cookie.secure)).toBe(true);
    await page.reload();await expect(page.getByRole('combobox',{name:/^(Workspace|工作區)$/})).toHaveValue(packet.workspace_id);
    const second=await context.newPage();await second.goto(packet.origin+'/app');
    await expect(second.getByRole('combobox',{name:/^(Workspace|工作區)$/})).toHaveValue(packet.workspace_id);
    await page.getByRole('button',{name:/^(Sign out|登出)$/}).click();
    await expect(second.getByRole('button',{name:/^(Sign in|登入)$/})).toBeVisible();
  } finally {await context.close();}
});
test('N11-09 real Neon-only account retains workspace on independent compatible rollback origin',async({browser})=>{
  const packet=target();expect(packet.rollback_origin).not.toBe(packet.origin);
  const context=await browser.newContext();
  try {await signIn(await context.newPage(),packet.rollback_origin,packet);}finally{await context.close();}
});
