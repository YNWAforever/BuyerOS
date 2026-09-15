from decimal import Decimal

from buyeros_api.services.budget_service import lock_order, would_exceed


def test_invariant_boundary():
    assert not would_exceed(Decimal("10.000000"), Decimal("5.000000"), Decimal("4.000000"), Decimal("1.000000"))
    assert would_exceed(Decimal("10.000000"), Decimal("5.000000"), Decimal("4.000000"), Decimal("1.000001"))


def test_lock_order_is_deterministic_and_sorted():
    assert lock_order(["c", "a", "b"]) == ["a", "b", "c"]
    assert lock_order([]) == []
