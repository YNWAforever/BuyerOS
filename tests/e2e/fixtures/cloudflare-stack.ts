import {expect} from '@playwright/test';

export async function awaitCloudflareIntent(runId:string, projectId:string, draftJobId?:string):Promise<{stdout:string}> {
  for (const id of [runId, projectId, ...(draftJobId ? [draftJobId] : [])]) {
    if (!/^[0-9a-f-]{36}$/.test(id)) throw new Error('fixture requires UUID identifiers');
  }
  const url=new URL(`/fixture/cloudflare/state/${projectId}/${runId}`, 'http://127.0.0.1:8000');
  if (draftJobId) url.searchParams.set('draft_job_id',draftJobId);
  let report:Record<string,unknown>={};
  await expect.poll(async()=>{
    const response=await fetch(url);
    if (!response.ok) throw new Error(`Cloudflare fixture state read failed:${response.status}`);
    report=await response.json();
    expect(report.transport).toBe('actual-local-cloudflare');
    // The native job can commit before the platform step receipt is recorded.
    // Both observations must be ready before this real-transport check succeeds.
    return {status:report.status,receipted:typeof report.platform_receipts==='number' && report.platform_receipts>0};
  },{timeout:180_000,intervals:[250,500,1000]}).toEqual({status:'completed',receipted:true});
  expect(report.platform_receipts).toBeGreaterThan(0);
  return {stdout:JSON.stringify(report)};
}
