"""Consume only the persisted T11 job id; the database remains instruction source."""
import uuid

from ..registry import HandlerResult, register


@register("bulk.mutate")
async def handle(session, context, payload) -> HandlerResult:
    if not isinstance(payload, dict) or set(payload) != {"job_id"}:
        return HandlerResult(state="blocked", detail="bulk.mutate: invalid payload")
    try:
        job_id = uuid.UUID(payload["job_id"])
    except (TypeError, AttributeError, ValueError):
        return HandlerResult(state="blocked", detail="bulk.mutate: invalid job id")
    from buyeros_api.services.bulk_service import apply_bulk_chunk

    await apply_bulk_chunk(session, job_id)
    return HandlerResult(state="done", detail="bulk chunk committed")
