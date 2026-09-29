from buyeros_api.db.icp import canonical_hash


def test_canonical_hash_is_order_independent():
    assert canonical_hash({"b": 1, "a": [1, 2]}) == canonical_hash({"a": [1, 2], "b": 1})


def test_canonical_hash_changes_with_content():
    assert canonical_hash({"a": 1}) != canonical_hash({"a": 2})


def test_canonical_hash_prefix():
    assert canonical_hash({}).startswith("sha256:")


def test_effective_offer_facts_require_reviewer_and_exclude_inference():
    from types import SimpleNamespace
    from buyeros_api.services.icp_service import effective_offer_facts

    facts = [{"id": "manual", "provenance": "user_entered", "approved": True},
             {"id": "inferred", "provenance": "model_inference", "approved": True}]
    row = SimpleNamespace(content={"offer_facts": facts}, approved_at=None, approved_by=None)
    assert [fact["approved"] for fact in effective_offer_facts(row)] == [False, False]
    row.approved_at, row.approved_by = object(), object()
    assert [fact["approved"] for fact in effective_offer_facts(row)] == [True, False]
    assert facts[0]["approved"] is True  # The stored flag is never rewritten.
