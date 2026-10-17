import type {components} from '../../services/generated/buyeros-api';

export type ActivationSubmit = components['schemas']['ActivationSubmit'];
export type ActivationDecision = components['schemas']['ActivationDecision'];
export type ActivationWithdrawal = components['schemas']['ActivationWithdrawal'];
export type ActivationView = components['schemas']['ActivationView'];
export interface PolicyClientScope {
  actor_id: string; workspace_id: string; project_id: string; isCurrent(): boolean;
}
export interface PolicyActivationLocator {
  actor_id: string; workspace_id: string; project_id: string;
  client_request_id: string; operation: 'submit' | 'approve' | 'reject' | 'withdraw';
  operation_key: string; request_id: string | null; terms_hash: string | null;
}
export interface PolicyTransport {
  submit(scope: PolicyClientScope, data: ActivationSubmit, key: string): Promise<ActivationView>;
  decide(scope: PolicyClientScope, id: string, data: ActivationDecision, key: string): Promise<ActivationView>;
  withdraw(scope: PolicyClientScope, id: string, data: ActivationWithdrawal, key: string): Promise<ActivationView>;
  get(scope: PolicyClientScope, id: string): Promise<ActivationView>;
  find(scope: PolicyClientScope, reference: string): Promise<ActivationView | null>;
}
export class PolicyScopeChanged extends Error {}
export class PolicyUnconfirmed extends Error {
  constructor(readonly locator: PolicyActivationLocator) {super('Policy result is unconfirmed. Check the original request.');}
}
const scopeKey = (s: PolicyClientScope) => JSON.stringify([s.actor_id, s.workspace_id, s.project_id]);
function guard(scope: PolicyClientScope, locator?: PolicyActivationLocator) {
  if (!scope.isCurrent() || (locator && scopeKey(scope) !== scopeKey({...locator, isCurrent: () => true}))) {
    throw new PolicyScopeChanged('Policy scope changed. Recover in the original workspace.');
  }
}
function stable(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(stable);
  if (value && typeof value === 'object') return Object.fromEntries(
    Object.entries(value).sort(([a], [b]) => a.localeCompare(b)).map(([key, item]) => [key, stable(item)]));
  return value;
}
type Entry = {
  fingerprint: string; locator: PolicyActivationLocator; scope: PolicyClientScope;
  promise: Promise<ActivationView> | null; attempted: boolean; confirmed: boolean; rejected: boolean;
};
export function createPolicyActivationClient(transport: PolicyTransport) {
  // The payload stays in memory. Only the non-content locator is exposed for
  // session storage. No token, person, channel or approval evidence is retained.
  const entries = new Map<string, Entry>();
  async function recoverPolicyActivation(scope: PolicyClientScope, locator: PolicyActivationLocator) {
    guard(scope, locator);
    const result = locator.request_id
      ? await transport.get(scope, locator.request_id)
      : await transport.find(scope, locator.client_request_id);
    guard(scope, locator);
    if (result && (result.project_id !== scope.project_id ||
      (locator.request_id && result.id !== locator.request_id) ||
      (!locator.request_id && result.client_request_id !== locator.client_request_id) ||
      (locator.terms_hash && result.terms_hash !== locator.terms_hash))) {
      throw new PolicyUnconfirmed(locator);
    }
    const entry = entries.get(scopeKey(scope));
    if (entry && entry.locator.operation === locator.operation &&
      entry.locator.client_request_id === locator.client_request_id) {
      // Only the original operation may be settled: a submit is resolved by the
      // request existing; a decision/withdrawal only by a non-pending outcome.
      const resolved = result !== null && (locator.operation === 'submit' || result.request_state !== 'submitted');
      if (resolved) entry.confirmed = true;
      if (result) entry.locator = {...entry.locator, request_id: result.id, terms_hash: result.terms_hash};
    }
    return result;
  }
  function run(scope: PolicyClientScope, operation: PolicyActivationLocator['operation'],
    reference: string, id: string | null, hash: string | null, data: unknown,
    write: (key: string) => Promise<ActivationView>): Promise<ActivationView> {
    try {guard(scope);} catch (cause) {return Promise.reject(cause);}
    const key = scopeKey(scope), fingerprint = JSON.stringify(stable({operation, reference, id, data}));
    let entry = entries.get(key);
    if (entry && entry.fingerprint !== fingerprint && !entry.confirmed && !entry.rejected) {
      return Promise.reject(new PolicyUnconfirmed({...entry.locator}));
    }
    if (!entry || entry.fingerprint !== fingerprint) {
      entry = {fingerprint, scope, promise: null, attempted: false, confirmed: false, rejected: false,
        locator: {actor_id: scope.actor_id, workspace_id: scope.workspace_id, project_id: scope.project_id,
          client_request_id: reference, operation, operation_key: crypto.randomUUID(), request_id: id, terms_hash: hash}};
      entries.set(key, entry);
    }
    if (entry.promise && entry.scope.isCurrent()) return entry.promise;
    const active = entry;
    active.scope = scope;
    const promise = (async () => {
      try {
        guard(scope);
        if (active.attempted) {
          const canonical = await recoverPolicyActivation(scope, active.locator);
          if (canonical && (operation === 'submit' || canonical.request_state !== 'submitted')) {
            active.confirmed = true;
            return canonical;
          }
          if (active.confirmed) throw new PolicyUnconfirmed({...active.locator});
          // An explicit retry first completed canonical lookup. Reuse the exact
          // original key and in-memory body; the server also deduplicates refs.
        }
        active.attempted = true;
        const result = await write(active.locator.operation_key);
        guard(scope);
        active.locator = {...active.locator, request_id: result.id, terms_hash: result.terms_hash};
        active.confirmed = true;
        return result;
      } catch (cause) {
        guard(scope);
        if (cause instanceof PolicyScopeChanged || cause instanceof PolicyUnconfirmed) throw cause;
        const status = (cause as {status?: number} | null)?.status;
        if (status && [400, 401, 403, 404, 409, 412, 422].includes(status)) {
          active.rejected = true;
          throw cause;
        }
        throw new PolicyUnconfirmed({...active.locator});
      } finally {
        if (active.scope === scope) active.promise = null;
      }
    })();
    active.promise = promise;
    return promise;
  }
  return {
    submitPolicyActivation: (scope: PolicyClientScope, data: ActivationSubmit) =>
      run(scope, 'submit', data.client_request_id, null, null, data,
        key => transport.submit(scope, data, key)),
    decidePolicyActivation: (scope: PolicyClientScope, id: string, data: ActivationDecision) =>
      run(scope, data.action, '', id, data.terms_hash, data,
        key => transport.decide(scope, id, data, key)),
    withdrawPolicyActivation: (scope: PolicyClientScope, id: string, data: ActivationWithdrawal) =>
      run(scope, 'withdraw', '', id, data.terms_hash, data,
        key => transport.withdraw(scope, id, data, key)),
    recoverPolicyActivation,
    getLocator: (scope: PolicyClientScope): PolicyActivationLocator | null => {
      const locator = entries.get(scopeKey(scope))?.locator;
      return locator ? {...locator} : null;
    },
  };
}
