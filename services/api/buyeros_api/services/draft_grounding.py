"""Human source qualification, not automated semantic truth verification (Q12)."""
from datetime import datetime, timezone
from types import SimpleNamespace

from sqlalchemy import select, update
from ..api.errors import ApiError
from ..db.drafts import Approval, DraftRevision
from ..db.icp import IcpVersion
from .draft_service import _digest


def validate_manual_segments(content, segments, *, icp_id, icp_hash):
    """Python string offsets are Unicode code points; cover all non-whitespace exactly once."""
    covered = {field: set() for field in ("subject", "body")}
    evidence = {(str(ref["id"]), ref["version"]) for ref in content.get("evidence_refs", [])}
    facts = set(map(str, content.get("value_proposition_fact_ids", [])))
    claims = []
    for segment in segments:
        field, start, end = segment["field"], segment["start"], segment["end"]
        text = content[field]
        if (start >= end or end > len(text) or text[start:end] != segment["exact_text"]
                or not segment["exact_text"].strip() or len(segment["reason"].strip()) < 3):
            raise ApiError(422, "INVALID_REQUEST", "invalid Unicode segment or review reason")
        positions = set(range(start, end))
        if covered[field].intersection(positions):
            raise ApiError(422, "INVALID_REQUEST", "overlapping review segments")
        covered[field].update(positions)
        er, fr = segment["evidence_refs"], segment["offer_fact_refs"]
        if len({str(r["id"]) for r in er}) != len(er) or len({str(r["id"]) for r in fr}) != len(fr):
            raise ApiError(422, "INVALID_REQUEST", "duplicate segment sources")
        if segment["classification"] == "non_factual":
            if er or fr:
                raise ApiError(422, "INVALID_REQUEST", "non-factual classification cannot cite sources")
            kind = "non_factual"
        else:
            if not er and not fr:
                raise ApiError(422, "INVALID_REQUEST", "factual segment requires a versioned source")
            if not {(str(r["id"]), r["version"]) for r in er} <= evidence:
                raise ApiError(412, "EVIDENCE_STALE", "segment evidence is outside the selected source versions")
            if any(str(r["id"]) not in facts or str(r["icp_version_id"]) != str(icp_id)
                   or r["icp_content_hash"] != icp_hash.removeprefix("sha256:") for r in fr):
                raise ApiError(412, "STALE_REVISION", "segment offer fact version changed")
            kind = "observation" if er else "offer_fact"
        claims.append({"text": segment["exact_text"], "kind": kind,
                       "evidence_ids": [str(r["id"]) for r in er],
                       "offer_fact_ids": [str(r["id"]) for r in fr]})
    for field, positions in covered.items():
        if any(i not in positions for i, point in enumerate(content[field]) if not point.isspace()):
            raise ApiError(422, "INVALID_REQUEST", "every non-whitespace code point must be classified")
    return claims


async def review_manual_grounding(session, *, workspace_id, actor_id, draft_id,
                                  expected_version, payload):
    from .approval_service import _locked_draft, current_approval_context
    project, draft, revision = await _locked_draft(session, workspace_id=workspace_id,
        draft_id=draft_id, actor_id=actor_id, roles={"reviewer", "workspace_admin"})
    if (draft.state_version != expected_version or revision.id != payload.revision_id
            or revision.content_hash != payload.content_hash or _digest(revision.content) != revision.content_hash):
        raise ApiError(412, "STALE_REVISION", "exact edited revision changed")
    if revision.content.get("grounding_status") != "needs_review":
        raise ApiError(409, "INVALID_STATE", "only an edited draft needs manual source review")
    if len(payload.reason.strip()) < 3:
        raise ApiError(422, "INVALID_REQUEST", "review reason required")
    icp = (await session.execute(select(IcpVersion).where(
        IcpVersion.workspace_id == workspace_id, IcpVersion.project_id == project.id,
        IcpVersion.id == project.active_icp_version_id))).scalar_one_or_none()
    if icp is None:
        raise ApiError(412, "STALE_REVISION", "approved profile changed")
    content = dict(revision.content)
    segments = [row.model_dump(mode="json") for row in payload.segments]
    content["claims"] = validate_manual_segments(content, segments, icp_id=icp.id, icp_hash=icp.content_hash)
    content["grounding_status"] = "grounded"
    now = datetime.now(timezone.utc)
    content["grounding_review"] = {"based_on_revision_id": str(revision.id),
        "based_on_content_hash": revision.content_hash, "reviewed_by": str(actor_id),
        "reviewed_at": now.isoformat(), "reason": payload.reason, "segments": segments}
    # An in-memory candidate is qualified by the SAME current approval guard before any write.
    candidate = SimpleNamespace(id=revision.id, revision_number=revision.revision_number,
        content=content, content_hash=_digest(content))
    context, _ = await current_approval_context(session, workspace_id=workspace_id, project=project,
        draft=draft, revision=candidate, pending_grounding_review=True)
    content["grounding_source_context"] = {"evidence": context["evidence"],
        "icp_id": str(icp.id), "icp_hash": icp.content_hash}
    successor = DraftRevision(workspace_id=workspace_id, draft_id=draft.id,
        revision_number=revision.revision_number + 1, content=content, content_hash=_digest(content),
        evidence_ids=[r["id"] for r in content["evidence_refs"]],
        offer_fact_ids=content["value_proposition_fact_ids"])
    session.add(successor)
    draft.current_revision += 1
    draft.state_version += 1
    draft.state = "draft"
    draft.review_revision_id = draft.review_context_hash = draft.review_context = None
    await session.execute(update(Approval).where(Approval.workspace_id == workspace_id,
        Approval.draft_id == draft.id, Approval.invalidated_reason.is_(None)).values(
            invalidated_reason="manual_grounding_review", invalidated_at=now))
    await session.flush()
    await session.refresh(draft)
    await session.refresh(successor)
    from .audit_service import append_audit
    append_audit(session, workspace_id=workspace_id, actor_id=actor_id,
        action="reviewDraftGrounding", entity_type="draft_revision", entity_id=successor.id,
        reason=payload.reason, detail_digest="sha256:" + successor.content_hash)
    return draft, successor
