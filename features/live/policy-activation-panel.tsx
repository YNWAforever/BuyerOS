'use client';
import {PolicyTermsSummary} from './policy-terms-summary';
import {useOwnerDirectory} from './lead-workflow/owner-directory';
import {useEffect, useMemo, useRef, useState} from 'react';
import {useSessionSnapshot, useWorkspaceSession} from '@/features/providers/workspace-session';
import {createOperationClient, type WriteContext} from '@/services/live/operations';
import {describeLiveError, LiveCancelled} from '@/services/live/client';
import type {components} from '@/services/generated/buyeros-api';
import {
  createPolicyActivationClient, PolicyScopeChanged, PolicyUnconfirmed,
  type PolicyClientScope, type PolicyActivationLocator, type ActivationSubmit, type ActivationView,
} from './policy-activation-client';

type Authority = components['schemas']['AuthoritySummary'];
type Policy = components['schemas']['PolicyDecision'];
type UiScope = PolicyClientScope & {context: WriteContext};
type Props = {roles: string[]; t: (label: string) => string};
const categories = ['professional_identity', 'employment', 'procurement_scope', 'business_channel',
  'evidence_excerpt', 'review_note', 'preparation_content'];
const manualActions = new Set(['observation.append', 'lead.review', 'lead.evidence.read',
  'preparation.create', 'preparation.revise', 'preparation.request_review', 'preparation.review', 'preparation.read']);
const split = (text: string) => text.split(/[\s,;]+/).filter(Boolean);
const locatorKey = (s: PolicyClientScope) => `buyeros.policy-locator.v1:${JSON.stringify([s.actor_id, s.workspace_id, s.project_id])}`;
function persistLocator(scope: PolicyClientScope, locator: PolicyActivationLocator | null) {
  try {
    if (locator) sessionStorage.setItem(locatorKey(scope), JSON.stringify(locator));
    else sessionStorage.removeItem(locatorKey(scope));
  } catch {/* In-memory recovery remains available; no private body is persisted. */}
}
function restoreLocator(scope: PolicyClientScope): PolicyActivationLocator | null {
  try {
    const value = JSON.parse(sessionStorage.getItem(locatorKey(scope)) ?? 'null') as PolicyActivationLocator | null;
    if (value && value.actor_id === scope.actor_id && value.workspace_id === scope.workspace_id &&
      value.project_id === scope.project_id && typeof value.operation_key === 'string' &&
      typeof value.client_request_id === 'string' && ['submit', 'approve', 'reject', 'withdraw'].includes(value.operation) &&
      (value.request_id === null || typeof value.request_id === 'string') &&
      (value.terms_hash === null || typeof value.terms_hash === 'string')) {
      // Whitelist metadata even if browser storage has extra fields.
      return {actor_id: value.actor_id, workspace_id: value.workspace_id, project_id: value.project_id,
        client_request_id: value.client_request_id, operation: value.operation, operation_key: value.operation_key,
        request_id: value.request_id, terms_hash: value.terms_hash};
    }
  } catch {/* Invalid browser state never becomes approval authority. */}
  return null;
}

export function PolicyActivationPanel(props: Props) {
  const snapshot = useSessionSnapshot();
  return <PolicyActivationForm key={snapshot.identity} {...props}/>;
}
function PolicyActivationForm({roles, t}: Props) {
  const {session, client} = useWorkspaceSession(), snapshot = useSessionSnapshot();
  const admin = roles.includes('workspace_admin');
  const directory=useOwnerDirectory(null,admin);
  const {workspace, project} = snapshot.scope;
  const [authorities, setAuthorities] = useState<Authority[]>([]), [history, setHistory] = useState<ActivationView[]>([]);
  const [policies, setPolicies] = useState<Policy[]>([]), [selected, setSelected] = useState<ActivationView | null>(null);
  const [authorityId, setAuthorityId] = useState(''), [busy, setBusy] = useState(false);
  const [error, setError] = useState(''), [historyError, setHistoryError] = useState(''), [message, setMessage] = useState('');
  const [locator, setLocator] = useState<PolicyActivationLocator | null>(null);
  const [canRetry, setCanRetry] = useState(false);
  const [reason, setReason] = useState(''), [confirmation, setConfirmation] = useState(false);
  const [form, setForm] = useState({
    purpose: 'contact_research' as ActivationSubmit['terms']['purpose'], domains: '', documents: '',
    actions: [] as string[], version: '', basis: '', provenance: '', ownerRef: '', ownerHash: '',
    countries: '', deletionRef: '', validFrom: '', expires: '', deadline: '', retention: '7',
  });
  const submission = useRef<ActivationSubmit | null>(null);
  const retryWork = useRef<((scope: UiScope) => Promise<ActivationView>) | null>(null);
  function capture(): UiScope {
    const captured = session.captureWriteContext();
    if (!captured.project) throw new Error('Select a project.');
    return {actor_id: captured.actor, workspace_id: captured.workspace, project_id: captured.project,
      isCurrent: () => session.isCurrent(captured.identity),
      context: {...captured, isCurrent: () => session.isCurrent(captured.identity),
        getToken: async () => {const token = session.token(); if (!token) throw new LiveCancelled('Sign-in required'); return token;}}};
  }
  const op = useMemo(() => createOperationClient(client), [client]);
  const controller = useMemo(() => createPolicyActivationClient({
    submit: (s, body, key) => op.requestOperation('submitPolicyActivationRequest', {
      path: {workspace_id: s.workspace_id}, header: {'Idempotency-Key': key}, body}, (s as UiScope).context),
    decide: (s, id, body, key) => op.requestOperation('decidePolicyActivationRequest', {
      path: {workspace_id: s.workspace_id, request_id: id}, header: {'Idempotency-Key': key}, body}, (s as UiScope).context),
    withdraw: (s, id, body, key) => op.requestOperation('withdrawPolicyActivationRequest', {
      path: {workspace_id: s.workspace_id, request_id: id}, header: {'Idempotency-Key': key}, body}, (s as UiScope).context),
    get: (s, id) => op.requestOperation('getPolicyActivationRequest', {
      path: {workspace_id: s.workspace_id, request_id: id}}, (s as UiScope).context),
    find: async (s, reference) => (await op.requestOperation('listPolicyActivationRequests', {
      path: {workspace_id: s.workspace_id}, query: {project_id: s.project_id, client_request_id: reference}},
    (s as UiScope).context)).items[0] ?? null,
  }), [op]);
  async function load(scope: UiScope) {
    try {
      const collect = async <T,>(get: (offset: number) => Promise<{items: T[]; total: number}>) => {
        const items: T[] = [];
        for (;;) {
          const page = await get(items.length); items.push(...page.items);
          if (items.length >= page.total) return items;
          if (!page.items.length) throw new Error('Incomplete policy page');
        }
      };
      const [nextAuthorities, nextHistory, nextPolicies] = await Promise.all([
        collect<Authority>(offset => op.requestOperation('listPolicyControllerAuthorities', {
          path: {workspace_id: scope.workspace_id}, query: {project_id: scope.project_id, offset, limit: 100}}, scope.context)),
        collect<ActivationView>(offset => op.requestOperation('listPolicyActivationRequests', {
          path: {workspace_id: scope.workspace_id}, query: {project_id: scope.project_id, offset, limit: 100}}, scope.context)),
        collect<Policy>(offset => op.requestOperation('listPolicyDecisions', {
          path: {workspace_id: scope.workspace_id}, query: {subject_id: scope.project_id, offset, limit: 100}}, scope.context)),
      ]);
      if (!scope.isCurrent()) return;
      setAuthorities(nextAuthorities); setHistory(nextHistory); setPolicies(nextPolicies); setHistoryError('');
      setSelected(current => current ? nextHistory.find(item => item.id === current.id) ?? null : null);
      setAuthorityId(current => current || nextAuthorities.find(item => item.eligible)?.id || '');
    } catch (cause) {
      if (scope.isCurrent() && !(cause instanceof LiveCancelled)) setHistoryError(describeLiveError(cause));
    }
  }
  useEffect(() => {
    if (!admin || !workspace || !project) return;
    const captured = session.captureWriteContext();
    const scope: UiScope = {actor_id: captured.actor, workspace_id: captured.workspace, project_id: project,
      isCurrent: () => session.isCurrent(captured.identity),
      context: {...captured, isCurrent: () => session.isCurrent(captured.identity),
        getToken: async () => {const token = session.token(); if (!token) throw new LiveCancelled('Sign-in required'); return token;}}};
    void (async () => {
      const retained = restoreLocator(scope);
      if (scope.isCurrent()) setLocator(retained);
      await load(scope);
    })();
    // Scope identity keys this component; old callbacks also check their generation.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [snapshot.identity, admin, workspace, project, session, op]);

  function remember(scope: UiScope) {
    const next = controller.getLocator(scope);
    persistLocator(scope, next);
    if (scope.isCurrent()) setLocator(next);
  }
  function accept(scope: UiScope, view: ActivationView) {
    if (!scope.isCurrent()) return;
    setSelected(view); setConfirmation(false);
    setHistory(current => [view, ...current.filter(item => item.id !== view.id)]);
    setMessage('Canonical policy result retrieved. External sending remains disabled.');
    retryWork.current = null;
    setCanRetry(false);
    persistLocator(scope, null); setLocator(null);
    void load(scope);
  }
  async function perform(work: (scope: UiScope) => Promise<ActivationView>) {
    if (busy || !admin) return;
    const scope = capture();
    retryWork.current = work;
    setCanRetry(true);
    setBusy(true); setError(''); setMessage('');
    try {
      const pending = work(scope); remember(scope);
      accept(scope, await pending);
    } catch (cause) {
      if (scope.isCurrent() && !(cause instanceof LiveCancelled) && !(cause instanceof PolicyScopeChanged)) {
        if (cause instanceof PolicyUnconfirmed) {
          persistLocator(scope, cause.locator); setLocator(cause.locator); setError('');
        } else {
          persistLocator(scope, null); setLocator(null); submission.current = null; retryWork.current = null;
          setCanRetry(false);
          setError(describeLiveError(cause));
        }
      }
    } finally {if (scope.isCurrent()) setBusy(false);}
  }
  function createBody(scope: UiScope): ActivationSubmit {
    const authority = authorities.find(item => item.id === authorityId && item.eligible);
    if (!authority) throw new Error(t('No current controller designation. Ask the data owner.'));
    const head = policies.filter(item => item.subject_type === 'project' && item.purpose === form.purpose)
      .sort((a, b) => b.version - a.version)[0];
    const iso = (value: string) => {if (!value) throw new Error(t('Complete every policy term.')); return new Date(value + ':00Z').toISOString();};
    return {client_request_id: crypto.randomUUID(), authority_id: authority.id, authority_version: authority.version,
      expected_policy_id: head?.id ?? null, expected_policy_version: head?.version ?? null,
      request_deadline: iso(form.deadline), terms: {
        workspace_id: scope.workspace_id, controller_scope_id: scope.workspace_id, project_id: scope.project_id,
        purpose: form.purpose, template_version: 'manual-native.v1', allowed_actions: [...form.actions].sort(),
        allowed_data_categories: categories, allowed_sources: {domains: split(form.domains), document_ids: split(form.documents)},
        valid_from: iso(form.validFrom), expires_at: iso(form.expires), retention_days: Number(form.retention),
        deletion_plan: {method: 'redact_private_payload', audit: 'retain_non_content', backup: 'expiry_and_replay', reference: form.deletionRef},
        countries: split(form.countries), policy_version: form.version, basis_reference: form.basis, provenance: form.provenance,
        owner_evidence_reference: form.ownerRef, owner_evidence_sha256: form.ownerHash,
      }};
  }
  function submit() {
    void perform(scope => {
      submission.current ??= createBody(scope);
      return controller.submitPolicyActivation(scope, submission.current);
    });
  }
  function edit<K extends keyof typeof form>(key: K, value: (typeof form)[K]) {
    if (busy || locator) return;
    submission.current = null;
    setForm(current => ({...current, [key]: value}));
  }
  function decide(action: 'approve' | 'reject') {
    if (!selected || (action === 'approve' && !confirmation)) return;
    void perform(scope => controller.decidePolicyActivation(scope, selected.id, {
      action, terms_hash: selected.terms_hash, reason, expected_request_state: 'submitted',
      expected_policy_id: policies.filter(item => item.purpose === selected.terms.purpose)
        .sort((a, b) => b.version - a.version)[0]?.id ?? null,
      expected_policy_version: policies.filter(item => item.purpose === selected.terms.purpose)
        .sort((a, b) => b.version - a.version)[0]?.version ?? null,
    }));
  }
  async function recover() {
    if (!locator || busy) return;
    const scope = capture();
    setBusy(true); setError('');
    try {
      const result = await controller.recoverPolicyActivation(scope, locator);
      if (result && (locator.operation === 'submit' || result.request_state !== 'submitted')) accept(scope, result);
      else if (result && scope.isCurrent()) {
        // The original op is still pending: keep the locator and retry body.
        setSelected(result);
        setMessage('The original policy operation is still pending; no duplicate was created.');
      } else if (scope.isCurrent()) setError(t('Policy result is unconfirmed. Check the original request.'));
    } catch (cause) {
      if (scope.isCurrent() && !(cause instanceof LiveCancelled)) setError(describeLiveError(cause));
    } finally {if (scope.isCurrent()) setBusy(false);}
  }
  const fields = [
    ['domains', 'Source domains'], ['documents', 'Provided document IDs'], ['version', 'Policy version'],
    ['basis', 'Basis reference'], ['provenance', 'Provenance'], ['ownerRef', 'Owner evidence reference'],
    ['ownerHash', 'Owner evidence SHA-256'], ['countries', 'Country codes'],
    ['deletionRef', 'Deletion arrangement reference'],
  ] as const;
  return <section className="panel live-policy-activation" role="region" aria-label={t('Controlled purpose activation')}>
    <h2>{t('Controlled purpose activation')}</h2>
    <p>{t('Manual Native processing only. Policy approval does not authorize paid research, enrichment or external sending.')}</p>
    {!admin ? <p>{t('Your role cannot view policy records. Ask a workspace administrator.')}</p> : <>
      {error && <p role="alert">{error}</p>}{message && <p role="status">{t(message)}</p>}
      {historyError && <p role="alert">{t('Policy history could not be refreshed. Keep the confirmed result.')}: {historyError}</p>}
      <button disabled={busy || !project} onClick={() => void load(capture())}>{t('Refresh policy history')}</button>
      {locator && <div className="notice">
        <p>{t('Policy result is unconfirmed. Check the original request.')}</p>
        <p>{t('Original operation')}: {locator.operation_key}</p>
        <button disabled={busy} onClick={() => void recover()}>{t('Check original policy result')}</button>
        {canRetry && locator.operation === 'submit' &&
          <button disabled={busy} onClick={submit}>{t('Retry original policy application')}</button>}
        {locator.operation !== 'submit' && canRetry &&
          <button disabled={busy} onClick={() => {if (retryWork.current) void perform(retryWork.current);}}>
            {t('Retry original policy decision')}</button>}
      </div>}
      {!selected ? <div className="settings-grid">
        <div>
          <label>{t('Controller designation')} <select value={authorityId} onChange={event => setAuthorityId(event.target.value)}>
            <option value="">{t('Select designation')}</option>
            {authorities.map(item => <option key={item.id} value={item.id} disabled={!item.eligible}>
              {directory.name(item.approver_user_id)||t('Unavailable member')} · v{item.version} · {item.expires_at}
            </option>)}
          </select></label>
          {!authorities.some(item => item.eligible) && <p role="status">{t('No current controller designation. Ask the data owner.')}</p>}
          <label>{t('Purpose')} <select value={form.purpose} disabled={busy || !!locator}
            onChange={event => edit('purpose', event.target.value as typeof form.purpose)}>
            {(['account_research', 'contact_research', 'draft_preparation'] as const).map(value =>
              <option key={value} value={value}>{t(value)}</option>)}
          </select></label>
          {fields.map(([key, label]) => <label key={key}>{t(label)} <input value={form[key]} disabled={busy || !!locator}
            onChange={event => edit(key, event.target.value)}/></label>)}
        </div><div>
          <p>{t('Supported professional data template')}: {categories.map(t).join(', ')}</p>
          <fieldset disabled={busy || !!locator}><legend>{t('Manual actions in this designation')}</legend>
            {(authorities.find(item => item.id === authorityId)?.allowed_actions ?? []).filter(action => manualActions.has(action)).map(action =>
              <label key={action}><input type="checkbox" checked={form.actions.includes(action)}
                onChange={event => edit('actions', event.target.checked
                  ? [...form.actions, action].sort() : form.actions.filter(value => value !== action))}/>{action}</label>)}
            {!authorityId && <p>{t('Select designation')}</p>}</fieldset>
          {([['validFrom', 'Valid from (UTC)'], ['expires', 'Expires at (UTC)'],
            ['deadline', 'Application deadline (UTC)']] as const).map(([key, label]) =>
            <label key={key}>{t(label)} <input type="datetime-local" value={form[key]} disabled={busy || !!locator}
              onChange={event => edit(key, event.target.value)}/></label>)}
          <label>{t('Retention days')} <input type="number" min="1" max="3650" value={form.retention} disabled={busy || !!locator}
            onChange={event => edit('retention', event.target.value)}/></label>
          <button disabled={busy || !project || !authorityId || form.actions.length === 0 || !!locator}
            onClick={submit}>{t('Submit policy application')}</button>
        </div>
      </div> : <div>
        <p data-testid="policy-current-state">{t('Application outcome')}: {t(selected.request_state)} ·
          {t('Current project purpose policy')}: {t(selected.effective_status)}</p>
        <PolicyTermsSummary terms={selected.terms} approver={directory.name(authorities.find(item=>item.id===selected.authority_id)?.approver_user_id??'')} t={t}/>
        <details><summary>{t('Exact canonical policy terms')}</summary><p>{t('Terms hash')}: <code>{selected.terms_hash}</code></p>
          <pre style={{whiteSpace: 'pre-wrap', overflowWrap: 'anywhere'}}>{JSON.stringify(selected.terms, null, 2)}</pre>
        </details>
        {selected.request_state === 'submitted' && <>
          <label>{t('Decision reason')} <textarea value={reason} onChange={event => setReason(event.target.value)} maxLength={2000}/></label>
          <label><input type="checkbox" checked={confirmation} onChange={event => setConfirmation(event.target.checked)}/>
            {t('I reviewed these exact canonical terms and hash')}</label>
          <p>{t('The server verifies the current designated owner for every decision.')}</p>
          <button disabled={busy || !!locator || !confirmation || reason.trim().length < 3} onClick={() => decide('approve')}>{t('Approve exact terms')}</button>
          <button disabled={busy || !!locator || reason.trim().length < 3} onClick={() => decide('reject')}>{t('Reject application')}</button>
          <button disabled={busy || !!locator || reason.trim().length < 3}
            onClick={() => void perform(scope => controller.withdrawPolicyActivation(scope, selected.id,
              {terms_hash: selected.terms_hash, reason}))}>{t('Withdraw pending application')}</button>
        </>}
        <button disabled={busy || !!locator} onClick={() => {setSelected(null); submission.current = null; setMessage('');}}>
          {t('New policy application')}</button>
      </div>}
      <div data-testid="policy-history"><h3>{t('Policy application history')}</h3>
        {history.map(item => <p key={item.id}>
          {t(item.terms.purpose)} · {item.terms.policy_version} · {t(item.request_state)} · {t(item.effective_status)} ·
          <button disabled={busy} onClick={() => {setSelected(item); setConfirmation(false); setReason('');}}>
            {t('Inspect')} {item.id}</button>
        </p>)}
      </div>
    </>}
  </section>;
}
