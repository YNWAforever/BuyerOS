"""Project-mutation idempotency, reusing the P4 record and the P5 conflict rule."""

import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

_ETAG = re.compile(r'"[1-9][0-9]*"')


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

    def _scope():
        return select(IdempotencyRecord).where(
            IdempotencyRecord.workspace_id == workspace_id,
            IdempotencyRecord.actor_id == actor_id,
            IdempotencyRecord.operation_id == operation_id,
            IdempotencyRecord.key == key,
        )

    def _resolve(existing):
        try:
            same_request(existing.key, existing.request_hash, key, fingerprint, raise_on_conflict=True)
        except IdempotencyConflict as exc:
            raise ApiError(409, "IDEMPOTENCY_CONFLICT", str(exc)) from exc
        if existing.status != "completed":
            raise ApiError(409, "IDEMPOTENCY_CONFLICT", "request with this key is still in progress")
        return IdempotencyOutcome(existing, replay=True)

    existing = (await session.execute(_scope())).scalar_one_or_none()
    if existing is not None:
        return _resolve(existing)

    record = IdempotencyRecord(
        workspace_id=workspace_id,
        actor_id=actor_id,
        operation_id=operation_id,
        key=key,
        request_hash=fingerprint,
        status="in_progress",
    )
    try:
        # A concurrent identical request may win the unique index first; the savepoint keeps the
        # outer transaction usable so we can re-select the winner instead of surfacing a 500.
        async with session.begin_nested():
            session.add(record)
            await session.flush()
    except IntegrityError:
        existing = (await session.execute(_scope())).scalar_one_or_none()
        if existing is None:
            # The winner's transaction has not committed yet, so its record is not visible.
            raise ApiError(409, "IDEMPOTENCY_CONFLICT", "request with this key is already in progress")
        return _resolve(existing)
    return IdempotencyOutcome(record, replay=False)


def complete_idempotency(outcome: IdempotencyOutcome, resource_id: str) -> None:
    """Mark this transaction's record complete, so a later replay can return its resource."""
    outcome.record.status = "completed"
    outcome.record.resource_id = resource_id


def if_match_version(if_match: str | None) -> int:
    """Parse the contract's strong ETag ('4'); missing or malformed is 400."""
    from .errors import ApiError

    if not if_match:
        raise ApiError(400, "INVALID_REQUEST", "If-Match header is required")
    if _ETAG.fullmatch(if_match) is None:
        raise ApiError(400, "INVALID_REQUEST", 'If-Match must be a strong ETag like "4"')
    return int(if_match[1:-1])
