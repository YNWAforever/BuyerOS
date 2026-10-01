import { parseEnvelope, workflowId, type QueueEnvelope } from './protocol';

type Instance = Pick<WorkflowInstance, 'id' | 'status'>;
type WorkflowPort = { create: (options: { id: string; params: QueueEnvelope }) => Promise<Instance>; get: (id: string) => Promise<Instance> };

export async function handoffMessage(message: Pick<Message<unknown>, 'body' | 'ack' | 'retry'>, workflow: WorkflowPort): Promise<void> {
  const envelope = parseEnvelope(message.body);
  const id = workflowId(envelope);
  try {
    let instance: Instance;
    try { instance = await workflow.create({ id, params: envelope }); }
    catch { instance = await workflow.get(id); }
    if (instance.id !== id) throw new Error('workflow identity mismatch');
    const status = await instance.status();
    if (!['queued', 'running', 'paused', 'errored', 'terminated', 'complete', 'waiting', 'waitingForPause'].includes(status.status)) {
      throw new Error('workflow existence not verified');
    }
    // Creation/existence is a handoff only. Business completion is in PostgreSQL.
    message.ack();
  } catch { message.retry({ delaySeconds: 5 }); }
}
