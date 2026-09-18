"""Project-mutation idempotency, reusing the P4 record and the P5 conflict rule."""

from dataclasses import dataclass

from sqlalchemy import select


@dataclass
class IdempotencyOutcome:
    """The record for this (workspace, actor, operation, key) and whether it is a replay."""

    record: object
    replay: bool


async def begin_idempotency(
    session, *, workspace_id, actor_id, operation_id: str, key: str, body: dict
) -> IdempotencyOutcome:
    """Return the completed record on a replay, or insert an in_progress one.

    The contract's `IdempotencyKey` is 8..200 opaque characters; anything else is 400. The same
    key with a different body is 409, matching `confirm_service.same_request`; a recorded record
    that is still `in_progress` is a conflict rather than a silent second mutation.
    """
    from ..db.contact import IdempotencyRecord
    from ..services.confirm_service import IdempotencyConflict, request_fingerprint, same_request
    from .errors import ApiError

    if not (8 <= len(key) <= 200):
        raise ApiError(400, "INVALID_REQUEST", "Idempotency-Key must be 8..200 characters")
    fingerprint = request_fingerprint(body)
    existing = (
        await session.execute(
            select(IdempotencyRecord).where(
                IdempotencyRecord.workspace_id == workspace_id,
                IdempotencyRecord.actor_id == actor_id,
                IdempotencyRecord.operation_id == operation_id,
                IdempotencyRecord.key == key,
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        record = IdempotencyRecord(
            workspace_id=workspace_id,
            actor_id=actor_id,
            operation_id=operation_id,
            key=key,
            request_hash=fingerprint,
            status="in_progress",
        )
        session.add(record)
        await session.flush()
        return IdempotencyOutcome(record, replay=False)
    try:
        same_request(existing.key, existing.request_hash, key, fingerprint, raise_on_conflict=True)
    except IdempotencyConflict as exc:
        raise ApiError(409, "IDEMPOTENCY_CONFLICT", str(exc)) from exc
    if existing.status != "completed":
        raise ApiError(409, "IDEMPOTENCY_CONFLICT", "request with this key is still in progress")
    return IdempotencyOutcome(existing, replay=True)


def complete_idempotency(outcome: IdempotencyOutcome, resource_id: str) -> None:
    """Mark this transaction's record complete, so a later replay can return its resource."""
    outcome.record.status = "completed"
    outcome.record.resource_id = resource_id


def if_match_version(if_match: str | None) -> int:
    """Parse the contract's strong ETag ('4'); missing or malformed is 400."""
    from .errors import ApiError

    if not if_match:
        raise ApiError(400, "INVALID_REQUEST", "If-Match header is required")
    if len(if_match) < 2 or not if_match.startswith('"') or not if_match.endswith('"'):
        raise ApiError(400, "INVALID_REQUEST", 'If-Match must be a strong ETag like "4"')
    try:
        version = int(if_match[1:-1])
    except ValueError as exc:
        raise ApiError(400, "INVALID_REQUEST", 'If-Match must be a strong ETag like "4"') from exc
    if version < 1:
        raise ApiError(400, "INVALID_REQUEST", 'If-Match must be a strong ETag like "4"')
    return version
