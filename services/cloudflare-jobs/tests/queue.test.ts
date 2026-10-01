import { expect, it, vi } from 'vitest';

const job = { v: 1, workspace_id: '11111111-1111-4111-8111-111111111111', outbox_id: '22222222-2222-4222-8222-222222222222', generation: 1, runtime_epoch: 1 };

it('ACK requires verified creation or inspection of the deterministic instance', async () => {
  const { handoffMessage } = await import('../src/queue');
  const status = vi.fn().mockResolvedValue({ status: 'running' });
  const instance = { id: 'bo1-22222222222242228222222222222222-g1-e1', status };
  const create = vi.fn().mockRejectedValue(new Error('already exists'));
  const get = vi.fn().mockResolvedValue(instance);
  const ack = vi.fn();
  await handoffMessage({ body: job, ack, retry: vi.fn() }, { create, get });
  expect(get).toHaveBeenCalledWith(instance.id);
  expect(status).toHaveBeenCalledOnce();
  expect(ack).toHaveBeenCalledOnce();
  expect(create).toHaveBeenCalledTimes(1);
});

it('does not ACK an unverified handoff or restart an existing failed workflow', async () => {
  const { handoffMessage } = await import('../src/queue');
  const create = vi.fn().mockRejectedValue(new Error('temporary create failure'));
  const get = vi.fn().mockRejectedValue(new Error('not proven'));
  const ack = vi.fn();
  const retry = vi.fn();
  await handoffMessage({ body: job, ack, retry }, { create, get });
  expect(ack).not.toHaveBeenCalled();
  expect(retry).toHaveBeenCalledOnce();
  expect(create).toHaveBeenCalledTimes(1);
});
