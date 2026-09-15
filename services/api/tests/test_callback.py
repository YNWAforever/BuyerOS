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
