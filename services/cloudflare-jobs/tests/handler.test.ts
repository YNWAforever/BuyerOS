import { env } from 'cloudflare:workers';
import { createMessageBatch, createExecutionContext, getQueueResult } from 'cloudflare:test';
import { expect, it, vi } from 'vitest';
import worker from '../src/index';

it('quarantines only opaque metadata and ACKs invalid data after quarantine accepts', async () => {
  const send = vi.fn().mockResolvedValue(undefined);
  const create = vi.fn();
  const batch = createMessageBatch('buyeros-jobs', [{ id: 'opaque-invalid-1', timestamp: new Date(), attempts: 1,
    body: { email: 'fictional@example.invalid', url: 'https://attacker.invalid/' } }]);
  await worker.queue(batch, { ...env, QUARANTINE: { ...env.QUARANTINE, send },
    JOB_WORKFLOW: { create, get: vi.fn(), createBatch: vi.fn(), deleteBatch: vi.fn() } });
  expect(send).toHaveBeenCalledWith({ v: 1, message_id: 'opaque-invalid-1', reason: 'INVALID_ENVELOPE' });
  expect((await getQueueResult(batch, createExecutionContext())).explicitAcks).toEqual(['opaque-invalid-1']);
  expect(create).not.toHaveBeenCalled();
});

it('disabled handoff retains messages for retry and has no public fetch entrypoint', async () => {
  const batch = createMessageBatch('buyeros-jobs', [{ id: 'opaque-paused-1', timestamp: new Date(), attempts: 1, body: {} }]);
  const retry = vi.spyOn(batch.messages[0], 'retry');
  await worker.queue(batch, { ...env, EXECUTION_ENABLED: 'false' });
  const result = await getQueueResult(batch, createExecutionContext());
  expect(result.explicitAcks).toEqual([]);
  // This SDK's QueueResult omits per-message delay; verify the actual handler
  // argument independently while retaining the platform's retry evidence.
  expect(result.retryMessages).toEqual([{ msgId: 'opaque-paused-1' }]);
  expect(retry).toHaveBeenCalledWith({ delaySeconds: 60 });
  expect('fetch' in worker).toBe(false);
});
