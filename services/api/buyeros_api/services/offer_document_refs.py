"""Validate cited private offer documents before immutable profile save/approval."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from ..api.errors import ApiError
from ..db.ingestion import OfferDocument


async def validate_offer_document_refs(session, *, workspace_id, project_id,
                                       document_ids, facts) -> None:
    ids = [str(value) for value in document_ids]
    if len(ids) != len(set(ids)):
        raise ApiError(422, "INVALID_REQUEST", "duplicate offer document")
    if not ids:
        if any(fact.source_document_id is not None for fact in facts):
            raise ApiError(422, "INVALID_REQUEST", "fact references an unselected document")
        return
    rows = (await session.execute(select(OfferDocument).where(
        OfferDocument.workspace_id == workspace_id,
        OfferDocument.project_id == project_id,
        OfferDocument.id.in_(document_ids),
    ).with_for_update())).scalars().all()
    by_id = {str(row.id): row for row in rows}
    now = datetime.now(timezone.utc)
    if len(by_id) != len(ids) or any(
        by_id[key].status != "ready" or by_id[key].sha256 is None
        or by_id[key].retention_until is None or by_id[key].retention_until <= now
        for key in ids
    ):
        raise ApiError(422, "INVALID_REQUEST", "document is missing, unready or expired")
    for fact in facts:
        if fact.source_document_id is None:
            if fact.provenance == "document_excerpt":
                raise ApiError(422, "INVALID_REQUEST", "document excerpt needs a source")
            continue
        source_id = str(fact.source_document_id)
        if source_id not in by_id or fact.provenance != "document_excerpt":
            raise ApiError(422, "INVALID_REQUEST", "fact has invalid document provenance")
        candidates = by_id[source_id].fact_candidates or []
        if not any(
            item.get("id") == str(fact.id)
            and item.get("field") == fact.field
            and item.get("value") == fact.value
            and item.get("excerpt") == fact.excerpt
            and item.get("approved") is False
            for item in candidates
        ):
            raise ApiError(422, "INVALID_REQUEST", "fact is not a verified document candidate")
