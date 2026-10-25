// Run from the repository root with no other frontend server on port5195.
// Synthetic browser-local state only; every API/provider request is refused.
import {createServer} from 'vite';
import {chromium} from '@playwright/test';
import {writeFile,readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {loadModule} from '../tests/ts-loader.mjs';
for(const key of Object.keys(process.env))if(key.startsWith('BUYEROS_')||key.startsWith('MARKETING_'))delete process.env[key];
Object.assign(process.env,{BUYEROS_API_BASE_URL:'',BUYEROS_AUTH_PROVIDER:'auth0',BUYEROS_NEON_AUTH_ROUTE_ENABLED:'0',XDG_CONFIG_HOME:process.cwd()+'/.sites-runtime/xdg'});
const {seed,base}=await loadModule('data/demo/fixtures.ts');
const {siteCopy}=await loadModule('features/marketing/content.ts');
const server=await createServer({server:{host:'127.0.0.1',port:5195,strictPort:true},logLevel:'warn'});
let browser;const receipts=[],unexpected=[];
try{
 await server.listen();browser=await chromium.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox']});
 for(const locale of ['zh-HK','en']){
  const context=await browser.newContext({viewport:{width:1520,height:1000},reducedMotion:'reduce'});
  await context.route('**/*',route=>{const u=new URL(route.request().url());if(u.hostname!=='127.0.0.1'||/^\/(api|v1)\//.test(u.pathname)){unexpected.push(u.origin+u.pathname);return route.abort();}return route.continue();});
  const store=JSON.parse(JSON.stringify(seed()).replaceAll('Willy Lai','Example Reviewer').replace(/https?:[^"\s]+/g,'https://source.example.test'));store.locale=locale;
  store.drafts=[{...base,id:'synthetic-public-draft',buyerId:store.companies[0].id,recipient:'buyer@sample.example',subject:siteCopy[locale].sample.draftSubject,body:siteCopy[locale].sample.draftBody,revision:1,status:'Draft',policyReviewed:false,sender:'Example Sender',delivery:'Not connected',followup:'None',objective:'Synthetic demonstration',tone:'Professional',language:locale==='en'?'English':'Traditional Chinese',valueProposition:'Industrial sensors'}];
  await context.addInitScript(({store,locale})=>{localStorage.setItem('buyeros-demo-v1',JSON.stringify(store));localStorage.setItem('buyeros-prefs-v1',JSON.stringify({locale}));},{store,locale});
  const page=await context.newPage();
  for(const [name,path]of[['overview','/app'],['criteria','/app/discover/new'],['drafts','/app/outreach']]){
   await page.goto('http://127.0.0.1:5195'+path);await page.locator('[data-demo-ready=true]').waitFor();await page.waitForFunction(locale=>document.documentElement.lang===locale,locale);await page.evaluate(()=>document.fonts.ready);
   const file=`public/marketing/product-${name}-${locale}.png`;await page.screenshot({path:file,clip:{x:224,y:105,width:1280,height:820},animations:'disabled'});receipts.push({file,path,locale,mode:'demo',synthetic:true,sha256:createHash('sha256').update(await readFile(file)).digest('hex')});
  }
  await context.close();
  const og=await browser.newPage({viewport:{width:1200,height:630}});const copy=siteCopy[locale];
  await og.setContent(`<html lang="${locale}"><style>*{box-sizing:border-box}body{margin:0;width:1200px;height:630px;background:#f6f8fa;color:#0b1f2a;font-family:system-ui,sans-serif;padding:58px 64px}header{display:flex;justify-content:space-between;font-size:26px;font-weight:750;letter-spacing:-1px}small{font-size:14px;font-weight:500;color:#0e766e;letter-spacing:1px}h1{font-size:64px;line-height:1.2;letter-spacing:-3px;max-width:940px;margin:65px 0 24px;text-wrap:balance}p{font-size:22px;line-height:1.6;max-width:980px;color:#435969}footer{display:flex;gap:14px;margin-top:36px}footer span{border:1px solid #bcd2c7;border-radius:5px;padding:8px 15px;color:#0e766e;font-size:16px;background:#edf4ef}</style><header>BuyerOS<small>${copy.pages.home.eyebrow}</small></header><h1>${copy.home.headline}</h1><p>${copy.home.intro}</p><footer>${copy.home.proof.slice(0,3).map(x=>'<span>'+x.title+'</span>').join('')}</footer></html>`);await og.evaluate(()=>document.fonts.ready);const file=`public/marketing/og-${locale}.png`;await og.screenshot({path:file});await og.close();receipts.push({file,locale,kind:'original HTML typographic graphic',sha256:createHash('sha256').update(await readFile(file)).digest('hex')});
 }
 if(unexpected.length)throw Error('Unexpected network paths: '+JSON.stringify(unexpected));
 await writeFile('outputs/marketing-full/capture-receipts.json',JSON.stringify({synthetic:true,realProviderCalls:0,receipts},null,2)+'\n');console.log('Captured six synthetic product screens and two original OG graphics.');
}finally{await browser?.close();await server.close();}
