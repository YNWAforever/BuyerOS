from buyeros_api.services.callback import digest_conflict, event_key, is_replay


def test_event_key_scopes_provider_account_event():
    assert event_key("p", "acct", "e1") == "p:acct:e1"


def test_replay_detected():
    assert is_replay({"p:acct:e1"}, "p:acct:e1", "sha256:x") is True
    assert is_replay(set(), "p:acct:e1", "sha256:x") is False


def test_same_key_different_digest_conflicts():
    seen = {"p:acct:e1": "sha256:x"}
    assert digest_conflict(seen, "p:acct:e1", "sha256:y") is True
    assert digest_conflict(seen, "p:acct:e1", "sha256:x") is False


def test_fixture_raw_callback_verifies_signature_window_and_test_only_boundary():
    import hashlib
    import hmac
    import json
    import time

    import pytest

    from buyeros_api.api.errors import ApiError
    from buyeros_api.services.callback import FixtureCallbackVerifier, verify_raw_callback

    secret = b"fixture-only-callback-secret-for-unit-tests"
    raw = json.dumps({"account_reference": "fixture-test",
                      "operation_reference": "fixture:ref", "event_id": "evt-1",
                      "state": "pending", "observed_cost": None}).encode()
    stamp = str(int(time.time()))
    signature = hmac.new(secret, stamp.encode() + b"." + raw, hashlib.sha256).hexdigest()
    verifier = FixtureCallbackVerifier(secret)
    event = verify_raw_callback("fixture", raw, {"x-fixture-timestamp": stamp,
        "x-fixture-signature": signature}, verifier=verifier, environment="test")
    assert event["digest"] == hashlib.sha256(raw).hexdigest()
    with pytest.raises(ApiError) as stale:
        verify_raw_callback("fixture", raw, {"x-fixture-timestamp": str(int(stamp)-301),
            "x-fixture-signature": signature}, verifier=verifier, environment="test")
    assert stale.value.status_code == 401
    with pytest.raises(ApiError) as wrong_environment:
        verify_raw_callback("fixture", raw, {"x-fixture-timestamp": stamp,
            "x-fixture-signature": signature}, verifier=verifier, environment="production")
    assert wrong_environment.value.status_code == 503
