"""Budget invariant and deterministic lock ordering (BO-010)."""

from decimal import Decimal


def would_exceed(limit: Decimal, settled: Decimal, reserved: Decimal, proposed: Decimal) -> bool:
    return (settled + reserved + proposed) > limit


def lock_order(account_ids: list[str]) -> list[str]:
    """Deterministic order so concurrent transactions cannot deadlock/overspend."""
    return sorted(account_ids)
