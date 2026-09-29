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
    response: dict | None = None
    session: object | None = None


def request_fingerprint(operation_id: str, target: dict, precondition: str | None, body: dict) -> str:
    """Canonical v1 mutation identity; never infer target from a legacy body-only record."""
    from ..services.confirm_service import request_fingerprint as canonical_hash

    return canonical_hash({
        "serializer_version": 1,
        "operation_id": operation_id,
        "target": target,
        "precondition": precondition,
        "body": body,
    })


async def begin_idempotency(
    session, *, workspace_id, actor_id, operation_id: str, key: str, body: dict,
    target: dict | None = None, precondition: str | None = None,
) -> IdempotencyOutcome:
    """Return the completed record on a replay, or insert an in_progress one.

    The contract's `IdempotencyKey` is 8..200 opaque characters; anything else is 400. The same
    key with a different body is 409, matching `confirm_service.same_request`; a recorded record
    that is still `in_progress` is a conflict rather than a silent second mutation.
    """
    from ..db.contact import IdempotencyRecord
    from ..services.confirm_service import IdempotencyConflict, request_fingerprint as body_fingerprint, same_request
    from .errors import ApiError

    if not (8 <= len(key) <= 200):
        raise ApiError(400, "INVALID_REQUEST", "Idempotency-Key must be 8..200 characters")
    fingerprint = (
        request_fingerprint(operation_id, target, precondition, body)
        if target is not None else body_fingerprint(body)
    )

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
        return IdempotencyOutcome(existing, replay=True, response=existing.response, session=session)

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
    return IdempotencyOutcome(record, replay=False, session=session)


def complete_idempotency(outcome: IdempotencyOutcome, resource_id: str, response: dict | None = None) -> None:
    """Mark this transaction's record complete, so a later replay can return its resource/response."""
    outcome.record.status = "completed"
    outcome.record.resource_id = resource_id
    if response is not None:
        outcome.record.response = response
    # Mutations already audited in their domain services are intentionally absent.
    # This map covers older T01-T11 writes at their shared first-commit boundary.
    audit_actions = {
        "createProject": ("project.created", "project"),
        "updateProject": ("project.updated", "project"),
        "saveICPVersion": ("icp.saved", "icp_version"),
        "updateBuyer": ("buyer.updated", "project_buyer"),
        "createBuyerList": ("buyer_list.created", "buyer_list"),
        "renameBuyerList": ("buyer_list.renamed", "buyer_list"),
        "saveFilterPreset": ("filter_preset.saved", "filter_preset"),
        "uploadOfferDocument": ("offer_document.uploaded", "offer_document"),
        "deleteOfferDocument": ("offer_document.deleted", "offer_document"),
    }
    operation = outcome.record.operation_id.split(":", 1)[0]
    if operation.startswith("createBuyerSnapshot"):
        action, entity_type = "buyer_snapshot.created", "buyer_snapshot"
    elif operation in ("assignBuyerOwners", "reviewBuyers", "changeListMemberships"):
        action = operation + ".requested"
        entity_type = "async_job" if response and response.get("http_status") == 202 else "project"
    elif operation in ("retryFailedAsyncJob", "cancelAsyncJob"):
        action, entity_type = operation + ".requested", "async_job"
    else:
        found = audit_actions.get(operation)
        action, entity_type = found if found else (None, None)
    if action and outcome.session is not None:
        from ..services.audit_service import append_audit, request_correlation
        append_audit(outcome.session, workspace_id=outcome.record.workspace_id,
                     actor_id=outcome.record.actor_id, action=action,
                     entity_type=entity_type, entity_id=resource_id,
                     request_id=request_correlation.get())


def if_match_version(if_match: str | None) -> int:
    """Parse the contract's strong ETag ('4'); missing or malformed is 400."""
    from .errors import ApiError

    if not if_match:
        raise ApiError(400, "INVALID_REQUEST", "If-Match header is required")
    if _ETAG.fullmatch(if_match) is None:
        raise ApiError(400, "INVALID_REQUEST", 'If-Match must be a strong ETag like "4"')
    return int(if_match[1:-1])
