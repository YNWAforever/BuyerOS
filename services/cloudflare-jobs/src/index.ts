import { callWorkerApi } from './api-client';
import { dispatchTick } from './dispatcher';
import { handoffMessage } from './queue';
import { parseEnvelope, type ApiCall } from './protocol';
export { BuyerOSJobWorkflow } from './workflow';

function epoch(value: string): number {
  if (!/^[1-9][0-9]*$/.test(value) || !Number.isSafeInteger(Number(value))) throw new Error('invalid runtime epoch');
  return Number(value);
}

export default {
  async scheduled(_event: ScheduledController, env: Env): Promise<void> {
    if (env.EXECUTION_ENABLED !== 'true') return;
    const runtimeEpoch = epoch(env.RUNTIME_EPOCH);
    const api: ApiCall = (operation, body, timeout) => callWorkerApi(env, operation, body, timeout);
    await env.JOBS.send({ v: 1, kind: 'probe', probe_id: crypto.randomUUID(), runtime_epoch: runtimeEpoch });
    await dispatchTick({ enabled: true, epoch: runtimeEpoch, api, send: async item => { await env.JOBS.send(item); } });
  },
  async queue(batch: MessageBatch<unknown>, env: Env): Promise<void> {
    for (const message of batch.messages) {
      if (env.EXECUTION_ENABLED !== 'true') { message.retry({ delaySeconds: 60 }); continue; }
      try { parseEnvelope(message.body); }
      catch {
        // Quarantine only the opaque queue message ID. Never persist or log an
        // invalid body that might contain customer data or attacker URLs.
        await env.QUARANTINE.send({ v: 1, message_id: message.id, reason: 'INVALID_ENVELOPE' });
        message.ack();
        continue;
      }
      await handoffMessage(message, env.JOB_WORKFLOW);
    }
  },
} satisfies ExportedHandler<Env>;
