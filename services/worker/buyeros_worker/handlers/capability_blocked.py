from ..registry import HandlerResult, register

BLOCKED_EVENTS = frozenset({"run.discover", "contact.submit", "draft.generate"})


def blocked(session, context, payload) -> HandlerResult:
    """Fail closed: no verified provider/model, so make no external call."""
    event_type = (payload or {}).get("event_type", "unknown")
    return HandlerResult(state="blocked", detail=f"{event_type}: no verified provider or model is configured")


for _event in BLOCKED_EVENTS:
    register(_event)(blocked)
