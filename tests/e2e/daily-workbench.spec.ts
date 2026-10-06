import {expect,test} from '@playwright/test';
import {signInWorkbench as signIn,resetWorkbenchFixtureRateWindows,workspace,project} from './fixtures/workbench-auth';
const browserApiOrigin=process.env.BUYEROS_E2E_FRONTEND==='vercel-built'?'http://localhost:5173':'http://127.0.0.1:8000';

test.beforeEach(async()=>{await resetWorkbenchFixtureRateWindows();});

test('T27 usage, queue filters and manual outcome history survive refresh in both locales',async({page,request})=>{
  test.setTimeout(240_000);await signIn(page);
  await expect(page.locator('header select')).toBeEnabled({timeout:30_000});
  await page.locator('header select').selectOption('en');
  await expect(page.locator('html')).toHaveAttribute('lang','en');
  const usage=page.getByRole('region',{name:'Usage'});
  await expect(usage).toContainText('New accepted companies');
  await expect(usage).toContainText('1');
  await expect(page.getByRole('region',{name:'Daily work queue'})).toBeVisible();
  await expect(page.getByText('Unknown provider acceptance')).toBeVisible();
  await page.getByRole('region',{name:'Daily work queue'}).getByRole('button',{name:'Open'}).first().click();
  await expect.poll(()=>new URL(page.url()).searchParams.get('review'),{timeout:30_000}).toBe('awaiting_review');
  await expect(page.getByText('23 in snapshot')).toBeVisible({timeout:30_000});
  await page.getByRole('combobox',{name:'Review filter'}).selectOption('');
  await expect(page.getByText('24 in snapshot')).toBeVisible({timeout:30_000});
  await page.getByRole('button',{name:'Log outcome'}).first().click();
  await page.getByRole('textbox',{name:'Outcome notes'}).fill('Fixture manual reply reported by the operator');
  await page.getByRole('button',{name:'Record manual outcome'}).click();
  const outcomes=page.getByRole('region',{name:'Manual outcomes'});
  await expect(outcomes).toContainText('1 outcome events');
  await expect(outcomes).toContainText('Fixture manual reply reported by the operator');
  await outcomes.getByRole('button',{name:'Correct event'}).click();
  await outcomes.getByRole('combobox',{name:'Outcome stage'}).selectOption('meeting');
  await outcomes.getByRole('textbox',{name:'Outcome notes'}).fill('Fixture meeting confirmed manually');
  await outcomes.getByRole('textbox',{name:'Correction reason'}).fill('Corrected after staff review');
  await outcomes.getByRole('button',{name:'Append correction'}).click();
  await expect(outcomes).toContainText('2 outcome events');
  await expect(outcomes).toContainText('Corrected after staff review');
  const denied=await request.post(`http://127.0.0.1:8000/v1/workspaces/${workspace}/projects/${project}/outcomes`,{
    headers:{Authorization:'Bearer fixture-viewer','Idempotency-Key':'t27-viewer-browser'},
    data:{buyer_id:'e2000000-0000-4000-8000-000000000001',stage:'reply',source:'manual',occurred_at:new Date().toISOString(),notes:'Viewer cannot write'}});
  expect(denied.status()).toBe(403);
  await page.reload();
  await page.getByRole('button',{name:'Sign in'}).click();
  await expect(page.getByRole('region',{name:'Manual outcomes'})).toContainText('2 outcome events');
  await page.screenshot({path:'test-results/t27-workbench-en-fixture.png',fullPage:true});
  await page.locator('header select').selectOption('zh-HK');
  await page.setViewportSize({width:390,height:844});
  await expect(page.getByRole('region',{name:'人手記錄成果'})).toContainText('2 項成果紀錄');
  await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
  await page.screenshot({path:'test-results/t27-workbench-zh-mobile-fixture.png',fullPage:true});
  const usagePath=`${browserApiOrigin}/v1/workspaces/*/projects/*/usage*`;
  await page.route(usagePath,route=>route.fulfill({status:503,contentType:'application/json',
    headers:{'Access-Control-Allow-Origin':'http://localhost:5173'},
    body:JSON.stringify({code:'METRIC_UNAVAILABLE',message:'fixture outage',request_id:'11111111-1111-4111-8111-111111111111',retryable:true})}));
  const zhUsage=page.getByRole('region',{name:'使用量'});
  await zhUsage.getByRole('button',{name:'更新使用量'}).click();
  await expect(zhUsage.getByRole('alert')).toContainText('Request ID: 11111111-1111-4111-8111-111111111111');
  await expect(zhUsage).not.toContainText('新接納公司');
  await expect(page.getByRole('region',{name:'人手記錄成果'})).toContainText('2 項成果紀錄');
  await page.unroute(usagePath);
  await zhUsage.getByRole('button',{name:'更新使用量'}).click();
  await expect(zhUsage).toContainText('新接納公司');
});

for (const locale of ['en','zh-HK'] as const) {
  test(`T29 API-backed workbench reflows across routes and widths in ${locale}`,async({page})=>{
    test.setTimeout(300_000);
    await signIn(page);
    await expect(page.locator('header select')).toBeEnabled({timeout:30_000});
    await page.locator('header select').selectOption(locale);
    await expect(page.locator('html')).toHaveAttribute('lang',locale);
    await page.emulateMedia({reducedMotion:'reduce'});
    const nav=page.getByRole('navigation',{name:'BuyerOS sections'});
    const cdp=await page.context().newCDPSession(page);
    const sections=[
      {index:0,path:'/app'},
      {index:2,path:'/app/discover'},
      {index:3,path:'/app/results'},
      {index:5,path:'/app/outreach'},
      {index:6,path:'/app/settings'},
      {index:7,path:'/app/operations'},
    ];
    for(const section of sections){
      await nav.getByRole('button').nth(section.index).click();
      await expect.poll(()=>new URL(page.url()).pathname).toBe(section.path);
      await expect(page.locator('main')).toBeVisible();
      for(const width of [320,390,720,768,1280,1440]){
        await page.setViewportSize({width,height:900});
        if(width===390||width===1280){
          const tree=await cdp.send('Accessibility.getFullAXTree');
          const unnamed=tree.nodes.filter((node:{ignored?:boolean;role?:{value?:string};name?:{value?:string}})=>
            !node.ignored&&['button','link','textbox','combobox','checkbox','radio'].includes(node.role?.value??'')
            &&!(node.name?.value??'').trim());
          expect(unnamed.map((node:{nodeId:string;role?:{value?:string}})=>
            `${node.role?.value}:${node.nodeId}`),
          `${locale} ${section.path} at ${width}px has unnamed interactive controls`).toEqual([]);
        }
        try {
          await expect.poll(()=>page.evaluate(() =>
            Math.max(document.documentElement.scrollWidth,document.body.scrollWidth)
            - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
        } catch {
          const offenders=await page.evaluate(()=>Array.from(document.querySelectorAll('body *'))
            .map(element=>({element,box:element.getBoundingClientRect()}))
            .filter(({box})=>box.width>0&&box.right>document.documentElement.clientWidth+1)
            .slice(0,12).map(({element,box})=>({
              tag:element.tagName,className:element.className,
              text:(element.textContent||'').trim().slice(0,70),
              left:Math.round(box.left),right:Math.round(box.right),width:Math.round(box.width),
            })));
          throw new Error(`${locale} ${section.path} at ${width}px overflows: ${JSON.stringify(offenders)}`);
        }
        if(section.path==='/app/operations'&&(width===390||width===1440)){
          await expect(page.locator('section[aria-label] [role="region"]').first())
            .not.toContainText(/Loading|載入中/,{timeout:30_000});
          await page.screenshot({path:`test-results/t29-live-fixture-${locale}-${width}.png`,fullPage:true});
        }
      }
    }
    await expect(page.locator('html')).toHaveAttribute('lang',locale);
  });
}

test('T29 manual locale remains usable while preference loads and saves with its current version',async({page})=>{
  test.setTimeout(120_000);
  let releasePreference:()=>void=()=>{},preferenceReads=0;
  const preferenceWrites:string[]=[];
  const heldPreference=new Promise<void>(resolve=>{releasePreference=resolve;});
  const preferencePath=`/v1/workspaces/${workspace}/preferences`;
  const isPreference=(response:import('@playwright/test').Response)=>new URL(response.url()).pathname===preferencePath;
  await page.route(`${browserApiOrigin}${preferencePath}`,async route=>{
    if(route.request().method()==='GET'){preferenceReads++;await heldPreference;}
    else if(route.request().method()==='PATCH')preferenceWrites.push(route.request().headers()['if-match']);
    await route.continue();
  });
  const loadedPreference=page.waitForResponse(response=>isPreference(response)&&response.request().method()==='GET'&&response.status()===200,{timeout:30_000});
  try{
    await signIn(page,false);
    await expect(page.getByRole('combobox',{name:/^(Workspace|工作區)$/})).toHaveValue(workspace,{timeout:30_000});
    await expect(page.getByRole('combobox',{name:/^(Project|專案)$/})).toHaveValue(project,{timeout:30_000});
    await expect.poll(()=>preferenceReads,{timeout:30_000}).toBeGreaterThan(0);
    await expect(page.locator('header select')).toBeEnabled();
    await page.locator('header select').selectOption('zh-HK');
    await expect(page.locator('html')).toHaveAttribute('lang','zh-HK');
    expect(preferenceWrites).toEqual([]);
  }finally{
    releasePreference();
  }
  const loadedResponse=await loadedPreference;
  expect(await loadedResponse.finished()).toBeNull();
  const loaded=(await loadedResponse.json()).data;
  expect(Number.isInteger(loaded.version)).toBe(true);
  await expect(page.locator('header select')).toHaveValue('zh-HK');
  await expect(page.locator('html')).toHaveAttribute('lang','zh-HK');
  const reset=page.waitForResponse(response=>isPreference(response)&&response.request().method()==='PATCH',{timeout:30_000});
  await page.locator('header select').selectOption('en');
  const resetResponse=await reset;
  expect(resetResponse.status()).toBe(200);
  expect(await resetResponse.request().headerValue('if-match')).toBe(`"${loaded.version}"`);
  const resetVersion=(await resetResponse.json()).data.version;
  await expect(page.locator('header select')).toBeEnabled({timeout:30_000});
  const saved=page.waitForResponse(response=>isPreference(response)&&response.request().method()==='PATCH',{timeout:30_000});
  await page.locator('header select').selectOption('zh-HK');
  const savedResponse=await saved;
  expect(savedResponse.status()).toBe(200);
  expect(await savedResponse.request().headerValue('if-match')).toBe(`"${resetVersion}"`);
  const savedVersion=(await savedResponse.json()).data.version;
  expect(preferenceWrites).toEqual([`"${loaded.version}"`,`"${resetVersion}"`]);
  await expect(page.locator('html')).toHaveAttribute('lang','zh-HK');
  const restoredPreference=page.waitForResponse(response=>isPreference(response)&&response.request().method()==='GET'&&response.status()===200,{timeout:30_000});
  await page.reload();
  await page.getByRole('button',{name:/^(Sign in|登入)$/}).click();
  await expect(page.getByRole('combobox',{name:/^(Project|專案)$/}))
    .toHaveValue(project,{timeout:30_000});
  const restored=(await (await restoredPreference).json()).data;
  expect(restored.locale).toBe('zh-HK');
  expect(restored.version).toBe(savedVersion);
  await expect(page.locator('header select')).toHaveValue('zh-HK',{timeout:30_000});
  await expect(page.locator('html')).toHaveAttribute('lang','zh-HK');
  await page.screenshot({path:'test-results/pr11-ci-followup-20261006/locale-restored-zh.png',fullPage:true});
});

test('T29 operations resolves a failed profile lookup without a permanent spinner',async({page})=>{
  test.setTimeout(120_000);
  await signIn(page);
  await expect(page.locator('header select')).toBeEnabled({timeout:30_000});
  await page.locator('header select').selectOption('en');
  await expect(page.locator('html')).toHaveAttribute('lang','en');
  const requestId='22222222-2222-4222-8222-222222222222';
  await page.route(`${browserApiOrigin}/v1/workspaces/${workspace}/projects/${project}`,route=>{
    if(route.request().method()!=='GET')return route.continue();
    return route.fulfill({status:503,contentType:'application/json',
      headers:{'Access-Control-Allow-Origin':'http://localhost:5173'},
      body:JSON.stringify({code:'FIXTURE_OUTAGE',message:'fixture project read failed',
        request_id:requestId,retryable:true})});
  });
  await page.route(`${browserApiOrigin}/v1/workspaces/${workspace}/jobs**`,route=>{
    const url=new URL(route.request().url());
    if(url.searchParams.get('status')!=='failed')return route.continue();
    return route.fulfill({status:503,contentType:'application/json',
      headers:{'Access-Control-Allow-Origin':'http://localhost:5173'},
      body:JSON.stringify({code:'FIXTURE_OUTAGE',message:'fixture jobs read failed',
        request_id:requestId,retryable:true})});
  });
  await page.getByRole('navigation',{name:'BuyerOS sections'}).getByRole('button',{name:'Operations'}).click();
  const workQueue=page.getByRole('region',{name:'Work queue'});
  await expect(workQueue).toContainText('Profile approval: Unavailable',{timeout:30_000});
  await expect(workQueue).toContainText('Failed jobs: Unavailable',{timeout:30_000});
  await expect(workQueue).not.toContainText('Loading');
  await expect(page.getByRole('alert')).toContainText(`Request ID: ${requestId}`);
});


test('T29 live operations and results text meets measured AA contrast in both locales',async({page})=>{
  test.setTimeout(120_000);
  await signIn(page);
  await expect(page.locator('header select')).toBeEnabled({timeout:30_000});
  for(const locale of ['en','zh-HK'] as const){
    await page.locator('header select').selectOption(locale);
    await expect(page.locator('html')).toHaveAttribute('lang',locale);
    const nav=page.getByRole('navigation',{name:'BuyerOS sections'});
    for(const {index,path} of [{index:0,path:'/app'},{index:3,path:'/app/results'},{index:7,path:'/app/operations'}]){
      await nav.getByRole('button').nth(index).click();
      await expect.poll(()=>new URL(page.url()).pathname).toBe(path);
      const routeRegion=index===0?(locale==='en'?'Daily work queue':'每日工作佇列')
        :index===3?(locale==='en'?'Usage':'使用量'):(locale==='en'?'Work queue':'工作佇列');
      const region=page.getByRole('region',{name:routeRegion});
      await expect(region).toBeVisible({timeout:30_000});
      if(index===3)await expect(region).not.toContainText(/Loading usage|載入使用量/,{timeout:30_000});
      if(index===7)await expect(region).not.toContainText(/Loading|載入中/,{timeout:30_000});
      const failures=await page.evaluate(()=>{
        type Color={r:number;g:number;b:number;a:number};
        const parse=(value:string):Color|null=>{
          const match=value.match(/^rgba?\(([^)]+)\)$/);
          if(!match)return null;
          const values=match[1].split(',').map(part=>Number.parseFloat(part.trim()));
          return values.length>=3?{r:values[0],g:values[1],b:values[2],a:values[3]??1}:null;
        };
        const over=(top:Color,bottom:Color):Color=>({
          r:top.r*top.a+bottom.r*(1-top.a),
          g:top.g*top.a+bottom.g*(1-top.a),
          b:top.b*top.a+bottom.b*(1-top.a),a:1,
        });
        const background=(element:Element):Color=>{
          const chain:Element[]=[];
          for(let node:Element|null=element;node;node=node.parentElement)chain.push(node);
          let color:Color={r:255,g:255,b:255,a:1};
          for(const node of chain.reverse()){
            const layer=parse(getComputedStyle(node).backgroundColor);
            if(layer&&layer.a>0)color=over(layer,color);
          }
          return color;
        };
        const luminance=(color:Color)=>{
          const channel=(value:number)=>{const x=value/255;return x<=0.04045?x/12.92:((x+0.055)/1.055)**2.4;};
          return 0.2126*channel(color.r)+0.7152*channel(color.g)+0.0722*channel(color.b);
        };
        const root=document.querySelector('main');if(!root)return [{text:'main missing',ratio:0}];
        const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);
        const bad:{text:string;ratio:number;required:number;color:string;background:string}[]=[];
        while(walker.nextNode()){
          const node=walker.currentNode,element=node.parentElement,text=node.textContent?.trim();
          if(!element||!text||element.closest('[hidden],[aria-hidden="true"],script,style,:disabled'))continue;
          const style=getComputedStyle(element),rect=element.getBoundingClientRect();
          if(style.display==='none'||style.visibility!=='visible'||Number(style.opacity)===0||rect.width===0||rect.height===0)continue;
          const foreground=parse(style.color),back=background(element);if(!foreground)continue;
          const fg=over(foreground,back),light=Math.max(luminance(fg),luminance(back));
          const dark=Math.min(luminance(fg),luminance(back)),ratio=(light+0.05)/(dark+0.05);
          const size=Number.parseFloat(style.fontSize),weight=Number.parseInt(style.fontWeight,10);
          const required=size>=24||(size>=18.67&&weight>=700)?3:4.5;
          if(ratio+0.01<required)bad.push({text:text.slice(0,50),ratio:Number(ratio.toFixed(2)),required,
            color:style.color,background:`${back.r.toFixed(0)},${back.g.toFixed(0)},${back.b.toFixed(0)}`});
        }
        return bad.slice(0,30);
      });
      expect(failures,`${locale} route index ${index} text contrast`).toEqual([]);
    }
  }
});


test('T29 scope list timeout offers a bounded retry with current identity',async({page})=>{
  test.setTimeout(90_000);
  let releaseFirst:()=>void=()=>{};
  const held=new Promise<void>(resolve=>{releaseFirst=resolve;});
  let first=true;
  await page.route(`${browserApiOrigin}/v1/workspaces?**`,async route=>{
    if(first){first=false;await held;}
    try{await route.continue();}catch{ /* The first request may have timed out. */ }
  });
  try{
    await signIn(page,false);
    const picker=page.getByRole('region',{name:/^(Workspace selection|工作區選擇)$/});
    await expect(picker.getByRole('alert')).toBeVisible({timeout:20_000});
    await expect(page.getByRole('button',{name:'Retry loading workspaces'})).toBeEnabled();
  }finally{
    releaseFirst();
  }
  await page.getByRole('button',{name:'Retry loading workspaces'}).click();
  await expect(page.getByRole('combobox',{name:/^(Workspace|工作區)$/})).toHaveValue(workspace,{timeout:30_000});
  await expect(page.getByRole('combobox',{name:/^(Project|專案)$/})).toHaveValue(project,{timeout:30_000});
});


test('T29 live form controls have a visible three-to-one boundary in both locales',async({page})=>{
  test.setTimeout(120_000);
  await signIn(page);
  await expect(page.locator('header select')).toBeEnabled({timeout:30_000});
  for(const locale of ['en','zh-HK'] as const){
    await page.locator('header select').selectOption(locale);
    await expect(page.locator('html')).toHaveAttribute('lang',locale);
    const nav=page.getByRole('navigation',{name:'BuyerOS sections'});
    for(const {index,path} of [{index:3,path:'/app/results'},{index:5,path:'/app/outreach'},
      {index:6,path:'/app/settings'},{index:7,path:'/app/operations'}]){
      await nav.getByRole('button').nth(index).click();
      await expect.poll(()=>new URL(page.url()).pathname).toBe(path);
      const result=await page.evaluate(()=>{
        type Color={r:number;g:number;b:number;a:number};
        const parse=(value:string):Color|null=>{
          const match=value.match(/^rgba?\(([^)]+)\)$/);
          if(!match)return null;
          const values=match[1].split(',').map(part=>Number.parseFloat(part.trim()));
          return values.length>=3?{r:values[0],g:values[1],b:values[2],a:values[3]??1}:null;
        };
        const over=(top:Color,bottom:Color):Color=>({r:top.r*top.a+bottom.r*(1-top.a),
          g:top.g*top.a+bottom.g*(1-top.a),b:top.b*top.a+bottom.b*(1-top.a),a:1});
        const background=(element:Element|null):Color=>{
          const chain:Element[]=[];
          for(let node=element;node;node=node.parentElement)chain.push(node);
          let color:Color={r:255,g:255,b:255,a:1};
          for(const node of chain.reverse()){
            const layer=parse(getComputedStyle(node).backgroundColor);
            if(layer&&layer.a>0)color=over(layer,color);
          }
          return color;
        };
        const luminance=(color:Color)=>{
          const channel=(value:number)=>{const x=value/255;return x<=0.04045?x/12.92:((x+0.055)/1.055)**2.4;};
          return 0.2126*channel(color.r)+0.7152*channel(color.g)+0.0722*channel(color.b);
        };
        const contrast=(a:Color,b:Color)=>{const light=Math.max(luminance(a),luminance(b));
          return (light+0.05)/(Math.min(luminance(a),luminance(b))+0.05);};
        const root=document.querySelector('main');
        if(!root)return {checked:0,bad:[{name:'main missing',ratio:0}]};
        const controls=root.querySelectorAll('input:not([type=checkbox]):not([type=radio]):not([type=hidden]),select,textarea');
        const bad:{name:string;ratio:number}[]=[];let checked=0;
        for(const element of controls){
          const control=element;
          const style=getComputedStyle(control),rect=control.getBoundingClientRect();
          if(control.matches(':disabled')||style.display==='none'||style.visibility!=='visible'||Number(style.opacity)===0
            ||rect.width===0||rect.height===0)continue;
          checked++;const outside=background(control.parentElement);
          const fill=background(control);
          let ratio=contrast(fill,outside);
          for(const side of ['Top','Right','Bottom','Left'] as const){
            if(Number.parseFloat(style[`border${side}Width`])<=0||style[`border${side}Style`]==='none')continue;
            const border=parse(style[`border${side}Color`]);
            if(border)ratio=Math.max(ratio,contrast(over(border,outside),outside));
          }
          if(ratio+0.01<3)bad.push({name:control.getAttribute('aria-label')||control.id||control.outerHTML.slice(0,90),
            ratio:Number(ratio.toFixed(2))});
        }
        return {checked,bad:bad.slice(0,30)};
      });
      expect(result.checked,`${locale} ${path} should expose form controls`).toBeGreaterThan(0);
      expect(result.bad,`${locale} ${path} low-contrast control boundaries`).toEqual([]);
    }
  }
});
