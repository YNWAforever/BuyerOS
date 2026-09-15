from buyeros_api.db.icp import canonical_hash


def test_canonical_hash_is_order_independent():
    assert canonical_hash({"b": 1, "a": [1, 2]}) == canonical_hash({"a": [1, 2], "b": 1})


def test_canonical_hash_changes_with_content():
    assert canonical_hash({"a": 1}) != canonical_hash({"a": 2})


def test_canonical_hash_prefix():
    assert canonical_hash({}).startswith("sha256:")
