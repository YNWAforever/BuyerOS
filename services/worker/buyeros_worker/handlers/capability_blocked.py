from ..registry import HandlerResult, register
from ..run_emitter import emit_run_event

BLOCKED_EVENTS = frozenset({"run.discover", "contact.submit", "draft.generate"})


async def blocked(session, context, payload) -> HandlerResult:
    """Fail closed: no verified provider/model, so make no external call.

    When the intent carries a run id, the run is moved to the explicit
    ``blocked`` state and exactly one ``run_events`` row is written in the same
    transaction as the work. Every other path stays a pure, side-effect-free
    refusal.
    """
    event_type = None
    if isinstance(context, dict):
        event_type = context.get("event_type")
    if event_type is None and isinstance(payload, dict):
        event_type = payload.get("event_type")
    event_type = event_type or "unknown"
    detail = f"{event_type}: no verified provider or model is configured"

    run_id = payload.get("run_id") if isinstance(payload, dict) else None
    if run_id is not None:
        await emit_run_event(
            session,
            run_id,
            "capability_blocked",
            transition="capability_block",
            payload={"event_type": event_type, "detail": detail},
        )
    return HandlerResult(state="blocked", detail=detail)


for _event in BLOCKED_EVENTS:
    register(_event)(blocked)
