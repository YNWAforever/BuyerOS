import { expect, it, vi } from 'vitest';

const job = { v: 1, workspace_id: '11111111-1111-4111-8111-111111111111', outbox_id: '22222222-2222-4222-8222-222222222222', generation: 1, runtime_epoch: 1 } as const;
const done = { state: 'done', code: 'OK', next_step_key: null, retry_at: null };

it('HTTP timeout reads committed status before any repeated execution', async () => {
  const { executeUnit } = await import('../src/workflow');
  const api = vi.fn().mockRejectedValueOnce(new Error('fictional HTTP timeout')).mockResolvedValueOnce(done);
  expect(await executeUnit(api, job, 'start')).toEqual(done);
  expect(api.mock.calls.map(c => c[0])).toEqual(['workerExecuteStep', 'workerStepStatus']);
});

it('busy permits wait without consuming the transient error budget', async () => {
  const { runJob } = await import('../src/workflow');
  const busy = { state: 'retry_later', code: 'IN_PROGRESS', next_step_key: 'start', retry_at: '2026-10-01T00:00:01Z' };
  const api = vi.fn().mockResolvedValueOnce(busy).mockResolvedValueOnce(busy).mockResolvedValueOnce(busy).mockResolvedValueOnce(busy).mockResolvedValueOnce(busy).mockResolvedValueOnce(busy).mockResolvedValueOnce(done);
  const sleep = vi.fn().mockResolvedValue(undefined);
  const execute = async <T>(_name: string, action: () => Promise<T>) => action();
  expect(await runJob(job, { api, sleep, execute })).toEqual(done);
  expect(sleep).toHaveBeenCalledTimes(6);
});

it('unknown acceptance stops the controller without a new submit', async () => {
  const { runJob } = await import('../src/workflow');
  const unknown = { state: 'reconcile', code: 'PROVIDER_UNKNOWN', next_step_key: null, retry_at: null };
  const api = vi.fn().mockResolvedValue(unknown);
  const sleep = vi.fn();
  const execute = async <T>(_name: string, action: () => Promise<T>) => action();
  expect(await runJob(job, { api, sleep, execute })).toEqual(unknown);
  expect(api).toHaveBeenCalledOnce();
  expect(sleep).not.toHaveBeenCalled();
});

it('a failed status read is retried as status, never another execution request', async () => {
  const { runJob } = await import('../src/workflow');
  const api = vi.fn().mockRejectedValueOnce(new Error('execution response lost'))
    .mockRejectedValueOnce(new Error('status unavailable')).mockResolvedValueOnce(done);
  const execute = async <T>(_name: string, action: () => Promise<T>) => action();
  expect(await runJob(job, { api, execute, sleep: vi.fn().mockResolvedValue(undefined) })).toEqual(done);
  expect(api.mock.calls.map(c => c[0])).toEqual(['workerExecuteStep', 'workerStepStatus', 'workerStepStatus']);
});

it('halts a cyclic continuation at the persisted receipt ceiling', async () => {
  const { runJob } = await import('../src/workflow');
  const api = vi.fn().mockResolvedValue({ state: 'continue', code: 'OK', next_step_key: 'step:1', retry_at: null });
  const execute = async <T>(_name: string, action: () => Promise<T>) => action();
  const result = await runJob(job, { api, execute, sleep: vi.fn() });
  expect(result).toEqual({ state: 'blocked', code: 'LIMIT_EXCEEDED', next_step_key: null, retry_at: null });
  expect(api).toHaveBeenCalledTimes(512);
});
