import {describe, expect, it} from 'vitest';
import {
  createPolicyActivationClient, PolicyScopeChanged, PolicyUnconfirmed,
  type PolicyTransport, type PolicyClientScope, type ActivationSubmit, type ActivationView,
} from '../features/live/policy-activation-client';

const scope = (): PolicyClientScope => ({
  actor_id: 'fixture-actor', workspace_id: 'fixture-workspace', project_id: 'fixture-project', isCurrent: () => true,
});
// Synthetic wire fixture. No real source/owner/corporate subject.
const data = (): ActivationSubmit => ({
  client_request_id: '11111111-1111-4111-8111-111111111111',
  authority_id: '22222222-2222-4222-8222-222222222222', authority_version: 1,
  expected_policy_id: null, expected_policy_version: null,
  request_deadline: '2030-01-02T00:00:00Z',
  terms: {
    workspace_id: 'fixture-workspace', controller_scope_id: 'fixture-workspace', project_id: 'fixture-project',
    purpose: 'contact_research', template_version: 'manual-native.v1',
    allowed_actions: ['observation.append', 'lead.evidence.read'],
    allowed_data_categories: ['professional_identity', 'employment', 'procurement_scope', 'business_channel',
      'evidence_excerpt', 'review_note', 'preparation_content'],
    allowed_sources: {domains: ['rice.example.test'], document_ids: []},
    valid_from: '2030-01-01T00:00:00Z', expires_at: '2030-01-20T00:00:00Z', retention_days: 7,
    deletion_plan: {method: 'redact_private_payload', audit: 'retain_non_content', backup: 'expiry_and_replay',
      reference: 'fixture://deletion'}, countries: ['GB'], policy_version: 'fixture-v1',
    basis_reference: 'fixture://basis', provenance: 'synthetic fixture',
    owner_evidence_reference: 'fixture://owner', owner_evidence_sha256: 'a'.repeat(64),
  },
});
const view = (state = 'submitted', effective = 'unknown'): ActivationView => ({
  id: '33333333-3333-4333-8333-333333333333', project_id: 'fixture-project',
  client_request_id: data().client_request_id, requester_id: 'fixture-actor',
  authority_id: data().authority_id, authority_version: 1, terms: data().terms, terms_hash: 'b'.repeat(64),
  request_deadline: data().request_deadline, request_state: state, effective_status: effective,
  receipt: {request_id: '33333333-3333-4333-8333-333333333333', terms_hash: 'b'.repeat(64),
    outcome: state === 'submitted' ? 'submitted' : 'approved', resolution_id: null, decision_id: null, policy_version: null},
});
function fixture() {
  let stored: ActivationView | null = null;
  const writes: string[] = [];
  const transport: PolicyTransport = {
    submit: async (_scope, _data, key) => {writes.push(key); stored ??= view(); return stored;},
    get: async () => stored ?? Promise.reject(new Error('fixture absent')),
    find: async () => stored,
    decide: async (_scope, _id, _data, key) => {writes.push(key); stored = view('approved', 'permitted'); return stored;},
    withdraw: async (_scope, _id, _data, key) => {
      writes.push(key); stored = {...view(), request_state: 'withdrawn',
        receipt: {...view().receipt, outcome: 'withdrawn'}}; return stored;
    },
  };
  return {transport, writes, set: (next: ActivationView | null) => {stored = next;}};
}
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>(done => {resolve = done;});
  return {promise, resolve};
}

describe('controlled policy operation recovery', () => {
  it('duplicate_click_joins_one_original_write', async () => {
    const f = fixture(), wait = deferred<ActivationView>(), s = scope();
    f.transport.submit = async (_s, _d, key) => {f.writes.push(key); return wait.promise;};
    const client = createPolicyActivationClient(f.transport);
    const first = client.submitPolicyActivation(s, data()), second = client.submitPolicyActivation(s, data());
    wait.resolve(view());
    const [one, two] = await Promise.all([first, second]);
    expect(one.id).toBe(two.id);
    expect(f.writes).toHaveLength(1);
  });
  it('lost_commit_response_recovers_one_canonical_resource_without_another_write', async () => {
    const f = fixture(), s = scope();
    f.transport.submit = async (_s, _d, key) => {f.writes.push(key); f.set(view()); throw new Error('response lost');};
    const client = createPolicyActivationClient(f.transport);
    await expect(client.submitPolicyActivation(s, data())).rejects.toBeInstanceOf(PolicyUnconfirmed);
    const locator = client.getLocator(s)!;
    expect((await client.recoverPolicyActivation(s, locator))?.id).toBe(view().id);
    expect((await client.submitPolicyActivation(s, data())).id).toBe(view().id);
    expect(f.writes).toHaveLength(1);
    expect(Object.keys(locator).sort()).toEqual([
      'actor_id', 'client_request_id', 'operation', 'operation_key', 'project_id',
      'request_id', 'terms_hash', 'workspace_id',
    ]);
  });
  it('429_and_partial_read_failure_preserve_original_key_and_input', async () => {
    const f = fixture(), s = scope(), body = data();
    let attempts = 0;
    f.transport.submit = async (_s, received, key) => {
      expect(received).toEqual(body); f.writes.push(key);
      if (++attempts === 1) throw Object.assign(new Error('rate limited'), {status: 429});
      f.set(view()); return view();
    };
    const client = createPolicyActivationClient(f.transport);
    await expect(client.submitPolicyActivation(s, body)).rejects.toBeInstanceOf(PolicyUnconfirmed);
    const key = client.getLocator(s)!.operation_key;
    f.transport.find = async () => {throw Object.assign(new Error('history rate limited'), {status: 429});};
    await expect(client.submitPolicyActivation(s, body)).rejects.toBeInstanceOf(PolicyUnconfirmed);
    expect(f.writes).toEqual([key]);
    f.transport.find = async () => null;
    expect((await client.submitPolicyActivation(s, body)).id).toBe(view().id);
    expect(f.writes).toEqual([key, key]);
    expect(body.terms.provenance).toBe('synthetic fixture');
  });
  it('unresolved_payload_cannot_be_replaced_with_a_new_operation', async () => {
    const f = fixture(), s = scope();
    f.transport.submit = async () => {throw new Error('lost');};
    const client = createPolicyActivationClient(f.transport);
    await expect(client.submitPolicyActivation(s, data())).rejects.toBeInstanceOf(PolicyUnconfirmed);
    const changed = {...data(), request_deadline: '2030-01-03T00:00:00Z'};
    await expect(client.submitPolicyActivation(s, changed)).rejects.toBeInstanceOf(PolicyUnconfirmed);
    expect(client.getLocator(s)?.client_request_id).toBe(data().client_request_id);
  });
  it.each(['workspace', 'same-actor-relogin'])('late_policy_response_cannot_update_another_scope: %s', async scenario => {
    const f = fixture(), wait = deferred<ActivationView>();
    let current = true;
    const old = {...scope(), isCurrent: () => current};
    f.transport.submit = async (_s, _data, key) => {f.writes.push(key); f.set(view()); return wait.promise;};
    const client = createPolicyActivationClient(f.transport);
    const result = client.submitPolicyActivation(old, data());
    current = false;
    if (scenario === 'workspace') {
      wait.resolve(view());
      await expect(result).rejects.toBeInstanceOf(PolicyScopeChanged);
      const next = {...scope(), workspace_id: 'other-workspace'};
      expect(client.getLocator(next)).toBeNull();
      await expect(client.recoverPolicyActivation(next, client.getLocator(old)!)).rejects.toBeInstanceOf(PolicyScopeChanged);
    } else {
      // The same actor/workspace has a NEW session generation. It may reconcile
      // the committed resource, but cannot join the old in-flight promise.
      const recovered = client.submitPolicyActivation(scope(), data());
      wait.resolve(view());
      const [late, fresh] = await Promise.allSettled([result, recovered]);
      expect(late.status).toBe('rejected');
      if (late.status === 'rejected') expect(late.reason).toBeInstanceOf(PolicyScopeChanged);
      expect(fresh.status).toBe('fulfilled');
      if (fresh.status === 'fulfilled') expect(fresh.value.id).toBe(view().id);
      expect(f.writes).toHaveLength(1);
    }
  });
  it('relogin_can_read_original_locator_but_never_replay_the_old_generation', async () => {
    const f = fixture(), old = scope(), client = createPolicyActivationClient(f.transport);
    f.set(view('approved', 'expired'));
    const locator = {actor_id: old.actor_id, workspace_id: old.workspace_id, project_id: old.project_id,
      client_request_id: data().client_request_id, operation: 'approve' as const, operation_key: 'original-key',
      request_id: view().id, terms_hash: view().terms_hash};
    const current = await client.recoverPolicyActivation(scope(), locator);
    expect(current?.receipt.outcome).toBe('approved');
    expect(current?.effective_status).toBe('expired');
    expect(f.writes).toHaveLength(0);
  });
  it('lost_decision_response_reconciles_actual_outcome_and_does_not_reapprove', async () => {
    const f = fixture(), s = scope();
    f.set(view());
    f.transport.decide = async (_s, _id, _d, key) => {
      f.writes.push(key); f.set(view('approved', 'permitted')); throw new Error('lost');
    };
    const client = createPolicyActivationClient(f.transport);
    const decision = {action: 'approve' as const, terms_hash: view().terms_hash,
      expected_request_state: 'submitted' as const,
      expected_policy_id: null, expected_policy_version: null, reason: 'synthetic exact review'};
    await expect(client.decidePolicyActivation(s, view().id, decision)).rejects.toBeInstanceOf(PolicyUnconfirmed);
    expect((await client.decidePolicyActivation(s, view().id, decision)).request_state).toBe('approved');
    expect(f.writes).toHaveLength(1);
  });
  it('recovering_a_lost_submission_settles_it_so_the_owner_can_decide', async () => {
    const f = fixture(), s = scope();
    f.transport.submit = async (_s, _d, key) => {f.writes.push(key); f.set(view()); throw new Error('response lost');};
    const client = createPolicyActivationClient(f.transport);
    await expect(client.submitPolicyActivation(s, data())).rejects.toBeInstanceOf(PolicyUnconfirmed);
    await client.recoverPolicyActivation(s, client.getLocator(s)!);
    f.transport.decide = async (_s, _id, _d, key) => {f.writes.push(key); f.set(view('approved', 'permitted')); return view('approved', 'permitted');};
    const decision = {action: 'approve' as const, terms_hash: view().terms_hash, expected_request_state: 'submitted' as const,
      expected_policy_id: null, expected_policy_version: null, reason: 'synthetic exact review'};
    expect((await client.decidePolicyActivation(s, view().id, decision)).request_state).toBe('approved');
  });
  it('a_pending_decision_lookup_does_not_settle_the_original_operation', async () => {
    const f = fixture(), s = scope();
    f.set(view());
    f.transport.decide = async (_s, _id, _d, key) => {f.writes.push(key); throw Object.assign(new Error('rate limited'), {status: 429});};
    const client = createPolicyActivationClient(f.transport);
    const decision = {action: 'approve' as const, terms_hash: view().terms_hash, expected_request_state: 'submitted' as const,
      expected_policy_id: null, expected_policy_version: null, reason: 'synthetic exact review'};
    await expect(client.decidePolicyActivation(s, view().id, decision)).rejects.toBeInstanceOf(PolicyUnconfirmed);
    const recovered = await client.recoverPolicyActivation(s, client.getLocator(s)!);
    expect(recovered?.request_state).toBe('submitted');
    expect(client.getLocator(s)?.operation).toBe('approve');
    await expect(client.decidePolicyActivation(s, view().id, decision)).rejects.toBeInstanceOf(PolicyUnconfirmed);
  });
  it('withdrawal_uses_its_own_locator_and_returns_the_canonical_outcome', async () => {
    const f = fixture(), s = scope(), client = createPolicyActivationClient(f.transport);
    f.set(view());
    const result = await client.withdrawPolicyActivation(s, view().id,
      {terms_hash: view().terms_hash, reason: 'synthetic pending withdrawal'});
    expect(result.receipt.outcome).toBe('withdrawn');
    expect(f.writes).toHaveLength(1);
  });
});
