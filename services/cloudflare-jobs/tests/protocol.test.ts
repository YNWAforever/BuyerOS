import { describe, expect, it } from 'vitest';

export const job = {
  v: 1, workspace_id: '11111111-1111-4111-8111-111111111111',
  outbox_id: '22222222-2222-4222-8222-222222222222', generation: 1, runtime_epoch: 1,
} as const;

describe('opaque worker protocol', () => {
  it('rejects extra customer fields, URLs and unsafe numbers before scheduling', async () => {
    const { parseEnvelope } = await import('../src/protocol');
    expect(parseEnvelope(job)).toEqual(job);
    for (const value of [
      { ...job, url: 'https://customer.invalid/' }, { ...job, email: 'fixture@example.invalid' },
      { ...job, runtime_epoch: true }, { ...job, generation: Number.MAX_SAFE_INTEGER + 1 },
      { ...job, workspace_id: '../tenant' }, { ...job, v: 2 },
    ]) expect(() => parseEnvelope(value)).toThrow();
  });
  it('separates operational probes and deterministic workflow IDs', async () => {
    const { parseEnvelope, workflowId } = await import('../src/protocol');
    expect(workflowId(job)).toBe('bo1-22222222222242228222222222222222-g1-e1');
    const probe = { v: 1, kind: 'probe', probe_id: job.outbox_id, runtime_epoch: 1 };
    expect(parseEnvelope(probe)).toEqual(probe);
    expect(() => parseEnvelope({ ...probe, workspace_id: job.workspace_id })).toThrow();
    expect(workflowId({ ...job, generation: 2 })).not.toBe(workflowId(job));
  });
  it('requires the four-field bounded outcome and server-issued step key', async () => {
    const { parseOutcome } = await import('../src/protocol');
    const valid = { state: 'continue', code: 'OK', next_step_key: 'step:1', retry_at: null };
    expect(parseOutcome(valid)).toEqual(valid);
    for (const value of [{ ...valid, next_step_key: 'https://bad.invalid/' }, { ...valid, result: 'secret' },
      { state: 'done', code: 'OK' }, { ...valid, retry_at: 'not-a-time' }, { ...valid, state: 'success' },
      { ...valid, next_step_key: 'step.1' }]) {
      expect(() => parseOutcome(value)).toThrow();
    }
  });
});
