"""Authenticated HTTP + forced tenant RLS for turn-first conversation.

Fixture-only: approved offer facts and documents are seeded synthetically. No
model call, no provider call and no paid admission is enabled anywhere here.

Contract notes encoded below (Amendment A1/A2 and the turn contract):
* a thread-first turn creates the discussion with NO selected source, so it is
  honestly ``needs_input`` with a ``SOURCES_REQUIRED`` notice — not
  ``needs_approval``; citations/proposals require an explicit source selection;
* a replayed ``client_message_id`` returns the recorded turn (200) before the
  thread-version precondition, which is the intended idempotent-retry contract;
* inline proposals always require a separate authenticated decision.
"""
import uuid

import psycopg
import pytest
from psycopg.types.json import Jsonb

from buyeros_api.db.icp import canonical_hash
from buyeros_api.services.conversation_reply import reply_from_grounding
from tests.icp_fixtures import FACT_ID, valid_icp_payload
from tests.test_buyer_review_db import (_seed_buyer, api, _h, OPERATOR, REVIEWER, VIEWER, ADMIN,
    WORKSPACE_A, WORKSPACE_B, PROJECT_A, PROJECT_B)
from tests.test_conversation_threads_api import BODY as THREAD_BODY, ROOT as THREAD_ROOT, \
    create as create_thread, grant, member, headers as thread_headers

PROFILE = 'c5000000-0000-4000-8000-000000000001'
DOCUMENT = 'c3000000-0000-4000-8000-000000000001'
FACT_SOURCE = f'fact:profile:{PROFILE}:{FACT_ID}'
DOCUMENT_SOURCE = f'document:{DOCUMENT}'
TURN_ROOT = f'/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/conversation-turns'


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setenv('NEXT_PUBLIC_CONVERSATION_HOME', 'true')
    monkeypatch.setenv('BUYEROS_SALES_SKILLS_ENABLED', 'true')
    monkeypatch.setenv('BUYEROS_SALES_WORKSPACE_IDS', WORKSPACE_A)


@pytest.fixture
def turn_api(enabled, api, seeded):
    content = valid_icp_payload()
    content['offer_document_ids'] = [DOCUMENT]
    fact = content['offer_facts'][0]
    fact.update(provenance='document_excerpt', source_document_id=DOCUMENT,
                excerpt='Approved source excerpt')
    with psycopg.connect(seeded, autocommit=True) as conn:
        conn.execute("INSERT INTO offer_documents(id,workspace_id,project_id,kind,filename,"
            "media_type,status,sha256,retention_until,fact_candidates) VALUES(%s,%s,%s,'upload',"
            "'private.txt','text/plain','ready',%s,now()+interval '1 day',%s)",
            (DOCUMENT, WORKSPACE_A, PROJECT_A, 'a' * 64, Jsonb([fact])))
        conn.execute("INSERT INTO icp_versions(id,workspace_id,project_id,number,"
            "basis_offer_revision,content,content_hash,approved_by,approved_at) "
            "VALUES(%s,%s,%s,1,1,%s,%s,%s,now())",
            (PROFILE, WORKSPACE_A, PROJECT_A, Jsonb(content), canonical_hash(content),
             uuid.uuid5(uuid.NAMESPACE_URL, ADMIN)))
        conn.execute('UPDATE projects SET active_icp_version_id=%s WHERE id=%s',
            (PROFILE, PROJECT_A))
    yield api, seeded
    with psycopg.connect(seeded, autocommit=True) as conn:
        # Discussions must be removed before the shared fixture deletes users;
        # cover both seeded workspaces in case a test touched project B.
        conn.execute("UPDATE sales_tasks SET state='cancelled' WHERE workspace_id IN (%s,%s)",
            (WORKSPACE_A, WORKSPACE_B))
        conn.execute('DELETE FROM conversation_threads WHERE workspace_id IN (%s,%s)',
            (WORKSPACE_A, WORKSPACE_B))


def key(prefix='turn'):
    return f'{prefix}-{uuid.uuid4().hex[:16]}'


def turn_body(**changes):
    values = {'client_message_id': str(uuid.uuid4()), 'language': 'en',
              'text': 'Summarise the selected documents',
              'skill_id': 'understand-documents', 'template_id': 'understand-documents'}
    values.update(changes)
    return values


def post_turn(client, body=None, *, subject=OPERATOR, version=None, mutation_key=None):
    headers = dict(_h(subject, mutation_key or key()))
    if version is not None:
        headers['If-Match'] = f'"{version}"'
    return client.post(TURN_ROOT, headers=headers, json=body or turn_body())


def grounded_thread(client):
    """Existing discussion with one reviewer-approved document selected.

    Turn-first discussions intentionally start without a source selection, so
    citations and inline proposals need this explicit step (Amendment A1 keeps
    ``POST /conversation-threads`` valid for that purpose).
    """
    return create_thread(client, sources=[{'id': DOCUMENT_SOURCE, 'label': 'Offer document'}])


def turn_on_thread(client, thread, *, subject=OPERATOR, version=None, mutation_key=None,
                   **changes):
    body = {**turn_body(**changes), 'thread_id': thread['id']}
    return post_turn(client, body, subject=subject,
        version=thread['version'] if version is None else version,
        mutation_key=mutation_key)


def proposal_of(turn):
    return next(part for part in turn['parts'] if part['kind'] == 'proposal')


def decide(client, turn, decision='approve', *, subject=OPERATOR, version,
           mutation_key=None, proposal_id=None):
    proposal = proposal_of(turn)
    return client.post(f"{TURN_ROOT}/{turn['id']}/decisions",
        headers={**_h(subject, mutation_key or key('decision')),
                  'If-Match': f'"{version}"'},
        json={'proposal_id': proposal_id or proposal['proposal_id'],
              'decision': decision, 'expected_thread_version': version})


def cancel(client, turn, *, subject=OPERATOR, version, mutation_key=None):
    return client.post(f"{TURN_ROOT}/{turn['id']}/cancel",
        headers={**_h(subject, mutation_key or key('cancel')),
                  'If-Match': f'"{version}"'})


def fact_role(conn):
    return conn.execute('SELECT count(*) FROM conversation_threads').fetchone()[0]


def test_thread_first_turn_creates_thread_and_user_message_atomically(turn_api):
    """Amendment A1: thread + first user message are created in one transaction.

    A new discussion has no selected source yet, so the honest status is
    ``needs_input`` with a SOURCES_REQUIRED notice (no citations/proposal).
    """
    client, dsn = turn_api
    body = turn_body()
    result = post_turn(client, body)
    assert result.status_code == 200, result.text
    data = result.json()['data']
    thread, turn = data['thread'], data['turn']
    assert thread['access'] == 'owner' and thread['buyerId'] is None
    assert thread['title'] == 'Summarise the selected documents'
    assert turn['status'] == 'needs_input'
    assert [part['kind'] for part in turn['parts']] == ['text']
    assert 'SOURCES_REQUIRED' in {notice['code'] for notice in turn['notices']}
    citations = [part for part in turn['parts'] if part['kind'] == 'citations']
    assert citations == []
    assert [message['role'] for message in thread['messages']] == ['user', 'assistant']
    assert thread['messages'][0]['client_message_id'] == body['client_message_id']
    assert thread['messages'][0]['seq'] == 1 and thread['messages'][1]['seq'] == 2
    assert 'parts' not in thread['messages'][0]
    assert [part['kind'] for part in thread['messages'][1]['parts']] == ['text']
    with psycopg.connect(dsn) as conn:
        assert fact_role(conn) == 1
        assert conn.execute('SELECT count(*) FROM conversation_turns').fetchone()[0] == 1
        assert conn.execute('SELECT count(*) FROM conversation_thread_messages').fetchone()[0] == 2
        assert conn.execute('SELECT count(*) FROM sales_tasks').fetchone()[0] == 0


def test_duplicate_client_message_id_replays_without_second_thread_or_execution(turn_api):
    client, dsn = turn_api
    body = turn_body()
    first = post_turn(client, body, mutation_key='turn-first-key')
    assert first.status_code == 200, first.text
    turn, thread = first.json()['data']['turn'], first.json()['data']['thread']

    replay = post_turn(client, body, mutation_key='turn-other-key')
    assert replay.status_code == 200
    assert replay.json()['data']['turn']['id'] == turn['id']
    assert replay.json()['data']['thread']['id'] == thread['id']

    # Receipt expiry must not re-open the append: the durable client identity wins.
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute("DELETE FROM idempotency_records WHERE operation_id='conversationTurn'")
    third = post_turn(client, body, mutation_key='turn-third-key')
    assert third.status_code == 200
    assert third.json()['data']['turn']['id'] == turn['id']
    with psycopg.connect(dsn) as conn:
        assert fact_role(conn) == 1
        assert conn.execute('SELECT count(*) FROM conversation_turns').fetchone()[0] == 1
        assert conn.execute('SELECT count(*) FROM conversation_thread_messages').fetchone()[0] == 2

    conflicting = post_turn(client, {**body, 'text': 'A different request'},
        mutation_key='turn-conflict-key')
    assert conflicting.status_code == 409
    assert conflicting.json()['code'] == 'IDEMPOTENCY_CONFLICT'


def test_existing_thread_requires_current_version_and_edit_access(turn_api):
    client, dsn = turn_api
    thread = grounded_thread(client)
    assert thread['version'] == 1
    # Existing discussion without If-Match: the strong native precondition is required.
    missing = post_turn(client, {**turn_body(), 'thread_id': thread['id']})
    assert missing.status_code == 400 and missing.json()['code'] == 'INVALID_REQUEST'
    stale = post_turn(client, {**turn_body(), 'thread_id': thread['id']}, version=2)
    assert stale.status_code == 409 and stale.json()['code'] == 'STALE_REVISION'
    mismatch = post_turn(client, {**turn_body(), 'thread_id': thread['id'],
        'expected_thread_version': 3}, version=2)
    assert mismatch.status_code == 422
    accepted = post_turn(client, {**turn_body(), 'thread_id': thread['id']}, version=1)
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()['data']['thread']['version'] == 2
    # A viewer or an unshared member never reaches the turn: recovered current ACL only.
    assert post_turn(client, {**turn_body(), 'thread_id': thread['id']},
        subject=VIEWER, version=2).status_code == 404
    foreign = client.post(TURN_ROOT.replace(WORKSPACE_A, WORKSPACE_B).replace(PROJECT_A, PROJECT_B),
        headers=dict(_h(OPERATOR, key())), json=turn_body())
    assert foreign.status_code == 404
    with psycopg.connect(dsn) as conn:
        assert fact_role(conn) == 1


def test_inline_approval_is_required_and_then_uses_the_typed_output_path(turn_api):
    client, dsn = turn_api
    thread = grounded_thread(client)
    base = thread['version']
    created = turn_on_thread(client, thread).json()['data']
    turn, current_thread = created['turn'], created['thread']
    current = current_thread['version']
    assert current == base + 1
    with psycopg.connect(dsn) as conn:
        assert conn.execute('SELECT count(*) FROM sales_tasks').fetchone()[0] == 0
        assert conn.execute('SELECT count(*) FROM sales_outputs').fetchone()[0] == 0
    approved = decide(client, turn, version=current, mutation_key='approve-stale-replay-key')
    assert approved.status_code == 200, approved.text
    data = approved.json()['data']
    continuation, new_thread = data['turn'], data['thread']
    assert continuation['status'] == 'completed'
    kinds = [part['kind'] for part in continuation['parts']]
    assert 'tool_activity' in kinds and 'output_link' in kinds
    activity = next(part for part in continuation['parts'] if part['kind'] == 'tool_activity')
    assert activity['state'] == 'completed'
    link = next(part for part in continuation['parts'] if part['kind'] == 'output_link')
    assert link['output']['status'] == 'available'
    assert new_thread['version'] == current + 2
    # Same key AND the same expected version sent originally: the recorded
    # continuation must be replayed, not rejected with STALE_REVISION even
    # though the first commit advanced thread.version (BLOCKER-1 contract).
    replay = decide(client, turn, version=current, mutation_key='approve-stale-replay-key')
    assert replay.status_code == 200, replay.text
    assert replay.json()['data']['turn']['id'] == continuation['id']
    # New key, stale version: the durable decision row replays too.
    new_key = decide(client, turn, version=base, mutation_key='decision-replay-key')
    assert new_key.status_code == 200
    assert new_key.json()['data']['turn']['id'] == continuation['id']
    with psycopg.connect(dsn) as conn:
        # One durable task, one reviewed revision, exactly one decision; no provider work.
        assert conn.execute('SELECT count(*) FROM sales_tasks').fetchone()[0] == 1
        assert conn.execute('SELECT skill_id FROM sales_tasks').fetchone()[0] == 'understand-documents'
        assert conn.execute('SELECT count(*) FROM sales_outputs').fetchone()[0] == 1
        assert conn.execute('SELECT count(*) FROM conversation_turn_decisions').fetchone()[0] == 1
        assert conn.execute("SELECT status FROM conversation_turn_proposals").fetchone()[0] == 'executed'
        assert conn.execute('SELECT count(*) FROM xverum_stages').fetchone()[0] == 0
        assert conn.execute('SELECT count(*) FROM budget_reservations WHERE workspace_id=%s',
            (WORKSPACE_A,)).fetchone()[0] == 0
    reloaded = client.get(f"{THREAD_ROOT}/{thread['id']}", headers=_h()).json()['data']
    assistant = [message for message in reloaded['messages'] if message['role'] == 'assistant']
    assert [part['kind'] for part in assistant[-1]['parts']] == kinds
    rejected = decide(client, turn, decision='reject', version=base)
    assert rejected.status_code == 409 and rejected.json()['code'] == 'ALREADY_DECIDED'


def test_rejection_executes_nothing_and_is_safe_to_replay(turn_api):
    client, dsn = turn_api
    thread = grounded_thread(client)
    created = turn_on_thread(client, thread).json()['data']
    current = created['thread']['version']
    rejected = decide(client, created['turn'], decision='reject', version=current)
    assert rejected.status_code == 200, rejected.text
    turn = rejected.json()['data']['turn']
    assert turn['status'] == 'completed'
    assert 'PROPOSAL_REJECTED' in {notice['code'] for notice in turn['notices']}
    activity = next(part for part in turn['parts'] if part['kind'] == 'tool_activity')
    assert activity['state'] == 'skipped'
    # Replay with a stale version and a new key: the durable decision row wins.
    replay = decide(client, created['turn'], decision='reject', version=current,
        mutation_key='reject-replay-key')
    assert replay.status_code == 200
    assert replay.json()['data']['turn']['id'] == turn['id']
    with psycopg.connect(dsn) as conn:
        assert conn.execute('SELECT count(*) FROM sales_tasks').fetchone()[0] == 0
        assert conn.execute('SELECT count(*) FROM sales_outputs').fetchone()[0] == 0
        assert conn.execute('SELECT status FROM conversation_turn_proposals').fetchone()[0] == 'rejected'


def test_disabled_admission_returns_notice_and_executes_nothing_then_can_resume(turn_api, monkeypatch):
    client, dsn = turn_api
    thread = grounded_thread(client)
    created = turn_on_thread(client, thread).json()['data']
    current = created['thread']['version']
    monkeypatch.setenv('BUYEROS_SALES_SKILLS_ENABLED', 'false')
    blocked = decide(client, created['turn'], version=current)
    assert blocked.status_code == 200, blocked.text
    data = blocked.json()['data']
    assert data['turn']['status'] == 'needs_input'
    assert 'SALES_ADMISSION_DISABLED' in {notice['code'] for notice in data['turn']['notices']}
    with psycopg.connect(dsn) as conn:
        assert conn.execute('SELECT count(*) FROM sales_tasks').fetchone()[0] == 0
        assert conn.execute('SELECT count(*) FROM conversation_turn_decisions').fetchone()[0] == 0
        assert conn.execute('SELECT status FROM conversation_turn_proposals').fetchone()[0] == 'proposed'
    monkeypatch.setenv('BUYEROS_SALES_SKILLS_ENABLED', 'true')
    resumed = decide(client, created['turn'], version=data['thread']['version'])
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()['data']['turn']['status'] == 'completed'
    with psycopg.connect(dsn) as conn:
        assert conn.execute('SELECT count(*) FROM sales_tasks').fetchone()[0] == 1


def test_unknown_outcome_is_persisted_retained_and_never_retried(turn_api, monkeypatch):
    client, dsn = turn_api
    from buyeros_api.services import conversation_turns as engine
    from buyeros_api.sales.turn_contracts import ExecutionOutcome

    async def uncertain(session, scope, thread, turn, proposal):
        return ExecutionOutcome(kind='unknown', code='PROVIDER_OUTCOME_UNKNOWN',
            message='The execution outcome is unknown; reconciliation is required.')

    monkeypatch.setitem(engine.EXECUTORS, 'documents.read', uncertain)
    thread = grounded_thread(client)
    created = turn_on_thread(client, thread).json()['data']
    current = created['thread']['version']
    result = decide(client, created['turn'], version=current)
    assert result.status_code == 200, result.text
    turn = result.json()['data']['turn']
    assert turn['status'] == 'outcome_unknown'
    activity = next(part for part in turn['parts'] if part['kind'] == 'tool_activity')
    assert activity['state'] == 'outcome_unknown'
    replay = decide(client, created['turn'], version=current,
        mutation_key='unknown-replay-key')
    assert replay.status_code == 200
    assert replay.json()['data']['turn']['id'] == turn['id']
    reloaded = client.get(f"{THREAD_ROOT}/{thread['id']}", headers=_h()).json()['data']
    last = [message for message in reloaded['messages'] if message['role'] == 'assistant'][-1]
    assert last['parts'][0]['state'] == 'outcome_unknown'
    with psycopg.connect(dsn) as conn:
        assert conn.execute('SELECT status FROM conversation_turn_proposals').fetchone()[0] == 'outcome_unknown'
        assert conn.execute('SELECT count(*) FROM sales_tasks').fetchone()[0] == 0


def test_share_revocation_and_non_member_decisions_are_denied(turn_api):
    client, dsn = turn_api
    thread = grounded_thread(client)
    created = turn_on_thread(client, thread).json()['data']
    # Share after the turn, then revoke: current ACL is re-read for every call.
    shared = grant(client, dsn, created['thread'], REVIEWER, 'editor')
    revoked = client.delete(f"{THREAD_ROOT}/{thread['id']}/shares/{member(dsn, REVIEWER)}",
        headers=thread_headers(version=shared['version']))
    assert revoked.status_code == 200, revoked.text
    current = revoked.json()['data']['version']
    denied = decide(client, created['turn'], subject=REVIEWER, version=current)
    assert denied.status_code == 404, denied.text
    assert post_turn(client, {**turn_body(), 'thread_id': thread['id']},
        subject=REVIEWER, version=current).status_code == 404
    # Non-member workspace/project stays a 404 with no existence leak.
    foreign = client.post(
        TURN_ROOT.replace(WORKSPACE_A, WORKSPACE_B).replace(PROJECT_A, PROJECT_B),
        headers=dict(_h(OPERATOR, key())), json=turn_body())
    assert foreign.status_code == 404
    with psycopg.connect(dsn) as conn:
        assert conn.execute('SELECT count(*) FROM sales_tasks').fetchone()[0] == 0


def test_cancel_stops_undispatched_step_and_replays_idempotently(turn_api):
    client, dsn = turn_api
    thread = grounded_thread(client)
    created = turn_on_thread(client, thread).json()['data']
    current = created['thread']['version']
    cancelled = cancel(client, created['turn'], version=current, mutation_key='cancel-key')
    assert cancelled.status_code == 200, cancelled.text
    turn = cancelled.json()['data']['turn']
    assert turn['status'] == 'cancelled'
    assert 'TURN_CANCELLED' in {notice['code'] for notice in turn['notices']}
    activity = next(part for part in turn['parts'] if part['kind'] == 'tool_activity')
    assert activity['state'] == 'skipped'
    # Same key and stale expected version replay the recorded cancellation.
    replay = cancel(client, created['turn'], version=current, mutation_key='cancel-key')
    assert replay.status_code == 200
    assert replay.json()['data']['turn']['id'] == turn['id']
    with psycopg.connect(dsn) as conn:
        assert conn.execute('SELECT count(*) FROM sales_tasks').fetchone()[0] == 0
        assert conn.execute('SELECT status FROM conversation_turn_proposals').fetchone()[0] == 'cancelled'
        assert conn.execute('SELECT count(*) FROM conversation_turns').fetchone()[0] == 2


def test_fixture_adapter_answer_is_validated_and_persists_only_selected_citations(
        turn_api, monkeypatch):
    client, _ = turn_api
    from buyeros_api.services import conversation_turns as engine

    captured = {}

    def fixture_adapter(grounding):
        captured['refs'] = [item['id'] for item in grounding.citations]
        return reply_from_grounding(grounding, fixture_candidate={
            'text': 'Review the cited approved offer source.', 'status': 'needs_review',
            'fixture': True, 'citations': list(grounding.citations)})

    monkeypatch.setattr(engine, 'model_answer', fixture_adapter)
    thread = grounded_thread(client)
    result = turn_on_thread(client, thread)
    assert result.status_code == 200, result.text
    turn = result.json()['data']['turn']
    assert captured['refs'] == [DOCUMENT_SOURCE]
    assert turn['parts'][0]['text'] == 'Review the cited approved offer source.'
    assert 'CONVERSATION_MODEL_UNAVAILABLE' not in {notice['code'] for notice in turn['notices']}
    assert 'Approved source excerpt' not in result.text


def test_executor_failure_after_partial_write_is_terminal_and_not_replayable(turn_api, monkeypatch):
    """Blocker-2 regression: a failed executor must record the decision.

    The fixture adapter performs one real typed step (a durable sales task) and
    then raises. The proposal must become terminal, the decision must be
    recorded, and the failed turn must be durably replayed — never leave the
    proposal open with a committed task behind it.
    """
    client, dsn = turn_api
    from buyeros_api.services import conversation_turns as engine
    from buyeros_api.sales.contracts import SourceRef, TaskInput

    async def partial_then_fail(session, scope, thread, turn, proposal):
        from buyeros_api.services.sales_tasks import create_task
        await create_task(session, scope, TaskInput(
            thread_id=proposal.thread_id, skill_id=proposal.skill_id,
            skill_version=proposal.skill_version, user_message='PARTIAL_FAIL_SENTINEL',
            source_refs=tuple(SourceRef.model_validate(ref) for ref in proposal.source_refs),
            arguments=proposal.arguments), 'partial-failure-task-key', thread.version)
        raise ValueError('synthetic post-admission failure')

    monkeypatch.setitem(engine.EXECUTORS, 'documents.read', partial_then_fail)
    thread = grounded_thread(client)
    created = turn_on_thread(client, thread).json()['data']
    current = created['thread']['version']
    failed = decide(client, created['turn'], version=current,
        mutation_key='partial-failure-approve')
    assert failed.status_code == 200, failed.text
    continuation = failed.json()['data']['turn']
    assert continuation['status'] == 'failed'
    activity = next(part for part in continuation['parts'] if part['kind'] == 'tool_activity')
    assert activity['state'] == 'failed'
    again = decide(client, created['turn'], version=current,
        mutation_key='partial-failure-second-approve')
    assert again.status_code == 200
    assert again.json()['data']['turn']['id'] == continuation['id']  # durable replay
    different = decide(client, created['turn'], decision='reject', version=current,
        mutation_key='partial-failure-different-decision')
    assert different.status_code == 409 and different.json()['code'] == 'ALREADY_DECIDED'
    with psycopg.connect(dsn) as conn:
        assert conn.execute('SELECT status FROM conversation_turn_proposals').fetchone()[0] == 'failed'
        assert conn.execute('SELECT count(*) FROM conversation_turn_decisions').fetchone()[0] == 1
        assert conn.execute('SELECT count(*) FROM sales_tasks').fetchone()[0] == 1


# --- task-6: durable buyer link + proposal-only approved MCP capabilities ---

def test_buyer_link_grounds_turn_and_proposes_proposal_only_enrichment(turn_api, monkeypatch):
    client, dsn = turn_api
    buyer = _seed_buyer(dsn, name='DeltaGrid')
    body = turn_body(buyer_id=buyer, text='Enrich the linked company',
                     skill_id='sales-contacts')
    result = post_turn(client, body)
    assert result.status_code == 200, result.text
    data = result.json()['data']
    thread, turn = data['thread'], data['turn']
    assert thread['buyerId'] == buyer
    # Inspect every citations part (the linked buyer must be a buyer citation,
    # alongside any other legitimately grounded project sources).
    citation_items = [item for part in turn['parts']
        if part['kind'] == 'citations' for item in part['items']]
    assert f'buyer:{buyer}' in {item['id'] for item in citation_items}
    assert 'buyer' in {item['kind'] for item in citation_items}
    assert {item['kind'] for item in citation_items} <= {'buyer', 'document'}
    assert all(item['id'] == DOCUMENT_SOURCE for item in citation_items
        if item['kind'] == 'document')
    proposal = next(part for part in turn['parts'] if part['kind'] == 'proposal')
    assert proposal['capability'] == 'xverum.enrich_company'
    assert proposal['requires_approval'] is True
    assert proposal['cost']['kind'] == 'provider_credits'
    assert proposal['cost']['unit'] == 'credits'
    assert proposal['cost']['may_incur_provider_charges'] is True
    assert proposal['cost']['known'] is False
    with psycopg.connect(dsn) as conn:
        assert conn.execute('SELECT buyer_id FROM conversation_threads WHERE id=%s',
            (thread['id'],)).fetchone()[0] == uuid.UUID(buyer)
        assert conn.execute('SELECT count(*) FROM sales_tasks').fetchone()[0] == 0
    from buyeros_api.providers import xverum_mcp
    monkeypatch.setattr(xverum_mcp, 'XverumTransport',
        lambda *args, **kwargs: pytest.fail('provider transport must never be constructed'))
    approved = decide(client, turn, version=thread['version'],
        mutation_key='enrichment-approve-key')
    assert approved.status_code == 200, approved.text
    continuation = approved.json()['data']['turn']
    assert continuation['status'] == 'failed'
    codes = {notice['code'] for notice in continuation['notices']}
    assert codes & {'PAID_ADMISSION_DISABLED', 'EXECUTION_RUNTIME_REQUIRED',
                    'XVERUM_NOT_CONFIGURED', 'XVERUM_DISPATCH_NOT_ENABLED',
                    'SALES_ADMISSION_DISABLED'}
    activity = next(part for part in continuation['parts'] if part['kind'] == 'tool_activity')
    assert activity['state'] == 'failed'
    with psycopg.connect(dsn) as conn:
        assert conn.execute('SELECT status FROM conversation_turn_proposals').fetchone()[0] == 'failed'
        assert conn.execute('SELECT count(*) FROM conversation_turn_decisions').fetchone()[0] == 1
        assert conn.execute('SELECT count(*) FROM xverum_stages').fetchone()[0] == 0
        assert conn.execute('SELECT count(*) FROM xverum_tool_receipts').fetchone()[0] == 0
        assert conn.execute('SELECT count(*) FROM budget_reservations WHERE workspace_id=%s',
            (WORKSPACE_A,)).fetchone()[0] == 0
    replay = decide(client, turn, version=thread['version'],
        mutation_key='enrichment-approve-replay')
    assert replay.status_code == 200
    assert replay.json()['data']['turn']['id'] == continuation['id']


def test_buyer_link_rejects_unknown_and_foreign_ids(turn_api):
    client, dsn = turn_api
    unknown = post_turn(client, turn_body(buyer_id=str(uuid.uuid4())))
    assert unknown.status_code == 404 and unknown.json()['code'] == 'NOT_FOUND'
    # A canonical buyer from another workspace/project is not linkable.
    company, foreign_buyer = uuid.uuid4(), uuid.uuid4()
    with psycopg.connect(dsn) as conn:
        conn.execute("INSERT INTO companies(id,workspace_id,legal_name,display_name) "
            "VALUES(%s,%s,'B Co','B Co')", (company, WORKSPACE_B))
        conn.execute("INSERT INTO project_buyers(id,workspace_id,project_id,company_id) "
            "VALUES(%s,%s,%s,%s)", (foreign_buyer, WORKSPACE_B, PROJECT_B, company))
    foreign = post_turn(client, turn_body(buyer_id=str(foreign_buyer)))
    assert foreign.status_code == 404
    with psycopg.connect(dsn) as conn:
        assert conn.execute('SELECT count(*) FROM conversation_threads').fetchone()[0] == 0


def test_existing_thread_company_link_cannot_be_repointed(turn_api):
    client, dsn = turn_api
    buyer = _seed_buyer(dsn, name='LinkGuard')
    thread = grounded_thread(client)
    mismatch = post_turn(client, {**turn_body(buyer_id=buyer), 'thread_id': thread['id']},
        version=thread['version'])
    assert mismatch.status_code == 409
    assert mismatch.json()['code'] == 'BUYER_LINK_MISMATCH'
    with psycopg.connect(dsn) as conn:
        assert conn.execute('SELECT buyer_id FROM conversation_threads WHERE id=%s',
            (thread['id'],)).fetchone()[0] is None
        assert conn.execute('SELECT count(*) FROM conversation_thread_messages').fetchone()[0] == 1
