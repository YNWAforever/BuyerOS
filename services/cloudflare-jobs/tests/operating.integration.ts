/** Ten simultaneous actual Queue deliveries; no API or provider mocks. */
import {env} from 'cloudflare:workers';
import {introspectWorkflowInstance} from 'cloudflare:test';
import {expect,it} from 'vitest';
import {parseEnvelope,workflowId} from '../src/protocol';

it('ten real Queue/Workflow jobs complete under the one global PostgreSQL permit',async()=>{
  const jobs=(JSON.parse((env as Env & {CF_TEST_JOBS:string}).CF_TEST_JOBS) as unknown[]).map(parseEnvelope);
  expect(jobs).toHaveLength(10);
  const inspectors=await Promise.all(jobs.map(job=>introspectWorkflowInstance(env.JOB_WORKFLOW,workflowId(job))));
  try{
    await Promise.all(jobs.map(job=>env.JOBS.send(job)));
    await Promise.all(inspectors.map(i=>i.waitForStatus('complete')));
    for(const i of inspectors) expect(await i.getOutput()).toEqual({state:'done',code:'OK',next_step_key:null,retry_at:null});
    const probe={v:1 as const,kind:'probe' as const,probe_id:crypto.randomUUID(),runtime_epoch:jobs[0].runtime_epoch};
    const inspector=await introspectWorkflowInstance(env.JOB_WORKFLOW,workflowId(probe));
    try{await env.JOBS.send(probe);await inspector.waitForStatus('complete');
      expect(await inspector.getOutput()).toEqual({state:'done',code:'OK',next_step_key:null,retry_at:null});
    }finally{await inspector.dispose();}
  }finally{await Promise.all(inspectors.map(i=>i.dispose()));}
});
