"""Authenticated HTTP + forced tenant RLS for turn-first conversation.

Fixture-only: approved offer facts and documents are seeded synthetically. No
model call, no provider call and no paid admission is enabled anywhere here.
"""
import uuid

import psycopg
import pytest
from psycopg.types.json import Jsonb

from buyeros_api.db.icp import canonical_hash
from buyeros_api.services.conversation_reply import reply_from_grounding
from tests.icp_fixtures import FACT_ID, valid_icp_payload
from tests.test_buyer_review_db import (api, _h, OPERATOR, REVIEWER, VIEWER, ADMIN,
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
        conn.execute("UPDATE sales_tasks SET state='cancelled' WHERE workspace_id=%s",
            (WORKSPACE_A,))
        conn.execute('DELETE FROM conversation_threads WHERE workspace_id=%s', (WORKSPACE_A,))


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


def proposal_of(turn):
    return next(part for part in turn['parts'] if part['kind'] == 'proposal')


def decide(client, turn, decision='approve', *, subject=OPERATOR, version=None,
           mutation_key=None, proposal_id=None):
    proposal = proposal_of(turn)
    return client.post(f"{TURN_ROOT}/{turn['id']}/decisions",
        headers={**_h(subject, mutation_key or key('decision')),
                  'If-Match': f'"{version or 2}"'},
        json={'proposal_id': proposal_id or proposal['proposal_id'],
              'decision': decision, 'expected_thread_version': version or 2})


def cancel(client, turn, *, subject=OPERATOR, version=2, mutation_key=None):
    return client.post(f"{TURN_ROOT}/{turn['id']}/cancel",
        headers={**_h(subject, mutation_key or key('cancel')),
                  'If-Match': f'"{version}"'})


def fact_role(conn):
    return conn.execute('SELECT count(*) FROM conversation_threads').fetchone()[0]


def test_thread_first_turn_creates_thread_and_user_message_atomically(turn_api):
    client, dsn = turn_api
    body = turn_body()
    result = post_turn(client, body)
    assert result.status_code == 200, result.text
    data = result.json()['data']
    thread, turn = data['thread'], data['turn']
    assert thread['access'] == 'owner'
    assert thread['title'] == 'Summarise the selected documents'
    assert turn['status'] == 'needs_approval'
    kinds = [part['kind'] for part in turn['parts']]
    assert kinds[:2] == ['text', 'citations'] and 'proposal' in kinds
    assert [item['id'] for item in turn['parts'][1]['items']] == [DOCUMENT_SOURCE]
    assert [message['role'] for message in thread['messages']] == ['user', 'assistant']
    assert thread['messages'][0]['client_message_id'] == body['client_message_id']
    assert thread['messages'][0]['seq'] == 1 and thread['messages'][1]['seq'] == 2
    assert 'parts' not in thread['messages'][0]
    assert [part['kind'] for part in thread['messages'][1]['parts']] == kinds
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
    thread = create_thread(client, sources=[{'id': DOCUMENT_SOURCE, 'label': 'Offer document'}])
    assert thread['version'] == 1
    missing = post_turn(client, turn_body())
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
    body = turn_body()
    created = post_turn(client, body).json()['data']
    turn, thread = created['turn'], created['thread']
    with psycopg.connect(dsn) as conn:
        assert conn.execute('SELECT count(*) FROM sales_tasks').fetchone()[0] == 0
        assert conn.execute('SELECT count(*) FROM sales_outputs').fetchone()[0] == 0
    approved = decide(client, turn, version=thread['version'])
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
    assert new_thread['version'] == thread['version'] + 2
    replay = decide(client, turn, version=thread['version'], mutation_key='decision-replay-key')
    assert replay.status_code == 200
    assert replay.json()['data']['turn']['id'] == continuation['id']
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
    rejected = decide(client, turn, decision='reject', version=thread['version'])
    assert rejected.status_code == 409 and rejected.json()['code'] == 'ALREADY_DECIDED'


def test_rejection_executes_nothing_and_is_safe_to_replay(turn_api):
    client, dsn = turn_api
    created = post_turn(client, turn_body()).json()['data']
    rejected = decide(client, created['turn'], decision='reject', version=created['thread']['version'])
    assert rejected.status_code == 200, rejected.text
    turn = rejected.json()['data']['turn']
    assert turn['status'] == 'completed'
    assert 'PROPOSAL_REJECTED' in {notice['code'] for notice in turn['notices']}
    activity = next(part for part in turn['parts'] if part['kind'] == 'tool_activity')
    assert activity['state'] == 'skipped'
    replay = decide(client, created['turn'], decision='reject',
        version=created['thread']['version'], mutation_key='reject-replay-key')
    assert replay.status_code == 200
    assert replay.json()['data']['turn']['id'] == turn['id']
    with psycopg.connect(dsn) as conn:
        assert conn.execute('SELECT count(*) FROM sales_tasks').fetchone()[0] == 0
        assert conn.execute('SELECT count(*) FROM sales_outputs').fetchone()[0] == 0
        assert conn.execute('SELECT status FROM conversation_turn_proposals').fetchone()[0] == 'rejected'


def test_disabled_admission_returns_notice_and_executes_nothing_then_can_resume(turn_api, monkeypatch):
    client, dsn = turn_api
    created = post_turn(client, turn_body()).json()['data']
    turn, thread = created['turn'], created['thread']
    monkeypatch.setenv('BUYEROS_SALES_SKILLS_ENABLED', 'false')
    blocked = decide(client, turn, version=thread['version'])
    assert blocked.status_code == 200, blocked.text
    data = blocked.json()['data']
    assert data['turn']['status'] == 'needs_input'
    assert 'SALES_ADMISSION_DISABLED' in {notice['code'] for notice in data['turn']['notices']}
    with psycopg.connect(dsn) as conn:
        assert conn.execute('SELECT count(*) FROM sales_tasks').fetchone()[0] == 0
        assert conn.execute('SELECT count(*) FROM conversation_turn_decisions').fetchone()[0] == 0
        assert conn.execute('SELECT status FROM conversation_turn_proposals').fetchone()[0] == 'proposed'
    monkeypatch.setenv('BUYEROS_SALES_SKILLS_ENABLED', 'true')
    resumed = decide(client, turn, version=data['thread']['version'])
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
    created = post_turn(client, turn_body()).json()['data']
    result = decide(client, created['turn'], version=created['thread']['version'])
    assert result.status_code == 200, result.text
    turn = result.json()['data']['turn']
    assert turn['status'] == 'outcome_unknown'
    activity = next(part for part in turn['parts'] if part['kind'] == 'tool_activity')
    assert activity['state'] == 'outcome_unknown'
    replay = decide(client, created['turn'], version=created['thread']['version'],
        mutation_key='unknown-replay-key')
    assert replay.status_code == 200
    assert replay.json()['data']['turn']['id'] == turn['id']
    reloaded = client.get(f"{THREAD_ROOT}/{created['thread']['id']}", headers=_h()).json()['data']
    last = [message for message in reloaded['messages'] if message['role'] == 'assistant'][-1]
    assert last['parts'][0]['state'] == 'outcome_unknown'
    with psycopg.connect(dsn) as conn:
        assert conn.execute('SELECT status FROM conversation_turn_proposals').fetchone()[0] == 'outcome_unknown'
        assert conn.execute('SELECT count(*) FROM sales_tasks').fetchone()[0] == 0


def test_share_revocation_and_non_member_decisions_are_denied(turn_api):
    client, dsn = turn_api
    thread = grant(client, dsn, create_thread(client,
        sources=[{'id': DOCUMENT_SOURCE, 'label': 'Offer document'}]), REVIEWER, 'editor')
    created = post_turn(client, {**turn_body(), 'thread_id': thread['id']},
        subject=REVIEWER, version=thread['version']).json()['data']
    assert created['thread']['version'] == thread['version'] + 1
    revoked = client.delete(f"{THREAD_ROOT}/{thread['id']}/shares/{member(dsn, REVIEWER)}",
        headers=thread_headers(version=created['thread']['version']))
    assert revoked.status_code == 200, revoked.text
    current = revoked.json()['data']['version']
    denied = decide(client, created['turn'], subject=REVIEWER, version=current)
    assert denied.status_code == 404
    assert post_turn(client, {**turn_body(), 'thread_id': thread['id']},
        subject=REVIEWER, version=current).status_code == 404
    with psycopg.connect(dsn) as conn:
        assert conn.execute('SELECT count(*) FROM sales_tasks').fetchone()[0] == 0


def test_cancel_stops_undispatched_step_and_replays_idempotently(turn_api):
    client, dsn = turn_api
    created = post_turn(client, turn_body()).json()['data']
    cancelled = cancel(client, created['turn'], version=created['thread']['version'],
        mutation_key='cancel-key')
    assert cancelled.status_code == 200, cancelled.text
    turn = cancelled.json()['data']['turn']
    assert turn['status'] == 'cancelled'
    assert 'TURN_CANCELLED' in {notice['code'] for notice in turn['notices']}
    activity = next(part for part in turn['parts'] if part['kind'] == 'tool_activity')
    assert activity['state'] == 'skipped'
    replay = cancel(client, created['turn'], version=created['thread']['version'],
        mutation_key='cancel-key')
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
    result = post_turn(client, turn_body())
    assert result.status_code == 200, result.text
    turn = result.json()['data']['turn']
    assert captured['refs'] == [DOCUMENT_SOURCE]
    assert turn['parts'][0]['text'] == 'Review the cited approved offer source.'
    assert 'CONVERSATION_MODEL_UNAVAILABLE' not in {notice['code'] for notice in turn['notices']}
    assert 'Approved source excerpt' not in result.text
