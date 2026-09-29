"""T20 durable run read/replay and safe cancellation on disposable PostgreSQL."""

import uuid
import json
from decimal import Decimal

import psycopg

from tests.test_api_projects_db import OPERATOR, REVIEWER, WORKSPACE_A, _h, api as project_api
from tests.test_run_admission_integration_db import PROJECT_A, _post, admission_case


def _url(run_id):
    return f"/v1/workspaces/{WORKSPACE_A}/runs/{run_id}"


def test_run_page_replay_and_tenant_safe_missing(admission_case):
    api, dsn = admission_case
    created = _post(api, key="t20-run-page-001")
    assert created.status_code == 202, created.text
    run_id = created.json()["data"]["id"]
    listed = api.get(f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/runs?offset=0&limit=1",
                     headers=_h(subject=REVIEWER))
    assert listed.status_code == 200, listed.text
    assert listed.json()["data"]["total"] == 1
    assert listed.json()["data"]["items"][0]["id"] == run_id
    detail = api.get(_url(run_id), headers=_h(subject=REVIEWER))
    assert detail.status_code == 200, detail.text
    assert detail.json()["data"]["last_event_sequence"] == 1
    page = api.get(_url(run_id) + "/events?after_sequence=0&limit=1", headers=_h())
    assert page.status_code == 200, page.text
    assert [item["sequence"] for item in page.json()["data"]["items"]] == [1]
    assert page.json()["data"]["next_after_sequence"] == 1
    replay = api.get(_url(run_id) + "/events?after_sequence=1", headers=_h())
    assert replay.status_code == 200 and replay.json()["data"]["items"] == []
    assert api.get(_url(run_id) + "/events?after_sequence=9", headers=_h()).status_code == 409
    stream = api.get(_url(run_id) + "/events?after_sequence=0",
                     headers={**_h(), "Accept": "text/event-stream"})
    assert stream.status_code == 200 and "id: 1\n" in stream.text
    assert '"sequence":1' in stream.text
    assert api.get(f"/v1/workspaces/{WORKSPACE_A}/projects/{uuid.uuid4()}/runs", headers=_h()).status_code == 404
    missing = api.get(_url(uuid.uuid4()), headers=_h())
    assert missing.status_code == 404
    assert api.get(_url(run_id) + "/events", headers={}).status_code == 401


def test_cancel_before_dispatch_is_terminal_and_retry_does_not_reset(admission_case):
    api, dsn = admission_case
    created = _post(api, key="t20-run-cancel-001")
    assert created.status_code == 202, created.text
    run_id = created.json()["data"]["id"]
    assert api.post(_url(run_id) + "/cancel", json={"reason": "operator stopped"},
                    headers=_h(key="t20-viewer-cancel", subject=REVIEWER,
                               **{"If-Match": '"1"'})).status_code == 403
    assert api.post(_url(run_id) + "/cancel", json={"reason": "operator stopped"},
                    headers=_h(key="t20-no-etag")).status_code == 400
    assert api.post(_url(run_id) + "/cancel", json={"reason": "operator stopped"},
                    headers=_h(key="t20-stale-etag", **{"If-Match": '"9"'})).status_code == 412
    result = api.post(_url(run_id) + "/cancel", json={"reason": "operator stopped"},
                      headers=_h(key="t20-cancel-001", **{"If-Match": '"1"'}))
    assert result.status_code == 202, result.text
    assert result.json()["data"]["status"] == "cancelled"
    replay = api.post(_url(run_id) + "/cancel", json={"reason": "operator stopped"},
                      headers=_h(key="t20-cancel-001", **{"If-Match": '"1"'}))
    assert replay.status_code == 202
    with psycopg.connect(dsn) as db:
        row = db.execute("SELECT status,usage_counters FROM search_runs WHERE id=%s", (run_id,)).fetchone()
        assert row[0] == "cancelled" and row[1]["queries"] == 0
        events = db.execute("SELECT sequence,event_type FROM run_events WHERE run_id=%s ORDER BY sequence",
                            (run_id,)).fetchall()
        assert events == [(1, "run.queued"), (2, "run.cancelled")]
        state = db.execute("SELECT state FROM outbox_events WHERE payload->>'run_id'=%s", (run_id,)).fetchone()[0]
        assert state == "done"
    retry = api.post(_url(run_id) + "/retry",
                     json={"reason": "retry after cancel", "resume_from_last_committed_checkpoint": True},
                     headers=_h(key="t20-retry-cancel-001", **{"If-Match": '"2"'}))
    assert retry.status_code == 409


def test_cancel_unknown_operation_retains_hold(admission_case):
    api, dsn = admission_case
    created = _post(api, key="t20-run-unknown-001")
    run_id = created.json()["data"]["id"]
    operation_id, reservation_id = str(uuid.uuid4()), str(uuid.uuid4())
    with psycopg.connect(dsn, autocommit=True) as db:
        db.execute("UPDATE search_runs SET status='running',stage='discover' WHERE id=%s", (run_id,))
        account_id, period_start = db.execute(
            "SELECT id,period_start FROM budget_accounts WHERE workspace_id=%s AND scope='run' AND scope_id=%s",
            (WORKSPACE_A, run_id)).fetchone()
        db.execute("INSERT INTO provider_operations(id,workspace_id,intent_key,capability,input_hash,status) "
                   "VALUES (%s,%s,%s,'account_search','fixture-hash','unknown')",
                   (operation_id, WORKSPACE_A, f"research:{run_id}:{'a'*24}"))
        db.execute("INSERT INTO budget_reservations(id,workspace_id,account_id,operation_id,intent_key,"
                   "price_version,currency,origin_period_start,upper_bound,remaining_hold,state) "
                   "VALUES (%s,%s,%s,%s,%s,'fixture-price-v1','USD',%s,0.100000,0.100000,'active')",
                   (reservation_id,WORKSPACE_A,account_id,operation_id,operation_id,period_start))
        db.execute("INSERT INTO budget_reservation_allocations(id,workspace_id,reservation_id,account_id) "
                   "VALUES (%s,%s,%s,%s)", (str(uuid.uuid4()),WORKSPACE_A,reservation_id,account_id))
        db.execute("INSERT INTO outbox_events(id,workspace_id,intent_key,event_type,payload,state) "
                   "VALUES (%s,%s,%s,'research.reconcile',%s::jsonb,'ready')",
                   (str(uuid.uuid4()),WORKSPACE_A,f"research:reconcile:{operation_id}",
                    json.dumps({"run_id":run_id,"operation_id":operation_id,"query_id":"a"*24})))
    try:
        result = api.post(_url(run_id) + "/cancel", json={"reason": "stop pending calls"},
                          headers=_h(key="t20-cancel-unknown-001", **{"If-Match": '"1"'}))
        assert result.status_code == 202, result.text
        assert result.json()["data"]["status"] == "cancel_requested"
        assert result.json()["data"]["reserved"]["amount"] == "0.100000"
        assert api.get(_url(run_id), headers=_h(subject=REVIEWER)).json()["data"]["status"] == "cancel_requested"
        with psycopg.connect(dsn) as db:
            assert db.execute("SELECT remaining_hold FROM budget_reservations WHERE id=%s",
                              (reservation_id,)).fetchone()[0] == Decimal("0.100000")
            assert db.execute("SELECT count(*) FROM run_events WHERE run_id=%s", (run_id,)).fetchone()[0] == 2
            assert db.execute("SELECT state FROM outbox_events WHERE intent_key=%s",
                              (f"research:reconcile:{operation_id}",)).fetchone()[0] == "ready"
    finally:
        with psycopg.connect(dsn, autocommit=True) as db:
            db.execute("DELETE FROM budget_reservation_allocations WHERE reservation_id=%s", (reservation_id,))
            db.execute("DELETE FROM budget_reservations WHERE id=%s", (reservation_id,))
            db.execute("DELETE FROM provider_operations WHERE id=%s", (operation_id,))


def test_retry_only_safe_fit_checkpoint_preserves_usage_and_checks_current_profile(admission_case):
    api, dsn = admission_case
    created = _post(api, key="t20-run-fit-retry-001")
    run_id = created.json()["data"]["id"]
    with psycopg.connect(dsn, autocommit=True) as db:
        db.execute("UPDATE search_runs SET status='partial',stage='fit_review_required',"
                   "usage_counters=jsonb_set(usage_counters,'{queries}','3') WHERE id=%s", (run_id,))
    body={"reason":"resume verified fit", "resume_from_last_committed_checkpoint":True}
    first=api.post(_url(run_id)+"/retry",json=body,
                   headers=_h(key="t20-fit-retry-001", **{"If-Match": '"1"'}))
    assert first.status_code == 202, first.text
    assert first.json()["data"]["attempt"] == 2
    assert first.json()["data"]["status"] == "queued"
    replay=api.post(_url(run_id)+"/retry",json=body,
                    headers=_h(key="t20-fit-retry-001", **{"If-Match": '"1"'}))
    assert replay.status_code == 202 and replay.json()["data"]["attempt"] == 2
    with psycopg.connect(dsn) as db:
        counters, fit_count = db.execute("SELECT usage_counters,"
            "(SELECT count(*) FROM outbox_events WHERE workspace_id=%s AND event_type='run.fit') "
            "FROM search_runs WHERE id=%s", (WORKSPACE_A,run_id)).fetchone()
        assert counters["queries"] == 3 and fit_count == 1
    with psycopg.connect(dsn, autocommit=True) as db:
        db.execute("UPDATE search_runs SET status='partial',stage='fit_review_required' WHERE id=%s", (run_id,))
        db.execute("UPDATE projects SET offer_revision=2 WHERE id=%s", (PROJECT_A,))
    stale=api.post(_url(run_id)+"/retry",json=body,
                   headers=_h(key="t20-fit-retry-stale", **{"If-Match": '"2"'}))
    assert stale.status_code == 412
