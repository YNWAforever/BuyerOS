import {expect,type Page} from '@playwright/test';
import {createNeonFixtureProtocol,fixtureOrigin} from './neon-fixture-protocol.mjs';
import {createJourneyInput} from './journey-input';

type Options={subject?:string;accessToken?:string;apiOrigin?:string;origin?:string;tokenSubject?:string;expiresInSeconds?:number};
const installed=new WeakMap<Page,Awaited<ReturnType<typeof createFixture>>>();
async function createFixture(page:Page,options:Options){
  const apiOrigin=options.apiOrigin??'http://127.0.0.1:8000';
  const origin=options.origin??fixtureOrigin;
  if(!['http://127.0.0.1:8000','https://api.buyeros.test'].includes(apiOrigin))throw Error('owned fictional API origin required');
  const fixture=createNeonFixtureProtocol({...options,subject:options.subject??options.accessToken??'fixture-reviewer'});
  await page.route(`${origin}/api/auth/**`,async route=>{
    const request=route.request(),response=await fixture.respond(new Request(request.url(),{method:request.method(),headers:request.headers(),...(['GET','HEAD'].includes(request.method())?{}:{body:request.postData()??'{}'})}));
    await route.fulfill({status:response.status,headers:Object.fromEntries(response.headers),body:await response.text()});
  });
  // Translate only this fixture's exact token on the two owned API paths. Doing
  // this at the browser fetch boundary preserves later route.fetch fault tests.
  // No app source or server verifier accepts this unsigned synthetic JWT.
  await page.addInitScript(({token,bearer,origins})=>{
    const original=window.fetch.bind(window);
    window.fetch=(input,init)=>{
      const url=new URL(input instanceof Request?input.url:String(input),location.href);
      if(origins.includes(url.origin)&&url.pathname.startsWith('/v1/')){
        const headers=new Headers(init?.headers??(input instanceof Request?input.headers:undefined));
        if(headers.get('authorization')===`Bearer ${token}`){headers.set('authorization',`Bearer ${bearer}`);init={...init,headers};}
      }
      return original(input,init);
    };
  },{token:fixture.token,bearer:options.accessToken??options.subject??'fixture-reviewer',origins:[origin,apiOrigin]});
  return {async signIn(input=createJourneyInput()){
    await input.install(page);
    const signIn=page.getByRole('button',{name:/^(Sign in|登入)$/,exact:true});
    const signOut=page.getByRole('button',{name:/^(Sign out|登出)$/,exact:true});
    await expect(signIn.or(signOut)).toBeVisible({timeout:30_000});
    if(await signOut.isVisible())return;
    await input.activate(signIn);
    await expect(page).toHaveURL(/\/auth\/sign-in\?state=/);
    await input.fill(page.locator('#sign-in-email'),fixture.email);
    await input.fill(page.locator('#sign-in-password'),fixture.password);
    await input.activate(page.getByRole('button',{name:/^(Sign in with email|使用電郵登入)$/,exact:true}));
  }};
}

/** Synthetic same-origin cookie endpoints, isolated per page and fixture actor. */
export async function installNeonFixture(page:Page,options:Options={}){
  // A second journey on the same page keeps its real synthetic cookie session.
  const existing=installed.get(page);if(existing)return existing;
  const fixture=await createFixture(page,options);installed.set(page,fixture);return fixture;
}
