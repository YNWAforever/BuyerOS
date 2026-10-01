import { claimSchema, type ApiCall, type JobEnvelope } from './protocol';

export async function dispatchTick(ports: {
  enabled: boolean; epoch: number; api: ApiCall; send: (envelope: JobEnvelope) => Promise<void>;
  now?: () => number;
}): Promise<{ claimed: number; published: number }> {
  if (!ports.enabled) return { claimed: 0, published: 0 };
  const now = ports.now ?? Date.now;
  const deadline = now() + 10_000;
  const batch = claimSchema.parse(await ports.api('workerClaim', { runtime_epoch: ports.epoch, max_total: 10, time_budget_seconds: 10 }, 10_000));
  if (batch.runtime_epoch !== ports.epoch) throw new Error('claim epoch changed');
  let published = 0;
  for (const item of batch.items) {
    if (now() >= deadline) break;
    // Acceptance and a lost response are ambiguous. Never reset the generation
    // or report failed publication to make the API claim the same work blindly.
    await ports.send(item);
    published += 1;
    await ports.api('workerRecordPublication', { envelope: item, state: 'published' }, Math.max(1, deadline - now()));
  }
  return { claimed: batch.items.length, published };
}
