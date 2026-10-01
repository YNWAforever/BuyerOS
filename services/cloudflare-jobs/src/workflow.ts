import { WorkflowEntrypoint, type WorkflowEvent, type WorkflowStep } from 'cloudflare:workers';
import { callWorkerApi, WorkerApiError } from './api-client';
import { parseEnvelope, parseOutcome, type ApiCall, type JobEnvelope, type QueueEnvelope, type StepOutcome } from './protocol';

const blocked = (code: StepOutcome['code']): StepOutcome => ({ state: 'blocked', code, next_step_key: null, retry_at: null });

export async function executeUnit(api: ApiCall, envelope: JobEnvelope, key: string): Promise<StepOutcome> {
  const started = Date.now();
  try { return parseOutcome(await api('workerExecuteStep', { envelope, step_key: key }, 75_000)); }
  catch (error) {
    if (error instanceof WorkerApiError && [401, 403, 422].includes(error.status)) throw error;
    // The server may have committed despite a lost response. This status read
    // must complete before any decision to execute this key again.
    return parseOutcome(await api('workerStepStatus', { envelope, step_key: key }, Math.max(1, 85_000 - (Date.now() - started))));
  }
}

type WorkflowPorts = {
  api: ApiCall;
  execute: (name: string, action: () => Promise<StepOutcome>) => Promise<StepOutcome>;
  sleep: (name: string, milliseconds: number) => Promise<void>;
};

export async function runJob(envelope: JobEnvelope, ports: WorkflowPorts): Promise<StepOutcome> {
  let key = 'start';
  let needsStatus = false;
  let failures = 0;
  let units = 0;
  // Count durable actions conservatively: execute can issue step+status and a
  // wait adds one platform step. Permanent receipts remain bounded separately.
  let controllerOperations = 0;
  for (let iteration = 0; controllerOperations + 3 <= 2048; iteration += 1) {
    controllerOperations += 2;
    let result: StepOutcome;
    try {
      result = parseOutcome(await ports.execute(`unit:${iteration}`, () => needsStatus
        ? ports.api('workerStepStatus', { envelope, step_key: key }, 75_000)
        : executeUnit(ports.api, envelope, key)));
      needsStatus = false;
    } catch (error) {
      if (error instanceof WorkerApiError && [401, 403, 422].includes(error.status)) return blocked('INVALID_INTENT');
      failures += 1;
      if (failures >= 5) return blocked('TRANSIENT_UNAVAILABLE');
      needsStatus = true;
      controllerOperations += 1;
      await ports.sleep(`transport:${iteration}`, Math.min(30_000, 1000 * 2 ** failures));
      continue;
    }
    if (['done', 'blocked', 'stale', 'reconcile'].includes(result.state)) return result;
    if (result.state === 'continue') {
      units += 1;
      if (units >= 512 || result.next_step_key === null) return blocked('LIMIT_EXCEEDED');
      key = result.next_step_key;
      failures = 0;
      continue;
    }
    if (result.code === 'TRANSIENT_UNAVAILABLE' && ++failures >= 5) return blocked('TRANSIENT_UNAVAILABLE');
    // Permit contention is an ordinary bounded wait; it consumes no transient
    // retry budget. Keep the same server-issued key and refresh its lease.
    controllerOperations += 1;
    const delay = result.retry_at === null ? 2000 : Date.parse(result.retry_at) - Date.now();
    await ports.sleep(`permit:${iteration}`, Math.max(1000, Math.min(60_000, delay)));
  }
  return blocked('LIMIT_EXCEEDED');
}

export class BuyerOSJobWorkflow extends WorkflowEntrypoint<Env, QueueEnvelope> {
  async run(event: WorkflowEvent<QueueEnvelope>, step: WorkflowStep): Promise<StepOutcome> {
    const envelope = parseEnvelope(event.payload);
    if (this.env.EXECUTION_ENABLED !== 'true') return blocked('EXECUTION_DISABLED');
    const api: ApiCall = (operation, body, timeout) => callWorkerApi(this.env, operation, body, timeout);
    if ('kind' in envelope) {
      const receipt = await step.do('operational-probe', { retries: { limit: 0, delay: '1 second' }, timeout: '90 seconds' },
        () => api('workerMaintenance', { runtime_epoch: envelope.runtime_epoch, probe_id: envelope.probe_id }));
      if (!receipt.enabled) return blocked('EXECUTION_DISABLED');
      if (receipt.runtime_epoch !== envelope.runtime_epoch) return { state: 'stale', code: 'STALE_FENCE', next_step_key: null, retry_at: null };
      return { state: 'done', code: 'OK', next_step_key: null, retry_at: null };
    }
    return runJob(envelope, {
      api,
      execute: (name, action) => step.do(name, { retries: { limit: 0, delay: '1 second' }, timeout: '90 seconds' }, action),
      sleep: (name, milliseconds) => step.sleep(name, `${Math.ceil(milliseconds / 1000)} seconds`),
    });
  }
}
