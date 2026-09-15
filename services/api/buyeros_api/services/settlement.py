"""Ledger settlement and cancellation effects (BO-010/020)."""

from decimal import Decimal

ZERO = Decimal("0.000000")


def settle_effect(state: str, charge: str) -> dict:
    if state == "succeeded":
        return {"commit": Decimal(charge), "release": ZERO}
    return {"commit": ZERO, "release": ZERO}


def cancel_effect(state: str) -> str:
    """Only a proven-unsent bound may be released; anything else reconciles."""
    return "release" if state in {"intent", "reserved"} else "reconcile"
