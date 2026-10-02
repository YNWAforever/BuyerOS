/** Real local Workflow probe, with explicitly mocked operational HTTP only. */
import { env } from 'cloudflare:workers';
import { introspectWorkflowInstance } from 'cloudflare:test';
import { http, HttpResponse } from 'msw';
import { expect, it } from 'vitest';
import { network } from '../../services/cloudflare-jobs/tests/network';
import { workflowId } from '../../services/cloudflare-jobs/src/protocol';

it('the probe Workflow carries its opaque probe ID into the committed receipt request', async () => {
  const probe = { v: 1 as const, kind: 'probe' as const, probe_id: crypto.randomUUID(), runtime_epoch: 1 };
  let body: unknown;
  network.use(http.post('https://fixture.invalid/v1/internal/worker/maintenance', async ({ request }) => {
    body = await request.json();
    return HttpResponse.json({ runtime_epoch: 1, recovered: 0, enabled: true, alerts: [] });
  }));
  const introspector = await introspectWorkflowInstance(env.JOB_WORKFLOW, workflowId(probe));
  try {
    await env.JOB_WORKFLOW.create({ id: workflowId(probe), params: probe });
    await introspector.waitForStatus('complete');
    expect(body).toEqual({ runtime_epoch: 1, probe_id: probe.probe_id });
    expect(await introspector.getOutput()).toEqual({ state: 'done', code: 'OK', next_step_key: null, retry_at: null });
  } finally { await introspector.dispose(); }
});

it('a probe cannot report success when the durable selector is paused', async () => {
  const probe = { v: 1 as const, kind: 'probe' as const, probe_id: crypto.randomUUID(), runtime_epoch: 1 };
  network.use(http.post('https://fixture.invalid/v1/internal/worker/maintenance', () =>
    HttpResponse.json({ runtime_epoch: 1, recovered: 0, enabled: false, alerts: ['PROBE_STALE'] })));
  const introspector = await introspectWorkflowInstance(env.JOB_WORKFLOW, workflowId(probe));
  try {
    await env.JOB_WORKFLOW.create({ id: workflowId(probe), params: probe });
    await introspector.waitForStatus('complete');
    expect(await introspector.getOutput()).toEqual({ state: 'blocked', code: 'EXECUTION_DISABLED', next_step_key: null, retry_at: null });
  } finally { await introspector.dispose(); }
});
