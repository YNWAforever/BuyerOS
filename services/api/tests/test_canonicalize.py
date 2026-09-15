from buyeros_api.services.canonicalize import canonical_key, is_auto_merge_allowed, registrable_hint


def test_canonical_key_normalizes_host():
    assert canonical_key("HTTPS://WWW.Example.com/#x") == "example.com"


def test_shared_domain_is_not_auto_merged():
    a = {"registry_id": "DE1", "domain": "brand.com"}
    b = {"registry_id": "DE2", "domain": "brand.com"}
    assert is_auto_merge_allowed(a, b) is False


def test_matching_registry_id_may_merge():
    assert is_auto_merge_allowed({"registry_id": "DE1"}, {"registry_id": "DE1"}) is True


def test_missing_registry_id_never_auto_merges():
    assert is_auto_merge_allowed({}, {}) is False


def test_registrable_hint_strips_www():
    assert registrable_hint("www.example.com") == "example.com"
