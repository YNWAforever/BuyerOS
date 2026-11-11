"""PostgreSQL: bounded per-project conversation turn metrics.

CI-only (no local PostgreSQL). Deterministic fixture data; no model, provider or
paid admission is enabled. Aggregate counts are asserted, never user content.
"""
import psycopg
import pytest

from tests.test_buyer_review_db import PROJECT_A, PROJECT_B, WORKSPACE_A, _h, api  # noqa: F401
from tests.test_conversation_turns_api import enabled, post_turn, turn_api, turn_body  # noqa: F401

METRICS = f'/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/conversation-turns/metrics'


def test_metrics_summarize_this_project_only(turn_api):
    client, _ = turn_api
    created = post_turn(client, turn_body())
    assert created.status_code == 200, created.text
    response = client.get(METRICS, headers=_h())
    assert response.status_code == 200, response.text
    data = response.json()['data']
    assert data['window_days'] == 7
    assert data['turns']['total'] >= 1
    assert sum(data['turns']['by_status'].values()) == data['turns']['total']
    latency = data['latency_ms']
    assert latency['samples'] >= 1
    assert latency['p50'] is not None and latency['p95'] is not None
    assert latency['p50'] <= latency['p95'] <= latency['max']
    # A turn with no inline proposal contributes no proposal/budget rows.
    assert data['proposals']['total'] == 0
    assert data['budget']['priced_proposals'] == 0
    assert data['budget']['estimated'] == []
    # Another project in the same workspace never sees this project's turns.
    other = client.get(f'/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_B}'
                       '/conversation-turns/metrics', headers=_h())
    assert other.status_code == 200, other.text
    assert other.json()['data']['turns']['total'] == 0


def test_metrics_latency_uses_observed_boundaries(turn_api):
    client, dsn = turn_api
    created = post_turn(client, turn_body())
    assert created.status_code == 200, created.text
    turn_id = created.json()['data']['turn']['id']
    with psycopg.connect(dsn, autocommit=True) as db:
        # One transaction writes every event, so created_at is identical for the
        # whole turn; latency must come from the observed payload instants.
        assert db.execute('SELECT count(DISTINCT created_at) FROM conversation_turn_events'
                          ' WHERE turn_id=%s', (turn_id,)).fetchone()[0] == 1
        db.execute("UPDATE conversation_turn_events SET payload = payload || %s::jsonb"
                   " WHERE turn_id=%s AND kind='turn.started'",
                   ('{"started_at":"2026-11-11T00:00:00Z"}', turn_id))
        db.execute("UPDATE conversation_turn_events SET payload = payload || %s::jsonb"
                   " WHERE turn_id=%s AND kind='turn.final'",
                   ('{"finished_at":"2026-11-11T00:00:01.500Z"}', turn_id))
    response = client.get(METRICS, headers=_h())
    assert response.status_code == 200, response.text
    latency = response.json()['data']['latency_ms']
    assert latency['samples'] == 1
    assert latency['p50'] == 1500
    assert latency['p95'] == 1500
    assert latency['max'] == 1500


def test_metrics_window_is_bounded_and_excludes_aged_turns(turn_api):
    client, dsn = turn_api
    created = post_turn(client, turn_body())
    assert created.status_code == 200, created.text
    turn_id = created.json()['data']['turn']['id']
    with psycopg.connect(dsn, autocommit=True) as db:
        db.execute("UPDATE conversation_turn_events SET created_at=now()-interval '20 days'"
                   ' WHERE turn_id=%s', (turn_id,))
    recent = client.get(METRICS + '?window_days=7', headers=_h())
    assert recent.status_code == 200, recent.text
    assert recent.json()['data']['turns']['total'] == 0
    wider = client.get(METRICS + '?window_days=30', headers=_h())
    assert wider.status_code == 200, wider.text
    assert wider.json()['data']['turns']['total'] == 1


@pytest.mark.parametrize('query', ['0', '31', '-1', '1.5', 'many'])
def test_metrics_reject_out_of_range_windows(turn_api, query):
    client, _ = turn_api
    response = client.get(f'{METRICS}?window_days={query}', headers=_h())
    assert response.status_code == 422, response.text
    assert response.json()['code'] == 'INVALID_REQUEST'


def test_metrics_report_model_unavailability_honestly(turn_api):
    client, dsn = turn_api
    created = post_turn(client, turn_body())
    assert created.status_code == 200, created.text
    turn_id = created.json()['data']['turn']['id']
    with psycopg.connect(dsn, autocommit=True) as db:
        db.execute('UPDATE conversation_turns SET notices=%s::jsonb WHERE id=%s',
                   ('[{"code":"CONVERSATION_MODEL_UNAVAILABLE",'
                    '"message":"conversation model admission is unavailable"}]', turn_id))
    response = client.get(METRICS, headers=_h())
    assert response.status_code == 200, response.text
    data = response.json()['data']
    assert data['model']['unavailable_turns'] == 1
    # The dashboard never invents a priced model answer.
    assert data['budget']['estimated'] == []
