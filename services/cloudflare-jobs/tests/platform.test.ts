/** Actual local platform proof with a clearly mocked HTTP API. PG proof is separate. */
import { env } from 'cloudflare:workers';
import { introspectWorkflowInstance, createMessageBatch, createExecutionContext, getQueueResult } from 'cloudflare:test';
import { http, HttpResponse } from 'msw';
import { network } from './network';
import { expect, it } from 'vitest';
import worker from '../src/index';
import { workflowId, type JobEnvelope } from '../src/protocol';

const job: JobEnvelope = { v: 1, workspace_id: '11111111-1111-4111-8111-111111111111', outbox_id: '22222222-2222-4222-8222-222222222222', generation: 1, runtime_epoch: 1 };

it('real queue handler creates a durable Workflow; duplicate handoff keeps the same instance', async () => {
  let calls = 0;
  const introspector = await introspectWorkflowInstance(env.JOB_WORKFLOW, workflowId(job));
  try {
    network.use(http.post('https://fixture.invalid/v1/internal/worker/step', () => {
      calls++;
      return HttpResponse.json({ state: 'done', code: 'OK', next_step_key: null, retry_at: null });
    }));
    const batch = createMessageBatch('buyeros-jobs', [{ id: 'opaque-message-1', timestamp: new Date(), attempts: 1, body: job }]);
    const ctx = createExecutionContext();
    await worker.queue(batch, env);
    expect((await getQueueResult(batch, ctx)).explicitAcks).toEqual(['opaque-message-1']);
    await introspector.waitForStatus('complete');
    expect(await introspector.getOutput()).toEqual({ state: 'done', code: 'OK', next_step_key: null, retry_at: null });
    const duplicate = createMessageBatch('buyeros-jobs', [{ id: 'opaque-message-2', timestamp: new Date(), attempts: 2, body: job }]);
    await worker.queue(duplicate, env);
    expect((await getQueueResult(duplicate, createExecutionContext())).explicitAcks).toEqual(['opaque-message-2']);
    expect(calls).toBe(1);
  } finally { await introspector.dispose(); }
});
