import { z } from 'zod';
import type { operations, components } from './worker-api.generated';

export type JobEnvelope = components['schemas']['JobEnvelope'];
export type StepOutcome = components['schemas']['StepOutcome'];
export type InternalOperation = keyof operations;
export type InternalRequest<K extends InternalOperation> = operations[K]['requestBody']['content']['application/json'];
export type InternalResponse<K extends InternalOperation> = operations[K]['responses'][200]['content']['application/json'];
export type ApiCall = <K extends InternalOperation>(operation: K, body: InternalRequest<K>, timeoutMs?: number) => Promise<InternalResponse<K>>;

const positive = z.number().int().min(1).max(Number.MAX_SAFE_INTEGER);
const uuid = z.string().uuid().transform(value => value.toLowerCase());
export const jobSchema = z.object({
  v: z.literal(1), workspace_id: uuid, outbox_id: uuid,
  generation: positive, runtime_epoch: positive,
}).strict();
const probeSchema = z.object({
  v: z.literal(1), kind: z.literal('probe'), probe_id: uuid, runtime_epoch: positive,
}).strict();
export type ProbeEnvelope = z.infer<typeof probeSchema>;
export type QueueEnvelope = JobEnvelope | ProbeEnvelope;

export function parseEnvelope(value: unknown): QueueEnvelope {
  return z.union([jobSchema, probeSchema]).parse(value);
}

export function workflowId(value: QueueEnvelope): string {
  const envelope = parseEnvelope(value);
  return 'kind' in envelope
    ? `bop1-${envelope.probe_id.replaceAll('-', '')}-e${envelope.runtime_epoch}`
    : `bo1-${envelope.outbox_id.replaceAll('-', '')}-g${envelope.generation}-e${envelope.runtime_epoch}`;
}

export const stepKeySchema = z.string().regex(/^[a-z0-9][a-z0-9:_-]{0,63}$/);
const outcomeSchema = z.object({
  state: z.enum(['done', 'continue', 'retry_later', 'reconcile', 'blocked', 'stale']),
  code: z.enum(['OK', 'EXECUTION_DISABLED', 'CAPABILITY_UNAVAILABLE', 'POLICY_CHANGED',
    'ACTOR_CHANGED', 'INVALID_INTENT', 'STALE_FENCE', 'IN_PROGRESS',
    'TRANSIENT_UNAVAILABLE', 'PROVIDER_UNKNOWN', 'LIMIT_EXCEEDED', 'STEP_FAILED']),
  next_step_key: stepKeySchema.nullable(),
  retry_at: z.string().datetime({ offset: true }).regex(/(?:Z|\+00:00)$/).nullable(),
}).strict();

export function parseOutcome(value: unknown): StepOutcome {
  const result = outcomeSchema.parse(value);
  if (new TextEncoder().encode(JSON.stringify(result)).byteLength > 2048) {
    throw new Error('worker outcome exceeds protocol bound');
  }
  if (result.state === 'continue' && result.next_step_key === null) {
    throw new Error('continuation lacks a server step key');
  }
  return result;
}

export const claimSchema = z.object({
  runtime_epoch: positive, items: z.array(jobSchema).max(10), next_cursor: uuid.nullable(),
}).strict();
export const maintenanceSchema = z.object({
  runtime_epoch: positive, recovered: z.number().int().min(0).max(10), enabled: z.boolean(),
  alerts: z.array(z.enum(['PROBE_STALE', 'WORK_BACKLOG'])).max(2),
}).strict();
export const requestSchemas = {
  workerClaim: z.object({ runtime_epoch: positive, max_total: z.number().int().min(1).max(10), time_budget_seconds: z.number().int().min(1).max(10) }).strict(),
  workerMaintenance: z.object({ runtime_epoch: positive, probe_id: uuid.nullable().optional() }).strict(),
  workerRecordPublication: z.object({ envelope: jobSchema, state: z.enum(['published', 'unknown', 'failed']) }).strict(),
  workerExecuteStep: z.object({ envelope: jobSchema, step_key: stepKeySchema }).strict(),
  workerStepStatus: z.object({ envelope: jobSchema, step_key: stepKeySchema }).strict(),
} satisfies Record<InternalOperation, z.ZodType>;

export function parseResponse<K extends InternalOperation>(operation: K, value: unknown): InternalResponse<K> {
  const parsed = operation === 'workerClaim' ? claimSchema.parse(value)
    : operation === 'workerMaintenance' ? maintenanceSchema.parse(value) : parseOutcome(value);
  // Runtime parsing above checks every field; this associates the validated
  // discriminant with its generated OpenAPI response type.
  return parsed as InternalResponse<K>;
}
