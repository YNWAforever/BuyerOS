import {test,expect} from '@playwright/test';
import {signInLead,resetLead,leadProject} from './fixtures/lead-workflow';
test.beforeEach(async({request})=>resetLead(request));
for(const volume of [100,1000,10000]){
 test(`N21-PERF-02 bounded selection ${volume} companies, 100ms fixture latency`,async({page},info)=>{
  const queryBySnapshot=new Map<string,string>(),samples:number[]=[];
  let initialRequests=0,initial=true,template:Record<string,unknown>[]=[];
  let companies:Record<string,unknown>[]=[];
  const latency=()=>new Promise(resolve=>setTimeout(resolve,100));
  const matching=(query:string)=>companies.filter(row=>String(row.name).toLowerCase().includes(query.toLowerCase()));
  await page.route(`**/projects/${leadProject}/buyer-snapshots`,async route=>{
    if(initial)initialRequests++;await latency();
    const response=await route.fetch(),payload=await response.json();
    const query=String(route.request().postDataJSON().filters.q??'');
    queryBySnapshot.set(payload.data.id,query);
    const size=companies.length?matching(query).length:volume;
    payload.data.total=Math.min(size,1000);payload.data.result_limit_reached=size>1000;
    await route.fulfill({response,json:payload});
  });
  await page.route(new RegExp(`/projects/${leadProject}/buyers\\?`),async route=>{
    if(initial)initialRequests++;await latency();
    const response=await route.fetch(),payload=await response.json(),url=new URL(route.request().url());
    if(!template.length&&payload.data.items.length){
      template=payload.data.items;
      // Materialize distinct deterministic companies, not just an advertised
      // total on a 24-row response. The first 24 retain genuine fixture IDs;
      // every selected sample belongs to those already owned API records.
      companies=Array.from({length:volume},(_,index)=>({
        ...template[index%template.length],
        ...(index<template.length?{}:{
          id:`f3200000-0000-4000-8000-${String(index+1).padStart(12,'0')}`,
          company_id:`f3300000-0000-4000-8000-${String(index+1).padStart(12,'0')}`,
          normalized_domain:`scale${index+1}.example.test`,
        }),
        name:`Scale ${volume} v${volume}-s${index%10} ${String(index+1).padStart(5,'0')}`,
      })).sort((a,b)=>String(a.name).localeCompare(String(b.name)));
    }
    const query=queryBySnapshot.get(url.searchParams.get('snapshot_id')!)??'';
    const found=matching(query).slice(0,1000),offset=Number(url.searchParams.get('offset')??0);
    const limit=Math.min(Number(url.searchParams.get('limit')??24),24);
    payload.data.items=found.slice(offset,offset+limit);payload.data.total=found.length;
    await route.fulfill({response,json:payload});
  });
  await signInLead(page,'/app/outreach');
  const panel=page.getByRole('region',{name:'Lead preparations',exact:true}),picker=panel.getByLabel('Preparation company');
  await expect(picker.locator('option')).toHaveCount(25);initial=false;
  expect(companies).toHaveLength(volume);
  expect(new Set(companies.map(row=>row.id)).size).toBe(volume);
  expect(initialRequests).toBeLessThanOrEqual(2);
  for(let index=0;index<10;index++){
    const query=`v${volume}-s${index}`,target=matching(query)[0],start=performance.now();
    expect(template.some(row=>row.id===target.id)).toBe(true);
    await panel.getByRole('searchbox',{name:'Search companies',exact:true}).fill(query);
    await expect(picker.getByRole('option',{name:`${target.name} · ${target.normalized_domain}`,exact:true})).toHaveCount(1);
    await picker.selectOption(String(target.id));await expect(picker).toHaveValue(String(target.id));
    samples.push(performance.now()-start);
  }
  const ordered=[...samples].sort((a,b)=>a-b),p95=ordered[Math.ceil(ordered.length*.95)-1];
  await info.attach('fixed-latency-selection',{body:JSON.stringify({volume,materialized_companies:companies.length,
    distinct_company_ids:new Set(companies.map(row=>row.id)).size,latency_ms:100,n:samples.length,
    samples_ms:samples,p50_ms:ordered[4],p95_ms:p95,initial_requests:initialRequests,page_bound:24,snapshot_cap:1000,
    layer:'materialized deterministic browser-memory registry and synthetic transport; not DB capacity or field measurement'}),contentType:'application/json'});
  expect(p95).toBeLessThanOrEqual(2000);
 });
}
