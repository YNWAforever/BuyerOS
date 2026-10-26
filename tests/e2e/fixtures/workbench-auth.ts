import {installNeonFixture} from './neon-sign-in';
// Synthetic Neon cookie identity for the owned HTTP/PostgreSQL fixture only.
import {expect,type Page} from '@playwright/test';
import {runOwnedFixtureProcess} from './owned-fixture-process';
import {resolve} from 'node:path';
import {createJourneyInput,observeWorkspaceLocale} from './journey-input';
export const workspace='e0000000-0000-4000-8000-000000000001';
export const project='e1000000-0000-4000-8000-000000000001';

/** Isolate independent cases on the guarded owned Docker fixture, before login. */
export async function resetWorkbenchFixtureRateWindows(){
  const cwd=resolve('services/worker');
  const python=resolve(cwd,process.platform==='win32'?'.venv/Scripts/python.exe':'.venv/bin/python');
  const {stdout}=await runOwnedFixtureProcess(python,['tests/fixtures/prepare_browser_project.py','isolate-workbench'],
    {cwd,timeout:30_000});
  const initialized=JSON.parse(stdout);
  expect(initialized.fixture_initial_rate_windows_reset).toBe(true);
  expect(initialized.fixture_initial_locale_reset).toBe(true);
}

export async function signInWorkbench(page:Page,waitForProject=true,actor:'reviewer'|'access'|'viewer'|'admin'='reviewer',entry=`/app?workspace=${workspace}&project=${project}`,input=createJourneyInput()){
  await input.install(page);
  const fixture=await installNeonFixture(page,{subject:`fixture-${actor}`,accessToken:`fixture-${actor}`});
  const apiEvents:string[]=[];
  page.on('request',request=>{if(new URL(request.url()).pathname.startsWith('/v1/'))apiEvents.push(`request ${request.method()} ${request.url()}`);});
  page.on('requestfailed',request=>{if(new URL(request.url()).pathname.startsWith('/v1/'))apiEvents.push(`failed ${request.url()} ${request.failure()?.errorText}`);});
  page.on('response',response=>{if(new URL(response.url()).pathname.startsWith('/v1/'))apiEvents.push(`${response.status()} ${response.url()}`);});
  page.on('pageerror',error=>apiEvents.push(`pageerror ${error.name}: ${error.message}`));
  const localeRead=input.mode==='keyboard'&&waitForProject?observeWorkspaceLocale(page,workspace):null;
  try{
  await page.goto(entry);
  await fixture.signIn(input);
  // The cookie callback hydrates its matching token asynchronously. Negative-access
  // cases must reach the authenticated workspace read before asserting its result.
  await expect.poll(()=>apiEvents.some(event=>event.startsWith('request GET ')&&new URL(event.slice('request GET '.length)).pathname==='/v1/workspaces'),
    {timeout:30_000,message:'Fake sign-in must complete and request workspace access'}).toBe(true);
  if(waitForProject){
    try{await expect(page.getByRole('combobox',{name:/^(Project|專案)$/})).toHaveValue(project,{timeout:30_000});}
    catch(error){throw new Error(`Project selection did not settle; API events: ${apiEvents.join(' | ')}`,{cause:error});}
  }
  if(localeRead)await localeRead.settle();
  }finally{localeRead?.dispose();}
}
