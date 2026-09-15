import pytest

from buyeros_api.services.confirm_service import IdempotencyConflict, request_fingerprint, same_request


def test_fingerprint_is_order_independent():
    assert request_fingerprint({"a": 1, "b": 2}) == request_fingerprint({"b": 2, "a": 1})


def test_same_key_same_body_replays():
    assert same_request("k1", "h1", "k1", "h1") is True


def test_same_key_different_body_conflicts():
    assert same_request("k1", "h1", "k1", "h2") is False
    with pytest.raises(IdempotencyConflict):
        same_request("k1", "h1", "k1", "h2", raise_on_conflict=True)


def test_different_keys_do_not_replay():
    assert same_request("k1", "h1", "k2", "h1") is False
