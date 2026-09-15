"""Fail-closed purpose policy evaluation (BO-009)."""

from ..db.policy import PURPOSES  # re-exported for callers

_RANK = {"permitted": 0, "requires_review": 1, "blocked": 2}


def effective_decision(decisions: list[dict], purpose: str) -> str:
    """Most-restrictive applicable decision, or ``unknown`` when none applies."""
    relevant = [
        d["status"]
        for d in decisions
        if d.get("purpose") == purpose and d.get("status") in _RANK
    ]
    if not relevant:
        return "unknown"
    return max(relevant, key=lambda status: _RANK[status])


__all__ = ["PURPOSES", "effective_decision"]
