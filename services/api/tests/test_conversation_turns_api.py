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
import json
import uuid
from datetime import datetime

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

# --- increment C: durable turn events, SSE stream and reconciliation -------

def events_url(turn, after=0):
    return f"{TURN_ROOT}/{turn['id']}/events?after={after}"


def parse_sse(text):
    events = []
    for block in text.strip().split('\n\n'):
        lines = [line for line in block.splitlines() if line]
        if not lines or any(line.startswith(':') for line in lines):
            continue
        record = {'event': None, 'data': None}
        for line in lines:
            if line.startswith('event: '):
                record['event'] = line[7:]
            elif line.startswith('data: '):
                record['data'] = json.loads(line[6:])
        if record['event'] and record['data'] is not None:
            events.append(record)
    return events


def seed_sales_task(dsn, thread_id, state='ready_for_review'):
    task = uuid.uuid4()
    owner = uuid.uuid5(uuid.NAMESPACE_URL, OPERATOR)
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute("INSERT INTO sales_tasks(id,workspace_id,project_id,thread_id,"
            "owner_user_id,actor_id,client_message_id,message_sequence,intent_fingerprint,"
            "skill_id,skill_version,user_message,arguments,source_refs,intake_history,"
            "state,revision,event_sequence,output_ids) VALUES(%s,%s,%s,%s,%s,%s,%s,1,%s,"
            "'understand-documents','1','reconcile fixture','{}'::jsonb,'[]'::jsonb,"
            "'[]'::jsonb,%s,1,0,'[]'::jsonb)",
            (task, WORKSPACE_A, PROJECT_A, thread_id, owner, owner, uuid.uuid4(), 'd' * 64,
             state))
    return task


def test_reconcile_unknown_then_new_evidence_and_idempotent_replays(turn_api, monkeypatch):
    """Recovery is read-only, evidence-keyed, replay-safe and can upgrade later.

    * first reconcile finds no terminal evidence -> recorded ``outcome_unknown``
      resolution, one audit row, source stays recoverable;
    * same key, equivalent new key and a different editor replay the recorded
      result with no second probe result and no extra audit row;
    * new authoritative evidence creates the next resolution, transitions the
      source turn out of ``outcome_unknown`` once and resolves to ``failed``;
    * after the terminal transition, changed evidence is 409;
    * nothing ever dispatches/reserves/receives.
    """
    client, dsn = turn_api
    from buyeros_api.services import conversation_turns as engine
    from buyeros_api.sales.turn_contracts import ExecutionOutcome
    from buyeros_api.providers import xverum_mcp

    thread = grounded_thread(client)
    created = turn_on_thread(client, thread).json()['data']
    task = seed_sales_task(dsn, created['thread']['id'], state='ready_for_review')

    async def unknown_with_task(session, scope, thread, turn, proposal):
        return ExecutionOutcome(kind='unknown', code='PROVIDER_OUTCOME_UNKNOWN',
            message='Provider response was lost; reconciliation required.', task_id=task)

    monkeypatch.setitem(engine.EXECUTORS, 'documents.read', unknown_with_task)
    monkeypatch.setattr(xverum_mcp, 'XverumTransport',
        lambda *args, **kwargs: pytest.fail('reconcile must never construct a transport'))
    current = created['thread']['version']
    unknown = decide(client, created['turn'], version=current, mutation_key='unknown-key')
    assert unknown.status_code == 200, unknown.text
    unknown_turn = unknown.json()['data']['turn']
    assert unknown_turn['status'] == 'outcome_unknown'
    url = f"{TURN_ROOT}/{unknown_turn['id']}/reconcile"

    first = client.post(url, headers=_h(OPERATOR, 'reconcile-key-a'))
    assert first.status_code == 200, first.text
    first_turn = first.json()['data']['turn']
    assert first_turn['status'] == 'outcome_unknown'
    assert 'RECONCILE_NO_EVIDENCE' in {notice['code']
        for notice in first_turn['notices']}
    same_key = client.post(url, headers=_h(OPERATOR, 'reconcile-key-a'))
    assert same_key.status_code == 200
    assert same_key.json()['data']['turn']['id'] == first_turn['id']
    equivalent = client.post(url, headers=_h(OPERATOR, 'reconcile-key-b'))
    assert equivalent.status_code == 200
    assert equivalent.json()['data']['turn']['id'] == first_turn['id']
    with psycopg.connect(dsn) as conn:
        assert conn.execute('SELECT count(*) FROM audit_events WHERE action=%s',
            ('conversation_turn.reconciled',)).fetchone()[0] == 1
        assert conn.execute('SELECT count(*) FROM conversation_turn_reconciliations'
            ).fetchone()[0] == 1
        assert conn.execute('SELECT status FROM conversation_turns WHERE id=%s',
            (unknown_turn['id'],)).fetchone()[0] == 'outcome_unknown'

    # New authoritative evidence: the persisted task now records a failure.
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute("UPDATE sales_tasks SET state='failed' WHERE id=%s", (task,))
    resolved = client.post(url, headers=_h(OPERATOR, 'reconcile-key-c'))
    assert resolved.status_code == 200, resolved.text
    resolved_turn = resolved.json()['data']['turn']
    assert resolved_turn['status'] == 'failed'
    # Reconciliation responses still return the source proposal, so the
    # read-time decision decoration is present there too.
    reconciled_proposals = proposal_parts(resolved.json()['data']['thread'])
    assert reconciled_proposals
    assert reconciled_proposals[0]['decision']['choice'] == 'approve'
    assert reconciled_proposals[0]['decision']['decided_by'] == 'you'
    assert 'RECONCILED_FAILED' in {notice['code'] for notice in resolved_turn['notices']}
    activity = next(part for part in resolved_turn['parts']
        if part['kind'] == 'tool_activity')
    assert activity['state'] == 'failed'
    # Equivalent replay (same evidence) returns the recorded terminal result.
    terminal_replay = client.post(url, headers=_h(OPERATOR, 'reconcile-key-d'))
    assert terminal_replay.status_code == 200
    assert terminal_replay.json()['data']['turn']['id'] == resolved_turn['id']
    # A different editor with the same evidence must not duplicate recovery.
    latest_thread = client.get(f"{THREAD_ROOT}/{thread['id']}", headers=_h()).json()['data']
    grant(client, dsn, latest_thread, REVIEWER, 'editor')
    other_editor = client.post(url, headers=_h(REVIEWER, 'reconcile-key-e'))
    assert other_editor.status_code == 200
    assert other_editor.json()['data']['turn']['id'] == resolved_turn['id']
    # Changed evidence after the terminal transition is a real conflict.
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute("UPDATE sales_tasks SET state='cancelled' WHERE id=%s", (task,))
    late = client.post(url, headers=_h(OPERATOR, 'reconcile-key-f'))
    assert late.status_code == 409, late.text
    assert late.json()['code'] == 'INVALID_STATE'
    with psycopg.connect(dsn) as conn:
        assert conn.execute('SELECT status FROM conversation_turns WHERE id=%s',
            (unknown_turn['id'],)).fetchone()[0] == 'failed'
        assert conn.execute('SELECT count(*) FROM sales_tasks').fetchone()[0] == 1
        assert conn.execute('SELECT count(*) FROM sales_executions').fetchone()[0] == 0
        assert conn.execute('SELECT count(*) FROM xverum_stages').fetchone()[0] == 0
        assert conn.execute('SELECT count(*) FROM xverum_tool_receipts').fetchone()[0] == 0
        assert conn.execute('SELECT count(*) FROM budget_reservations WHERE workspace_id=%s',
            (WORKSPACE_A,)).fetchone()[0] == 0
        audit_rows = conn.execute('SELECT count(*) FROM audit_events WHERE action=%s',
            ('conversation_turn.reconciled',)).fetchone()[0]
        assert audit_rows == 2  # one per effective (unique-evidence) resolution
        rows = conn.execute('SELECT evidence_seq,outcome,continuation_turn_id '
            'FROM conversation_turn_reconciliations ORDER BY evidence_seq').fetchall()
        assert [(seq, outcome) for seq, outcome, _ in rows] == [(1, 'unknown'), (2, 'failed')]
        assert rows[1][2] == uuid.UUID(resolved_turn['id'])
        events = conn.execute('SELECT seq,kind,payload FROM conversation_turn_events '
            'WHERE turn_id=%s ORDER BY seq', (resolved_turn['id'],)).fetchall()
        assert events and events[0][1] == 'turn.started'
        assert events[-1][1] == 'turn.final'
        assert events[-1][2] == {'status': 'failed'}


def test_stream_replays_ordered_events_and_reconnect_has_no_duplicates(turn_api):
    client, dsn = turn_api
    created = post_turn(client, turn_body()).json()['data']
    turn = created['turn']
    response = client.get(events_url(turn), headers=_h())
    assert response.status_code == 200, response.text
    assert response.headers['content-type'].startswith('text/event-stream')
    assert response.headers['cache-control'] == 'no-store'
    events = parse_sse(response.text)
    kinds = [event['event'] for event in events]
    seqs = [event['data']['seq'] for event in events]
    assert kinds[0] == 'turn.started' and kinds[-1] == 'turn.final'
    assert kinds.count('turn.final') == 1
    assert seqs == list(range(1, len(seqs) + 1))
    assert all(event['data']['turn_id'] == turn['id'] for event in events)
    assert events[-1]['data']['payload']['status'] == turn['status']
    replay = client.get(events_url(turn, seqs[-1]), headers=_h())
    assert replay.status_code == 200
    assert parse_sse(replay.text) == []
    with psycopg.connect(dsn) as conn:
        assert conn.execute('SELECT count(*) FROM conversation_turn_events WHERE turn_id=%s',
            (turn['id'],)).fetchone()[0] == len(events)


def test_stream_cursor_validation_and_foreign_turn(turn_api):
    client, _ = turn_api
    created = post_turn(client, turn_body()).json()['data']
    turn = created['turn']
    for cursor in ('-1', 'abc', '1.5'):
        response = client.get(events_url(turn).replace('after=0', f'after={cursor}'),
            headers=_h())
        assert response.status_code == 422, response.text
    missing = client.get(f"{TURN_ROOT}/{uuid.uuid4()}/events", headers=_h())
    assert missing.status_code == 404
    assert missing.json()['code'] == 'NOT_FOUND'


def test_reconcile_requires_an_unknown_turn(turn_api):
    client, _ = turn_api
    thread = grounded_thread(client)
    created = turn_on_thread(client, thread).json()['data']
    result = client.post(f"{TURN_ROOT}/{created['turn']['id']}/reconcile",
        headers=_h(OPERATOR, 'reconcile-invalid-state-key'))
    assert result.status_code == 409
    assert result.json()['code'] == 'INVALID_STATE'


# --- Increment 2.7: read-time decision decoration on proposal parts ---------

def proposal_parts(payload):
    return [part for message in payload.get('messages', [])
        for part in (message.get('parts') or ())
        if isinstance(part, dict) and part.get('kind') == 'proposal']


def stored_part_bodies(dsn, thread_id):
    with psycopg.connect(dsn) as conn:
        turns = conn.execute('SELECT parts FROM conversation_turns WHERE thread_id=%s '
            'ORDER BY created_at,id', (thread_id,)).fetchall()
        messages = conn.execute('SELECT parts FROM conversation_thread_messages '
            'WHERE thread_id=%s ORDER BY seq', (thread_id,)).fetchall()
    return [row[0] for row in turns], [row[0] for row in messages]


def test_proposal_decision_absent_before_decision_and_stored_parts_unchanged(turn_api):
    client, dsn = turn_api
    thread = grounded_thread(client)
    created = turn_on_thread(client, thread).json()['data']
    # Before any decision: the optional field is omitted everywhere.
    assert proposal_parts(created['thread']) and all(
        'decision' not in part for part in proposal_parts(created['thread']))
    turn_proposal = next(part for part in created['turn']['parts']
        if part['kind'] == 'proposal')
    assert 'decision' not in turn_proposal
    source_turn_id = created['turn']['id']
    with psycopg.connect(dsn) as conn:
        turn_before = conn.execute('SELECT parts FROM conversation_turns WHERE id=%s',
            (source_turn_id,)).fetchone()[0]
        messages_before = conn.execute('SELECT id,parts FROM conversation_thread_messages '
            'WHERE thread_id=%s ORDER BY seq', (thread['id'],)).fetchall()

    approved = decide(client, created['turn'], version=created['thread']['version'],
        mutation_key='decision-decoration-approve')
    assert approved.status_code == 200, approved.text
    approved_data = approved.json()['data']
    decorated = proposal_parts(approved_data['thread'])
    assert decorated, 'the source proposal part is returned on the thread'
    decision = decorated[0]['decision']
    assert decision['choice'] == 'approve'
    assert decision['decided_by'] == 'you'
    assert decision['decided_at'].endswith('+00:00')
    # Persisted decision timestamp, not request time.
    with psycopg.connect(dsn) as conn:
        persisted = conn.execute('SELECT created_at FROM conversation_turn_decisions '
            'WHERE workspace_id=%s', (WORKSPACE_A,)).fetchone()[0]
    assert datetime.fromisoformat(decision['decided_at']) == persisted
    # Read-time derivation only: stored parts are byte-for-byte unchanged.
    with psycopg.connect(dsn) as conn:
        turn_after = conn.execute('SELECT parts FROM conversation_turns WHERE id=%s',
            (source_turn_id,)).fetchone()[0]
        messages_after = {row[0]: row[1] for row in conn.execute(
            'SELECT id,parts FROM conversation_thread_messages WHERE thread_id=%s',
            (thread['id'],)).fetchall()}
    assert turn_before == turn_after, 'the source turn parts are not rewritten'
    assert all(messages_after.get(message_id) == parts for message_id, parts in messages_before)
    assert 'decision' not in str(turn_after) and 'decision' not in str(list(messages_after.values()))
    # Privacy: no raw actor id or internal reference in the payload.
    operator_id = str(uuid.uuid5(uuid.NAMESPACE_URL, OPERATOR))
    assert operator_id not in approved.text
    assert str(uuid.uuid5(uuid.NAMESPACE_URL, REVIEWER)) not in approved.text
    # Reload through the plain thread read model as well.
    reloaded = client.get(f"{THREAD_ROOT}/{thread['id']}", headers=_h()).json()['data']
    assert proposal_parts(reloaded)[0]['decision'] == decision


def test_proposal_decision_after_reject_and_coarse_label_for_other_member(turn_api):
    client, dsn = turn_api
    thread = grounded_thread(client)
    created = turn_on_thread(client, thread).json()['data']
    rejected = decide(client, created['turn'], decision='reject',
        version=created['thread']['version'], mutation_key='decision-decoration-reject')
    assert rejected.status_code == 200, rejected.text
    decision = proposal_parts(rejected.json()['data']['thread'])[0]['decision']
    assert decision['choice'] == 'reject'
    assert decision['decided_by'] == 'you'
    # A teammate sees the same persisted choice/time with a coarse actor label.
    latest = client.get(f"{THREAD_ROOT}/{thread['id']}", headers=_h()).json()['data']
    grant(client, dsn, latest, REVIEWER, 'editor')
    as_teammate = client.get(f"{THREAD_ROOT}/{thread['id']}",
        headers=_h(REVIEWER)).json()['data']
    other = proposal_parts(as_teammate)[0]['decision']
    assert other['choice'] == 'reject'
    assert other['decided_by'] == 'a workspace member'
    assert other['decided_at'] == decision['decided_at']
    assert str(uuid.uuid5(uuid.NAMESPACE_URL, OPERATOR)) not in json.dumps(other)
    # A read-only viewer sees the same persisted choice/time, coarse label only.
    current = client.get(f"{THREAD_ROOT}/{thread['id']}", headers=_h()).json()['data']
    grant(client, dsn, current, VIEWER, 'viewer')
    as_viewer = client.get(f"{THREAD_ROOT}/{thread['id']}",
        headers=_h(VIEWER)).json()['data']
    viewer_decision = proposal_parts(as_viewer)[0]['decision']
    assert viewer_decision['choice'] == 'reject'
    assert viewer_decision['decided_by'] == 'a workspace member'
    assert viewer_decision['decided_at'] == decision['decided_at']
    assert str(uuid.uuid5(uuid.NAMESPACE_URL, OPERATOR)) not in json.dumps(viewer_decision)
    assert str(uuid.uuid5(uuid.NAMESPACE_URL, VIEWER)) not in json.dumps(viewer_decision)



def test_foreign_mismatched_decision_row_never_decorates(turn_api):
    """Direct-DB mismatch must not decorate: containment is thread/turn scoped."""
    client, dsn = turn_api
    thread = grounded_thread(client)
    created = turn_on_thread(client, thread).json()['data']
    proposal = next(part for part in created['turn']['parts']
        if part['kind'] == 'proposal')
    other_thread = create_thread(client)
    operator_user = uuid.uuid5(uuid.NAMESPACE_URL, OPERATOR)
    foreign_turn = uuid.uuid4()
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute("INSERT INTO conversation_turns(id,workspace_id,project_id,thread_id,"
            "owner_user_id,actor_id,request_fingerprint,language,status,step_count,parts,notices) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,'en','needs_input',1,'[]','[]')",
            (foreign_turn, WORKSPACE_A, PROJECT_A, other_thread['id'], operator_user,
             operator_user, 'e' * 64))
        conn.execute("INSERT INTO conversation_turn_decisions(id,workspace_id,project_id,"
            "thread_id,turn_id,proposal_id,actor_id,decision,request_fingerprint,"
            "continuation_turn_id,status) VALUES(%s,%s,%s,%s,%s,%s,%s,'approve',%s,%s,'applied')",
            (uuid.uuid4(), WORKSPACE_A, PROJECT_A, other_thread['id'], foreign_turn,
             proposal['proposal_id'], operator_user, 'f' * 64, foreign_turn))
    response = client.get(f"{THREAD_ROOT}/{thread['id']}", headers=_h())
    assert response.status_code == 200, response.text
    parts = proposal_parts(response.json()['data'])
    assert parts
    assert all('decision' not in part for part in parts)
    assert str(uuid.uuid5(uuid.NAMESPACE_URL, OPERATOR)) not in response.text
