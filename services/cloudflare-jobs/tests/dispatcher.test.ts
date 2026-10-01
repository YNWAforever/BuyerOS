import { expect, it, vi } from 'vitest';

const job = { v: 1, workspace_id: '11111111-1111-4111-8111-111111111111', outbox_id: '22222222-2222-4222-8222-222222222222', generation: 1, runtime_epoch: 1 };

it('dispatch off performs no API or binding calls', async () => {
  const { dispatchTick } = await import('../src/dispatcher');
  const api = vi.fn();
  const send = vi.fn();
  expect(await dispatchTick({ enabled: false, epoch: 1, api, send })).toEqual({ claimed: 0, published: 0 });
  expect(api).not.toHaveBeenCalled();
  expect(send).not.toHaveBeenCalled();
});

it('claims at most ten IDs for ten seconds and records only accepted publication', async () => {
  const { dispatchTick } = await import('../src/dispatcher');
  const api = vi.fn().mockResolvedValueOnce({ runtime_epoch: 1, items: [job], next_cursor: null }).mockResolvedValueOnce({ state: 'done', code: 'OK', next_step_key: null, retry_at: null });
  const send = vi.fn().mockResolvedValue(undefined);
  expect(await dispatchTick({ enabled: true, epoch: 1, api, send })).toEqual({ claimed: 1, published: 1 });
  expect(api.mock.calls[0]).toEqual(['workerClaim', { runtime_epoch: 1, max_total: 10, time_budget_seconds: 10 }, expect.any(Number)]);
  expect(send).toHaveBeenCalledWith(job);
  expect(api.mock.calls[1][0]).toBe('workerRecordPublication');
  expect(api.mock.calls[1][1]).toEqual({ envelope: job, state: 'published' });
});

it('publish-before-receipt crash keeps the original opaque generation for recovery', async () => {
  const { dispatchTick } = await import('../src/dispatcher');
  const api = vi.fn().mockResolvedValueOnce({ runtime_epoch: 1, items: [job], next_cursor: null }).mockRejectedValueOnce(new Error('fictional receipt lost'));
  const send = vi.fn().mockResolvedValue(undefined);
  await expect(dispatchTick({ enabled: true, epoch: 1, api, send })).rejects.toThrow();
  expect(send).toHaveBeenCalledTimes(1);
  expect(api.mock.calls).toHaveLength(2);
  expect(api.mock.calls[1][1]).toEqual({ envelope: job, state: 'published' });
});

it('does not publish after the ten-second claim cycle expires', async () => {
  const { dispatchTick } = await import('../src/dispatcher');
  const api = vi.fn().mockResolvedValue({ runtime_epoch: 1, items: [job], next_cursor: null });
  const send = vi.fn();
  const now = vi.fn().mockReturnValueOnce(0).mockReturnValue(10_001);
  expect(await dispatchTick({ enabled: true, epoch: 1, api, send, now })).toEqual({ claimed: 1, published: 0 });
  expect(send).not.toHaveBeenCalled();
  expect(api).toHaveBeenCalledTimes(1);
});

it('rejects an over-limit batch or changed epoch before any binding side effect', async () => {
  const { dispatchTick } = await import('../src/dispatcher');
  for (const batch of [{ runtime_epoch: 1, items: Array.from({ length: 11 }, () => job), next_cursor: null },
    { runtime_epoch: 2, items: [job], next_cursor: null }]) {
    const send = vi.fn();
    await expect(dispatchTick({ enabled: true, epoch: 1, api: vi.fn().mockResolvedValue(batch), send })).rejects.toThrow();
    expect(send).not.toHaveBeenCalled();
  }
});
