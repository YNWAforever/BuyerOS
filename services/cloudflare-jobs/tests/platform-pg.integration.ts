/** Actual local Queue -> Workflow -> HTTP API -> owned PostgreSQL. No HTTP mock. */
import { env } from 'cloudflare:workers';
import { introspectWorkflowInstance } from 'cloudflare:test';
import { expect, it } from 'vitest';
import { callWorkerApi } from '../src/api-client';
import { parseEnvelope, workflowId } from '../src/protocol';

it('actual Queue binding commits one API-owned mutation; duplicate delivery keeps its receipt', async () => {
  const job = parseEnvelope(JSON.parse((env as Env & { CF_TEST_JOB: string }).CF_TEST_JOB));
  if ('kind' in job) throw new Error('customer fixture requires a JobEnvelope');
  const id = workflowId(job);
  const introspector = await introspectWorkflowInstance(env.JOB_WORKFLOW, id);
  try {
    await env.JOBS.send(job);
    await introspector.waitForStatus('complete');
    const expected = { state: 'done', code: 'OK', next_step_key: null, retry_at: null };
    expect(await introspector.getOutput()).toEqual(expected);
    // A duplicate is delivered by the actual binding; existence is verified by
    // the queue handler. A status read independently verifies durable API truth.
    await env.JOBS.send(job);
    expect((await env.JOB_WORKFLOW.get(id)).id).toBe(id);
    expect(await callWorkerApi(env, 'workerStepStatus', { envelope: job, step_key: 'start' })).toEqual(expected);
    expect(await callWorkerApi(env, 'workerExecuteStep', { envelope: job, step_key: 'start' })).toEqual(expected);
  } finally { await introspector.dispose(); }
});
