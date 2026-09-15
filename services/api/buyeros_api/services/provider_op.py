"""Uncertainty-safe provider operation state machine (BO-019)."""

_ORDER = ["intent", "reserved", "submitting", "accepted", "pending", "unknown", "succeeded", "not_found", "failed"]
TERMINAL = {"succeeded", "not_found", "failed"}


def submit_outcome(kind: str) -> str:
    return {"accepted": "accepted", "pending": "pending", "timeout": "unknown", "error": "unknown"}.get(kind, "unknown")


def transition(current: str, event: str) -> str:
    if current in TERMINAL or current == "unknown":
        return current
    if _ORDER.index(event) <= _ORDER.index(current):
        return current
    return event


def should_hold(state: str) -> bool:
    return state in {"reserved", "submitting", "accepted", "pending", "unknown"}
