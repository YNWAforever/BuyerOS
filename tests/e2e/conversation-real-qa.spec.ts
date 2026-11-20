import type {Page} from '@playwright/test';
import {test,expect} from './qa-protection.fixture';
import {mkdirSync} from 'node:fs';
import {join} from 'node:path';

/**
 * Real authenticated conversation-studio QA against the deployed branch preview.
 *
 * Strictly nonbillable: this journey never approves a proposal, never dispatches a
 * paid capability and never sends outreach. It creates discussions/messages only in
 * the dedicated QA project, which is the point of this acceptance run.
 *
 * Required environment (values are never printed):
 *   BUYEROS_QA_ORIGIN, BUYEROS_QA_WORKSPACE_ID, BUYEROS_QA_PROJECT_ID,
 *   BUYEROS_QA_EXPECTED_SOURCE_SHA, BUYEROS_NEON_REAL_EMAIL, BUYEROS_NEON_REAL_PASSWORD
 */
const artifacts=join('artifacts','conversation-qa');
mkdirSync(artifacts,{recursive:true});
const uuidPattern=/^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$/i;
const shaPattern=/^[0-9a-f]{40}$/;
const mutationPath=/\/conversation-turns$|\/conversation-threads$|\/conversation-threads\/[0-9a-f-]{36}\/messages$/;

interface QaEnv{origin:string;workspace:string;project:string;expectedSourceSha:string;email:string;password:string;}
function required(name:string):string{
  const value=process.env[name];
  if(!value||!value.trim())throw new Error(`BLOCKED: ${name} missing`);
  return value.trim();
}
function qaEnv():QaEnv{
  const origin=required('BUYEROS_QA_ORIGIN');
  let parsed:URL;
  try{parsed=new URL(origin);}catch{throw new Error('BLOCKED: BUYEROS_QA_ORIGIN is not a URL');}
  if(parsed.protocol!=='https:'||parsed.pathname!=='/'||parsed.search||parsed.hash||parsed.username||parsed.password)
    throw new Error('BLOCKED: BUYEROS_QA_ORIGIN must be an https origin without path, query or credentials');
  const workspace=required('BUYEROS_QA_WORKSPACE_ID'),project=required('BUYEROS_QA_PROJECT_ID');
  if(!uuidPattern.test(workspace))throw new Error('BLOCKED: BUYEROS_QA_WORKSPACE_ID is not a UUID');
  if(!uuidPattern.test(project))throw new Error('BLOCKED: BUYEROS_QA_PROJECT_ID is not a UUID');
  const expectedSourceSha=required('BUYEROS_QA_EXPECTED_SOURCE_SHA');
  if(!shaPattern.test(expectedSourceSha))
    throw new Error('BLOCKED: BUYEROS_QA_EXPECTED_SOURCE_SHA is not a 40-character lowercase commit SHA');
  return {origin:parsed.origin,workspace,project,expectedSourceSha,
    email:required('BUYEROS_NEON_REAL_EMAIL'),password:required('BUYEROS_NEON_REAL_PASSWORD')};
}
function scoped(path:string,qa:QaEnv):string{
  const query=new URLSearchParams({workspace:qa.workspace,project:qa.project}).toString();
  return qa.origin+path+(path.includes('?')?'&':'?')+query;
}
async function shot(page:Page,name:string):Promise<void>{
  await page.screenshot({path:join(artifacts,name),fullPage:true});
}
/** Same sign-in contract as tests/e2e/neon-real-acceptance.spec.ts. */
async function signIn(page:Page,qa:QaEnv):Promise<void>{
  const navigation=await page.goto(scoped('/app',qa));
  // A protected Vercel deployment answers 401 before the app shell exists; fail
  // with the actionable cause instead of a 15-second locator timeout.
  if(navigation&&navigation.status()===401)
    throw new Error('BLOCKED: the QA candidate is protected by Vercel Authentication; set BUYEROS_QA_PROTECTION_BYPASS (Project Settings → Deployment Protection → Protection Bypass for Automation) or target an unprotected alias');
  await page.getByRole('button',{name:/^(Sign in|登入)$/}).click();
  const email=page.getByRole('textbox',{name:'Email',exact:true}),password=page.getByLabel('Password',{exact:true});
  await expect(email).toBeVisible();
  await expect(password).toBeVisible();
  await email.fill(qa.email);
  await password.fill(qa.password);
  await page.getByRole('button',{name:'Sign in with email',exact:true}).click();
  // The shell validates the requested workspace/project from the URL after sign-in.
  await expect(page.getByRole('combobox',{name:/^(Workspace|工作區)$/})).toHaveValue(qa.workspace,{timeout:60_000});
  await expect(page.getByRole('combobox',{name:/^(Project|專案)$/})).toHaveValue(qa.project);
}
async function waitForStudio(page:Page,language:'en'|'zh-HK'='en'):Promise<void>{
  const composer='Message BuyerOS',composerZh='向 BuyerOS 傳送訊息';
  try{
    await expect(page.getByRole('textbox',{name:language==='zh-HK'?composerZh:composer})).toBeVisible({timeout:60_000});
  }catch{
    throw new Error('BLOCKED: conversation studio is not visible at the QA origin; confirm NEXT_PUBLIC_CONVERSATION_HOME is enabled for this preview');
  }
}
async function expectDiscussions(page:Page,language:'en'|'zh-HK'='en'):Promise<void>{
  const discussions=page.getByRole('complementary',{name:language==='zh-HK'?'討論':'Discussions',exact:true});
  const openDrawer=!(await discussions.isVisible());
  if(openDrawer)await page.getByRole('button',{name:language==='zh-HK'?'顯示討論':'Show discussions',exact:true}).click();
  await expect(discussions).toBeVisible();
  await expect(discussions.getByRole('button',{name:language==='zh-HK'?'新增討論':'New discussion',exact:true})).toBeVisible();
  if(openDrawer){
    await discussions.getByRole('button',{name:language==='zh-HK'?'關閉討論':'Close discussions',exact:true}).click();
    await expect(discussions).toBeHidden();
  }
}
async function openStudio(page:Page,qa:QaEnv):Promise<void>{
  await page.goto(scoped('/app/discussions/new',qa));
  await waitForStudio(page);
  await expectDiscussions(page);
  await expect(page.locator('.conversation-compose-context')).toBeVisible();
}
function userMessages(page:Page){
  return page.locator('.conversation-transcript .conversation-user .conversation-part-text');
}
async function sendTurn(page:Page,text:string,expectedUserMessages:number){
  const composer=page.getByRole('textbox',{name:'Message BuyerOS'});
  await composer.fill(text);
  const [response]=await Promise.all([
    page.waitForResponse(candidate=>candidate.request().method()==='POST'&&
      mutationPath.test(new URL(candidate.url()).pathname),{timeout:90_000}),
    page.getByRole('button',{name:'Send message',exact:true}).click(),
  ]);
  expect(new URL(response.url()).pathname,'Send must use the durable turn endpoint').toMatch(/\/conversation-turns$/);
  expect(response.status(),'conversation mutation status').toBe(200);
  const {data}=await response.json();
  expect(data.thread.id,'saved discussion ID').toMatch(uuidPattern);
  expect(data.turn.id,'saved turn ID').toMatch(uuidPattern);
  await expect(userMessages(page)).toHaveCount(expectedUserMessages,{timeout:60_000});
  await expect(page.getByRole('article',{name:'BuyerOS reply'})).toHaveCount(expectedUserMessages);
  await expect(page.locator('.conversation-typing')).toHaveCount(0,{timeout:60_000});
  return {threadId:String(data.thread.id),turnId:String(data.turn.id)};
}

test('QA conversation studio: first turn, durable transcript and unsent draft',async({context})=>{
  const qa=qaEnv();
  // Reuse the extended fixture context so deployment-protection cookies and
  // configured desktop/mobile browser options apply to this real journey.
  // Pin the journey to EN so selectors never depend on the QA account's saved locale.
  await context.addInitScript(()=>{try{localStorage.setItem('buyeros.locale','en');}catch{/* Locale storage is optional. */}});
  const page=await context.newPage();
  const pageErrors:string[]=[],mutations:string[]=[];
  page.on('pageerror',error=>pageErrors.push(error.message));
  page.on('request',request=>{
    const path=new URL(request.url()).pathname;
    if(path.startsWith('/v1/')&&!['GET','HEAD','OPTIONS'].includes(request.method()))mutations.push(`${request.method()} ${path}`);
  });
  try{
    await signIn(page,qa);
    // Direct discussion links work even when the workspace home uses the legacy sales shell.
    await page.goto(scoped('/app/discussions/new',qa));
    await waitForStudio(page);
    const firstPrompt=`QA read-only project summary ${Date.now()}`;
    const first=await sendTurn(page,firstPrompt,1);
    const discussionURL=scoped(`/app/discussions/s/${first.threadId}`,qa);
    await expect(page).toHaveURL(discussionURL,{timeout:60_000});
    await expect(userMessages(page)).toHaveCount(1);
    await expect(userMessages(page).first()).toHaveText(firstPrompt);
    await shot(page,'qa-thread-first-turn.png');
    // g. Honest configuration surface, and never an auto-approved proposal.
    await expect(page.getByText('Notes only',{exact:true})).toHaveCount(0);
    if(await page.locator('.conversation-proposal').count()>0){
      await expect(page.locator('.conversation-proposal').first()).toContainText('Approval required');
      expect(await page.locator('.conversation-proposal').first().getByRole('button',{name:'Approve',exact:true}).count(),'proposal approval is explicit and never clicked').toBe(1);
      await shot(page,'qa-proposal-not-approved.png');
    }
    // d. A second turn in the same thread: both messages remain, in order, once each.
    const secondPrompt=`QA read-only follow-up ${Date.now()}`;
    const second=await sendTurn(page,secondPrompt,2);
    expect(second.threadId).toBe(first.threadId);
    expect(second.turnId).not.toBe(first.turnId);
    await expect(page).toHaveURL(discussionURL);
    let texts=await userMessages(page).allTextContents();
    expect(texts).toHaveLength(2);
    expect(texts[0]).toBe(firstPrompt);expect(texts[1]).toBe(secondPrompt);
    expect(texts.filter(text=>text===firstPrompt)).toHaveLength(1);
    expect(texts.filter(text=>text===secondPrompt)).toHaveLength(1);
    // e. Reload: durable thread, both messages restored, no pending state.
    await page.reload();
    await waitForStudio(page);
    const resumed=new URL(page.url());
    expect(resumed.pathname).toMatch(/^\/app\/discussions\/s\/[0-9a-f-]{36}$/);
    expect(resumed.searchParams.get('workspace')).toBe(qa.workspace);
    expect(resumed.searchParams.get('project')).toBe(qa.project);
    await expect(userMessages(page)).toHaveCount(2,{timeout:60_000});
    texts=await userMessages(page).allTextContents();
    expect(texts[0]).toBe(firstPrompt);expect(texts[1]).toBe(secondPrompt);
    await expect(page.locator('.conversation-typing')).toHaveCount(0);
    await expect(page.getByText('Preparing a reply…',{exact:true})).toHaveCount(0);
    await shot(page,'qa-reload-resumed.png');
    // A deep link must accept a follow-up after reload and preserve both sides in another tab.
    const thirdPrompt='Please continue the discussion after this reload.';
    const third=await sendTurn(page,thirdPrompt,3);
    expect(third.threadId).toBe(first.threadId);
    expect(new Set([first.turnId,second.turnId,third.turnId]).size).toBe(3);
    const turns=page.getByRole('article',{name:'BuyerOS reply'});
    const answerParts='.conversation-part-text, .conversation-notice';
    const savedAnswers=await turns.locator(answerParts).allTextContents();
    expect(savedAnswers.length).toBeGreaterThanOrEqual(3);
    const reopened=await context.newPage();
    await reopened.goto(discussionURL);
    await expect(userMessages(reopened)).toHaveText([firstPrompt,secondPrompt,thirdPrompt]);
    await expect(reopened.getByRole('article',{name:'BuyerOS reply'})).toHaveCount(3);
    await expect(reopened.getByRole('article',{name:'BuyerOS reply'}).locator(answerParts)).toHaveText(savedAnswers);
    await expect(reopened).toHaveURL(discussionURL);
    await reopened.close();
    // f. Unsent text survives navigation/reload and is never sent.
    const draft=`QA unsent draft ${Date.now()}`;
    await page.getByRole('textbox',{name:'Message BuyerOS'}).fill(draft);
    await page.reload();
    await waitForStudio(page);
    await expect(page.getByRole('textbox',{name:'Message BuyerOS'})).toHaveValue(draft,{timeout:60_000});
    await expect(userMessages(page).filter({hasText:draft})).toHaveCount(0);
    // Nonbillable boundary: only conversation create/append mutations are allowed.
    expect(mutations.filter(row=>/\/decisions$|\/cancel$|\/xverum\/|\/quotes?$|\/approve$|\/dispatch|\/native-actions$|\/send$/.test(row)),'no paid or approval mutation').toEqual([]);
    for(const row of mutations)expect(row).toMatch(/^POST \/v1\/.*\/conversation-turns$|^POST \/v1\/.*\/conversation-threads$|^POST \/v1\/.*\/conversation-threads\/[0-9a-f-]{36}\/messages$/);
    // h. No uncaught errors during the whole journey.
    expect(pageErrors,'uncaught page errors').toEqual([]);
    // The workflow supplies the expected source SHA; it is validated above as env readiness.
    expect(qa.expectedSourceSha).toMatch(shaPattern);
  }finally{await context.close();}
});

test('authorized model recalls the correct buyer independently in two saved discussions',async({context})=>{
  test.skip(process.env.BUYEROS_QA_MODEL_RECALL!=='true','Requires separately authorized model QA');
  test.setTimeout(360_000);
  const qa=qaEnv();
  await context.addInitScript(()=>localStorage.setItem('buyeros.locale','en'));
  const page=await context.newPage();
  await signIn(page,qa);
  const sourceName=required('BUYEROS_QA_MODEL_SOURCE_LABEL');
  const pairs=[['Alder','Birch'],['Cedar','Willow']];
  const threads:string[]=[];
  for(const [first,second] of pairs){
    await page.goto(scoped('/app/discussions/new',qa));
    const intro=`For this exercise the first buyer is ${first} and the second buyer is ${second}.`;
    const {threadId}=await sendTurn(page,intro,1);
    expect(threads).not.toContain(threadId);
    threads.push(threadId);
    const url=scoped(`/app/discussions/s/${threadId}`,qa);
    await expect(page).toHaveURL(url);
    const sourcesTab=page.getByRole('tab',{name:'Sources',exact:true});
    if(!await sourcesTab.isVisible())await page.getByRole('button',{name:'Show context panel',exact:true}).click();
    await sourcesTab.click();
    const saveSelection=page.waitForResponse(r=>r.request().method()==='PUT'&&new URL(r.url()).pathname.endsWith(`/conversation-threads/${threadId}/sources`));
    await page.getByRole('checkbox',{name:sourceName,exact:true}).check();
    expect((await saveSelection).status()).toBe(200);
    await page.reload();
    const question='Which buyer was second? Reply with only the name.';
    expect((await sendTurn(page,question,2)).threadId).toBe(threadId);
    const answer=page.getByRole('article',{name:'BuyerOS reply'}).last().locator('.conversation-part-text');
    await expect(answer).toHaveText(new RegExp(`^\\s*${second}[.!]?\\s*$`,'i'));
    const reopened=await context.newPage();
    await reopened.goto(url);
    const followUp='Which buyer was first? Reply with only the name.';
    expect((await sendTurn(reopened,followUp,3)).threadId).toBe(threadId);
    await expect(reopened.getByRole('article',{name:'BuyerOS reply'}).last().locator('.conversation-part-text')).toHaveText(new RegExp(`^\\s*${first}[.!]?\\s*$`,'i'));
    await page.reload();
    await expect(userMessages(page)).toHaveText([intro,question,followUp]);
    await expect(page.getByRole('article',{name:'BuyerOS reply'})).toHaveCount(3);
    await expect(page).toHaveURL(url);
    await reopened.close();
  }
});

test('QA conversation studio renders in EN and zh-HK',async({context})=>{
  const qa=qaEnv();
  const page=await context.newPage();
  const pageErrors:string[]=[],mutations:string[]=[];
  page.on('pageerror',error=>pageErrors.push(error.message));
  page.on('request',request=>{
    const path=new URL(request.url()).pathname;
    if(path.startsWith('/v1/')&&!['GET','HEAD','OPTIONS'].includes(request.method()))mutations.push(`${request.method()} ${path}`);
  });
  try{
    await signIn(page,qa);
    await page.evaluate(()=>localStorage.setItem('buyeros.locale','en'));
    await openStudio(page,qa);
    await expect(page.getByRole('textbox',{name:'Message BuyerOS'})).toBeVisible();
    await expectDiscussions(page);
    await expect(page.locator('html')).toHaveAttribute('lang','en');
    await page.evaluate(()=>localStorage.setItem('buyeros.locale','zh-HK'));
    await page.reload();
    await waitForStudio(page,'zh-HK');
    await expect(page.getByRole('textbox',{name:'向 BuyerOS 傳送訊息'})).toBeVisible({timeout:60_000});
    await expect(page.getByPlaceholder('詢問此專案，或選擇快速操作')).toBeVisible();
    await expectDiscussions(page,'zh-HK');
    await expect(page.locator('html')).toHaveAttribute('lang','zh-HK');
    await shot(page,'qa-zh-hk.png');
    expect(mutations,'locale switch performs no workspace mutation').toEqual([]);
    expect(pageErrors,'uncaught page errors').toEqual([]);
  }finally{await context.close();}
});
