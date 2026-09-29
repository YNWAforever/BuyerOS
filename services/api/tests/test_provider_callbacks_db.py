"""T23: contact job controls and callback safety on a disposable database."""

from decimal import Decimal
import hashlib
import hmac
import json
import time
import uuid

import psycopg

from tests.contract_validation import assert_contract_response
from tests.test_api_projects_db import ADMIN, OPERATOR, REVIEWER, WORKSPACE_A, _h, api
from tests.test_contact_confirm_atomicity_db import _confirm, _limits
from buyeros_api.api.routes.provider_callbacks import selected_callback_verifier
from buyeros_api.services.callback import FixtureCallbackVerifier
from tests.test_lookup_quotes_db import _body, _post, quote_case


def _job(quote_case):
    client, dsn, buyers = quote_case
    _limits(client, dsn)
    quote = _post(client, _body(buyers), key="quote-t23-job").json()["data"]
    response = _confirm(client, quote, key="confirm-t23-job")
    assert response.status_code == 202, response.text
    return client, dsn, response.json()["data"]


def test_job_read_is_scoped_and_reports_actual_hold(quote_case):
    client, dsn, created = _job(quote_case)
    path = f"/v1/workspaces/{WORKSPACE_A}/enrichment-jobs/{created['id']}"
    response = client.get(path, headers=_h(subject=OPERATOR))
    assert response.status_code == 200, response.text
    assert_contract_response("EnrichmentJobResponse", response.json())
    data = response.json()["data"]
    assert data["status"] == "reserved"
    assert data["held_cost"] == {"amount": "0.300000", "currency": "USD"}
    assert data["provider_operation_ids"] == created["provider_operation_ids"]
    assert client.get(path, headers=_h(subject=REVIEWER)).status_code == 404


def test_pre_dispatch_cancel_releases_hold_once_and_fences_outbox(quote_case):
    client, dsn, created = _job(quote_case)
    path = f"/v1/workspaces/{WORKSPACE_A}/enrichment-jobs/{created['id']}/cancel"
    headers = _h(subject=OPERATOR, key="cancel-t23-job", **{"If-Match": '"1"'})
    response = client.post(path, headers=headers, json={"reason": "Fixture cancellation"})
    assert response.status_code == 202, response.text
    assert_contract_response("EnrichmentJobResponse", response.json())
    data = response.json()["data"]
    assert data["status"] == "cancelled" and data["held_cost"]["amount"] == "0.000000"
    assert client.post(path, headers=headers, json={"reason": "Fixture cancellation"}).json()["data"] == data
    assert client.post(path, headers=_h(subject=OPERATOR, key="cancel-t23-other", **{"If-Match": '"1"'}),
                       json={"reason": "Fixture cancellation"}).status_code == 412
    with psycopg.connect(dsn) as db:
        reservation = db.execute("SELECT state,remaining_hold FROM budget_reservations WHERE id=%s",
                                 (created["reservation_id"],)).fetchone()
        assert reservation == ("released", Decimal("0.000000"))
        assert db.execute("SELECT state FROM outbox_events WHERE intent_key=%s",
                          (f"contact.lookup:{created['id']}",)).fetchone()[0] == "done"


def test_callback_without_named_verified_vendor_never_mutates_job(quote_case):
    client, dsn, created = _job(quote_case)
    response = client.post("/v1/provider-callbacks/unselected", content=b'{"event_id":"fake"}',
                           headers={"content-type": "application/json", "x-provider-signature": "fake"})
    assert response.status_code in (401, 403, 503), response.text
    with psycopg.connect(dsn) as db:
        assert db.execute("SELECT count(*) FROM provider_events WHERE workspace_id=%s",
                          (WORKSPACE_A,)).fetchone()[0] == 0
        assert db.execute("SELECT state,remaining_hold FROM budget_reservations WHERE id=%s",
                          (created["reservation_id"],)).fetchone() == ("active", Decimal("0.300000"))


def _signed(body, secret):
    raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    stamp = str(int(time.time()))
    signature = hmac.new(secret, stamp.encode() + b"." + raw, hashlib.sha256).hexdigest()
    return raw, {"content-type": "application/json", "x-fixture-timestamp": stamp,
                 "x-fixture-signature": signature}


def test_verified_fixture_callback_dedupes_conflicts_and_never_uses_caller_tenant(quote_case):
    client, dsn, created = _job(quote_case)
    secret = b"fixture-only-callback-key-for-disposable-tests"
    ref = f"fixture:{uuid.uuid4().hex}"
    with psycopg.connect(dsn, autocommit=True) as db:
        operation_id = created["provider_operation_ids"][0]
        db.execute("UPDATE provider_operations SET status='accepted',provider_name='fixture',"
                   "account_reference='fixture-test',provider_ref=%s WHERE id=%s",
                   (ref, operation_id))
        db.execute("UPDATE enrichment_jobs SET state='pending',version=2 WHERE id=%s",
                   (created["id"],))
        db.execute("INSERT INTO provider_callback_routes(provider,account_reference,provider_ref,"
                   "workspace_id,operation_id) VALUES ('fixture','fixture-test',%s,%s,%s)",
                   (ref, WORKSPACE_A, operation_id))
    client.app.dependency_overrides[selected_callback_verifier] = lambda: (
        FixtureCallbackVerifier(secret), "test")
    try:
        body = {"account_reference": "fixture-test", "operation_reference": ref,
                "event_id": "fixture-callback-terminal-1", "state": "not_found",
                "observed_cost": "0.100000"}
        raw, headers = _signed(body, secret)
        invalid = client.post("/v1/provider-callbacks/fixture", content=raw,
                              headers={**headers, "x-fixture-signature": "0" * 64})
        assert invalid.status_code == 401
        unknown = client.post("/v1/provider-callbacks/fixture",
                              content=_signed({**body, "operation_reference": "fixture:missing"}, secret)[0],
                              headers=_signed({**body, "operation_reference": "fixture:missing"}, secret)[1])
        assert unknown.status_code == 404
        first = client.post("/v1/provider-callbacks/fixture", content=raw, headers=headers)
        assert first.status_code == 200, first.text
        assert_contract_response("CallbackReceiptResponse", first.json())
        assert first.json()["data"]["accepted"] is True
        assert first.json()["data"]["duplicate"] is False
        replay = client.post("/v1/provider-callbacks/fixture", content=raw, headers=headers)
        assert replay.status_code == 200 and replay.json()["data"]["duplicate"] is True
        changed_raw, changed_headers = _signed({**body, "observed_cost": "0.200000"}, secret)
        conflict = client.post("/v1/provider-callbacks/fixture",
                               content=changed_raw, headers=changed_headers)
        assert conflict.status_code == 409
        late_raw, late_headers = _signed({**body, "event_id": "fixture-callback-late-2",
                                          "state": "pending", "observed_cost": None}, secret)
        late = client.post("/v1/provider-callbacks/fixture", content=late_raw, headers=late_headers)
        assert late.status_code == 200
        with psycopg.connect(dsn) as db:
            assert db.execute("SELECT state,remaining_hold FROM budget_reservations WHERE id=%s",
                              (created["reservation_id"],)).fetchone() == ("settled", Decimal("0.000000"))
            assert db.execute("SELECT amount FROM cost_events WHERE operation_id=%s",
                              (created["id"],)).fetchall() == [(Decimal("0.100000"),)]
            assert db.execute("SELECT state FROM enrichment_jobs WHERE id=%s",
                              (created["id"],)).fetchone()[0] == "reconciled"
            assert db.execute("SELECT processing_state FROM provider_events WHERE event_id=%s",
                              ("fixture-callback-late-2",)).fetchone()[0] == "ignored"
    finally:
        client.app.dependency_overrides.pop(selected_callback_verifier, None)


def test_admin_reconcile_request_queues_status_only_and_replays(quote_case):
    from buyeros_api.api.routes.enrichment import selected_contact_status_capability
    from tests.test_lookup_quotes_db import _capability

    client, dsn, created = _job(quote_case)
    operation_id = created["provider_operation_ids"][0]
    with psycopg.connect(dsn, autocommit=True) as db:
        db.execute("UPDATE provider_operations SET status='unknown',provider_name='fixture',"
                   "account_reference='fixture-test',provider_ref=%s WHERE id=%s",
                   ("fixture:unknown-status", operation_id))
        db.execute("UPDATE enrichment_jobs SET state='unknown',version=2 WHERE id=%s",
                   (created["id"],))
    path = f"/v1/workspaces/{WORKSPACE_A}/enrichment-jobs/{created['id']}/reconcile"
    denied = client.post(path, headers=_h(subject=OPERATOR, key="reconcile-role"),
                         json={"reason": "Investigate fixture unknown"})
    assert denied.status_code == 403
    client.app.dependency_overrides[selected_contact_status_capability] = lambda: (
        _capability(), "test", True)
    try:
        headers = _h(subject=ADMIN, key="reconcile-t23-unknown")
        first = client.post(path, headers=headers,
                            json={"reason": "Investigate fixture unknown"})
        assert first.status_code == 202, first.text
        assert_contract_response("AsyncJobResponse", first.json())
        assert first.json()["data"]["kind"] == "reconciliation"
        replay = client.post(path, headers=headers,
                             json={"reason": "Investigate fixture unknown"})
        assert replay.status_code == 202
        assert replay.json()["data"]["id"] == first.json()["data"]["id"]
        with psycopg.connect(dsn) as db:
            assert db.execute("SELECT count(*) FROM outbox_events WHERE workspace_id=%s "
                              "AND event_type='contact.reconcile'", (WORKSPACE_A,)).fetchone()[0] == 1
            assert db.execute("SELECT state,remaining_hold FROM budget_reservations WHERE id=%s",
                              (created["reservation_id"],)).fetchone() == ("active", Decimal("0.300000"))
    finally:
        client.app.dependency_overrides.pop(selected_contact_status_capability, None)


def test_cancel_after_submitting_retains_full_hold_and_marks_reconciliation_needed(quote_case):
    client, dsn, created = _job(quote_case)
    with psycopg.connect(dsn, autocommit=True) as db:
        db.execute("UPDATE provider_operations SET status='submitting' WHERE id=%s",
                   (created["provider_operation_ids"][0],))
        db.execute("UPDATE enrichment_jobs SET state='submitting',version=2 WHERE id=%s",
                   (created["id"],))
        db.execute("UPDATE outbox_events SET state='dispatched',fencing_generation=1 "
                   "WHERE intent_key=%s", (f"contact.lookup:{created['id']}",))
    path = f"/v1/workspaces/{WORKSPACE_A}/enrichment-jobs/{created['id']}/cancel"
    response = client.post(path,
        headers=_h(subject=OPERATOR, key="cancel-after-submitting", **{"If-Match": '"2"'}),
        json={"reason": "Stop future fixture dispatch"})
    assert response.status_code == 202, response.text
    data = response.json()["data"]
    assert data["cancel_requested"] is True and data["status"] == "pending"
    assert data["held_cost"]["amount"] == "0.300000"
    assert data["unknown_count"] == 1
    with psycopg.connect(dsn) as db:
        assert db.execute("SELECT state,remaining_hold FROM budget_reservations WHERE id=%s",
                          (created["reservation_id"],)).fetchone() == ("active", Decimal("0.300000"))
        assert db.execute("SELECT cancel_requested,status FROM provider_operations WHERE id=%s",
                          (created["provider_operation_ids"][0],)).fetchone() == (True, "submitting")


def test_cancel_mixed_job_closes_unsubmitted_child_and_settles_only_proven_charge(quote_case):
    client, dsn, buyers = quote_case
    with psycopg.connect(dsn, autocommit=True) as db:
        db.execute("UPDATE suppressions SET active=false WHERE workspace_id=%s", (WORKSPACE_A,))
    _limits(client, dsn)
    quote = _post(client, _body(buyers), key="quote-t23-mixed").json()["data"]
    created_response = _confirm(client, quote, key="confirm-t23-mixed")
    assert created_response.status_code == 202, created_response.text
    created = created_response.json()["data"]
    assert len(created["provider_operation_ids"]) == 2
    with psycopg.connect(dsn, autocommit=True) as db:
        db.execute("UPDATE provider_operations SET status='succeeded',observed_cost=0.1,"
                   "external_event_id='fixture-proof-first' WHERE id=%s",
                   (created["provider_operation_ids"][0],))
        db.execute("UPDATE enrichment_jobs SET state='pending' WHERE id=%s",
                   (created["id"],))
    response = client.post(f"/v1/workspaces/{WORKSPACE_A}/enrichment-jobs/{created['id']}/cancel",
        headers=_h(subject=OPERATOR, key="cancel-t23-mixed", **{"If-Match": '"1"'}),
        json={"reason": "Stop remaining lookup"})
    assert response.status_code == 202, response.text
    data = response.json()["data"]
    assert data["status"] == "reconciled"
    assert data["settled_cost"]["amount"] == "0.100000"
    assert data["held_cost"]["amount"] == "0.000000"
    with psycopg.connect(dsn) as db:
        assert db.execute("SELECT status,observed_cost FROM provider_operations WHERE id=%s",
                          (created["provider_operation_ids"][1],)).fetchone() == (
                              "cancelled", Decimal("0.000000"))
        assert db.execute("SELECT amount FROM cost_events WHERE operation_id=%s",
                          (created["id"],)).fetchall() == [(Decimal("0.100000"),)]
