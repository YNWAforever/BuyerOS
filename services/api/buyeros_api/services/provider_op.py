"""Uncertainty-safe provider operation state machine (BO-019)."""

_ORDER = ["intent", "reserved", "submitting", "accepted", "pending", "unknown", "succeeded", "not_found", "failed"]
TERMINAL = {"succeeded", "not_found", "failed", "cancelled"}


def submit_outcome(kind: str) -> str:
    return {"accepted": "accepted", "pending": "pending", "timeout": "unknown", "error": "unknown"}.get(kind, "unknown")


def transition(current: str, event: str) -> str:
    if event == "cancelled":
        return "cancelled" if current in {"intent", "reserved"} else current
    if current in TERMINAL or current == "unknown":
        return current
    if _ORDER.index(event) <= _ORDER.index(current):
        return current
    return event


def should_hold(state: str) -> bool:
    return state in {"reserved", "submitting", "accepted", "pending", "unknown"}


def reconcile_transition(current: str, event: str, *, authoritative_event_id: str) -> str:
    """Move an unknown submission only on a verified provider event identity.

    The caller must verify the provider source and settle/release the retained
    hold in the same domain transaction; this function never changes money.
    """
    if not authoritative_event_id or len(authoritative_event_id) > 200:
        raise ValueError("authoritative provider event identity required")
    if current == "unknown":
        return event if event in TERMINAL else current
    return transition(current, event)
