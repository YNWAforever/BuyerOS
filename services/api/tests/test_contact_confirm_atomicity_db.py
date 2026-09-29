"""T22: quote consumption and bounded contact job admission are one transaction."""

import uuid
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import psycopg

from tests.contract_validation import assert_contract_response
from tests.test_api_projects_db import ADMIN, OPERATOR, WORKSPACE_A, _h, api
from tests.test_lookup_quotes_db import _body, _capability, _post, quote_case
from buyeros_api.api.routes.quotes import selected_contact_quote_capability


def _limits(client, dsn, amount="1.000000"):
    client.get(f"/v1/workspaces/{WORKSPACE_A}/budgets", headers=_h(subject=ADMIN))
    with psycopg.connect(dsn, autocommit=True) as db:
        db.execute("UPDATE budget_accounts SET approved_limit=%s WHERE workspace_id=%s",
                   (amount, WORKSPACE_A))


def _confirm(client, quote, *, key="confirm-fixture-0001", body=None, subject=OPERATOR):
    return client.post(
        f"/v1/workspaces/{WORKSPACE_A}/enrichment-quotes/{quote['id']}/confirm",
        json=body or {"quote_hash": quote["quote_hash"], "confirm_eligible_only": True},
        headers=_h(key=key, subject=subject),
    )


def _counts(dsn):
    with psycopg.connect(dsn) as db:
        return {table: db.execute(f"SELECT count(*) FROM {table} WHERE workspace_id=%s",
                                  (WORKSPACE_A,)).fetchone()[0]
                for table in ("enrichment_jobs", "budget_reservations", "provider_operations", "outbox_events")}


def test_confirmation_commits_one_job_hold_intent_outbox_and_replays(quote_case):
    client, dsn, buyers = quote_case
    _limits(client, dsn)
    quote = _post(client, _body(buyers), key="quote-confirm-base").json()["data"]
    first = _confirm(client, quote)
    assert first.status_code == 202, first.text
    assert_contract_response("EnrichmentJobResponse", first.json())
    data = first.json()["data"]
    assert data["status"] == "reserved"
    assert data["held_cost"] == {"amount": "0.300000", "currency": "USD"}
    assert data["settled_cost"] == {"amount": "0.000000", "currency": "USD"}
    assert data["found_count"] == 0 and data["result_contact_ids"] == []
    current = client.get(f"/v1/workspaces/{WORKSPACE_A}/enrichment-quotes/{quote['id']}",
                         headers=_h()).json()["data"]
    assert current["status"] == "consumed" and current["consumed_job_id"] == data["id"]
    assert current["reservation_id"] == data["reservation_id"]
    with psycopg.connect(dsn) as db:
        assert db.execute("SELECT count(*) FROM budget_reservation_allocations "
                          "WHERE workspace_id=%s AND reservation_id=%s",
                          (WORKSPACE_A, data["reservation_id"])).fetchone()[0] == 3
        assert db.execute("SELECT upper_bound,remaining_hold FROM budget_reservations "
                          "WHERE id=%s", (data["reservation_id"],)).fetchone() == (Decimal("0.300000"), Decimal("0.300000"))
    assert _counts(dsn) == {"enrichment_jobs": 1, "budget_reservations": 1,
                            "provider_operations": 1, "outbox_events": 1}
    replay = _confirm(client, quote)
    assert replay.status_code == 202 and replay.json()["data"]["id"] == data["id"]
    changed = _confirm(client, quote, body={"quote_hash": "f" * 64,
                                            "confirm_eligible_only": True})
    assert changed.status_code == 409 and changed.json()["code"] == "IDEMPOTENCY_CONFLICT"
    second_key = _confirm(client, quote, key="confirm-second-key")
    assert second_key.status_code == 409
    assert _counts(dsn) == {"enrichment_jobs": 1, "budget_reservations": 1,
                            "provider_operations": 1, "outbox_events": 1}


def test_twenty_racing_confirmations_never_double_consume_quote(quote_case):
    client, dsn, buyers = quote_case
    _limits(client, dsn)
    quote = _post(client, _body(buyers), key="quote-race-base").json()["data"]
    with ThreadPoolExecutor(max_workers=20) as pool:
        responses = list(pool.map(lambda i: _confirm(client, quote, key=f"confirm-race-{i:03d}"), range(20)))
    assert [response.status_code for response in responses].count(202) == 1
    assert all(response.status_code in (202, 409) for response in responses)
    assert _counts(dsn) == {"enrichment_jobs": 1, "budget_reservations": 1,
                            "provider_operations": 1, "outbox_events": 1}


def test_two_quotes_competing_for_one_budget_have_one_winner(quote_case):
    client, dsn, buyers = quote_case
    with psycopg.connect(dsn, autocommit=True) as db:
        db.execute("UPDATE suppressions SET active=false WHERE workspace_id=%s", (WORKSPACE_A,))
    _limits(client, dsn, "0.300000")
    quotes = [_post(client, _body([buyer]), key=f"quote-budget-{i}").json()["data"]
              for i, buyer in enumerate(buyers)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda i: _confirm(client, quotes[i], key=f"confirm-budget-{i}"), range(2)))
    assert [response.status_code for response in responses].count(202) == 1
    assert [response.json()["code"] for response in responses if response.status_code != 202] == ["BUDGET_LIMIT"]
    counts = _counts(dsn)
    assert counts == {"enrichment_jobs": 1, "budget_reservations": 1,
                      "provider_operations": 1, "outbox_events": 1}


def test_expired_or_suppressed_quote_cannot_reserve(quote_case):
    client, dsn, buyers = quote_case
    _limits(client, dsn)
    quote = _post(client, _body(buyers), key="quote-expiry-base").json()["data"]
    with psycopg.connect(dsn, autocommit=True) as db:
        db.execute("UPDATE enrichment_quotes SET expires_at=now()-interval '1 second' WHERE id=%s", (quote["id"],))
    expired = _confirm(client, quote, key="confirm-expired")
    assert expired.status_code == 409 and expired.json()["code"] == "QUOTE_EXPIRED"
    fresh = _post(client, _body(buyers), key="quote-policy-base").json()["data"]
    with psycopg.connect(dsn, autocommit=True) as db:
        db.execute("UPDATE suppressions SET active=true, subject_id=%s WHERE workspace_id=%s",
                   (buyers[0][1], WORKSPACE_A))
    changed = _confirm(client, fresh, key="confirm-policy-changed")
    assert changed.status_code in (409, 412) and changed.json()["code"] == "QUOTE_CHANGED"
    assert _counts(dsn) == {"enrichment_jobs": 0, "budget_reservations": 0,
                            "provider_operations": 0, "outbox_events": 0}


def test_price_actor_buyer_and_zero_budget_changes_fail_closed(quote_case):
    client, dsn, buyers = quote_case
    _limits(client, dsn, "0.000000")
    quote = _post(client, _body(buyers), key="quote-price-actor").json()["data"]
    assert _confirm(client, quote, key="confirm-other-actor", subject=ADMIN).status_code == 403
    client.app.dependency_overrides[selected_contact_quote_capability] = lambda: (
        _capability("0.400000", "fixture-price-v2"), "test")
    price_changed = _confirm(client, quote, key="confirm-price-changed")
    assert price_changed.status_code == 409 and price_changed.json()["code"] == "QUOTE_CHANGED"
    client.app.dependency_overrides[selected_contact_quote_capability] = lambda: (_capability(), "test")
    with psycopg.connect(dsn, autocommit=True) as db:
        db.execute("UPDATE project_buyers SET version=version+1 WHERE id=%s", (buyers[0][0],))
    version_changed = _confirm(client, quote, key="confirm-buyer-changed")
    assert version_changed.status_code == 409 and version_changed.json()["code"] == "QUOTE_CHANGED"
    with psycopg.connect(dsn, autocommit=True) as db:
        db.execute("UPDATE project_buyers SET version=version-1 WHERE id=%s", (buyers[0][0],))
    budget_denied = _confirm(client, quote, key="confirm-budget-zero")
    assert budget_denied.status_code == 409 and budget_denied.json()["code"] == "BUDGET_LIMIT"
    assert _counts(dsn) == {"enrichment_jobs": 0, "budget_reservations": 0,
                            "provider_operations": 0, "outbox_events": 0}


def test_suppression_and_confirm_have_one_committed_winner(quote_case):
    client, dsn, buyers = quote_case
    _limits(client, dsn)
    quote = _post(client, _body(buyers), key="quote-suppression-race").json()["data"]
    barrier = Barrier(2)

    def confirm():
        barrier.wait()
        return _confirm(client, quote, key="confirm-suppression-race")

    def suppress():
        barrier.wait()
        return client.post(f"/v1/workspaces/{WORKSPACE_A}/suppressions",
            headers=_h(subject=ADMIN, key="suppression-confirm-race"),
            json={"subject_type":"company","subject_id":buyers[0][1],
                  "controller_scope_id":WORKSPACE_A,"purposes":["contact_research"],
                  "reason":"Fixture race suppression"})

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(confirm)
        second = pool.submit(suppress)
        confirmed, suppressed = first.result(), second.result()
    assert suppressed.status_code == 201, suppressed.text
    counts = _counts(dsn)
    if confirmed.status_code == 202:
        # The subsequent T23 dispatch guard must observe this later suppression.
        assert counts == {"enrichment_jobs":1,"budget_reservations":1,
                          "provider_operations":1,"outbox_events":1}
    else:
        assert confirmed.status_code == 409 and confirmed.json()["code"] == "QUOTE_CHANGED"
        assert counts == {"enrichment_jobs":0,"budget_reservations":0,
                          "provider_operations":0,"outbox_events":0}
