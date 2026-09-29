"""Grounded draft revision validation (BO-021)."""

from .icp_service import effective_offer_facts


class UncitedClaim(Exception):
    pass


def validate_grounding(revision: dict, allowed_evidence: set[str], allowed_facts: set[str]) -> dict:
    evidence = revision.get("evidence_ids", [])
    facts = revision.get("offer_fact_ids", [])
    if not evidence and not facts:
        raise UncitedClaim("revision has no cited evidence or offer facts")
    if any(e not in allowed_evidence for e in evidence):
        raise UncitedClaim("unknown evidence id")
    if any(f not in allowed_facts for f in facts):
        raise UncitedClaim("unknown offer fact id")
    return revision


async def admit_grounded_template(session, *, workspace_id, project_id, actor_id, request):
    """Admit only a zero-cost, deterministic preparation job with current sources."""
    import uuid
    from datetime import datetime, timezone
    from decimal import Decimal

    from sqlalchemy import select
    from sqlalchemy.sql import and_, or_

    from ..api.errors import ApiError
    from ..db.buyers import Evidence, FitAssessment, HumanReview, ProjectBuyer, SourceDocument
    from ..db.drafts import OutreachDraft, SenderIdentityVersion
    from ..db.icp import IcpVersion, Project, canonical_hash
    from ..db.outbox import AsyncJob, AsyncJobItem, OutboxEvent
    from ..db.policy import PolicyDecision
    from .buyer_read import _fit_freshness
    from .outbox_service import build_intent
    from .policy_service import evaluate_current_policy

    if Decimal(request.max_cost.amount) != 0:
        raise ApiError(503, "PROVIDER_UNAVAILABLE", "no verified paid model route is selected")
    if request.recipient_contact_id is not None:
        raise ApiError(503, "PROVIDER_UNAVAILABLE", "addressed draft preparation is not enabled")
    if request.language not in {"en", "zh-HK"}:
        raise ApiError(422, "INVALID_REQUEST", "unsupported draft language")
    project = (await session.execute(select(Project).where(
        Project.workspace_id == workspace_id, Project.id == project_id,
    ).with_for_update())).scalar_one_or_none()
    if project is None:
        raise ApiError(404, "NOT_FOUND", "project not found")
    if project.status != "active":
        raise ApiError(409, "INVALID_STATE", "project is archived")
    icp = (await session.execute(select(IcpVersion).where(
        IcpVersion.workspace_id == workspace_id, IcpVersion.project_id == project_id,
        IcpVersion.id == project.active_icp_version_id,
    ))).scalar_one_or_none()
    if (icp is None or icp.approved_at is None or icp.superseded_at is not None
            or icp.basis_offer_revision != project.offer_revision
            or icp.content_hash != canonical_hash(icp.content)):
        raise ApiError(412, "STALE_REVISION", "current approved profile required")
    sender = (await session.execute(select(SenderIdentityVersion).where(
        SenderIdentityVersion.workspace_id == workspace_id,
        SenderIdentityVersion.project_id == project_id,
        SenderIdentityVersion.id == project.active_sender_identity_version_id,
        SenderIdentityVersion.retired.is_(False),
    ))).scalar_one_or_none()
    if sender is None or sender.reviewed_at is None:
        raise ApiError(412, "STALE_REVISION", "reviewed project sender required")
    buyer = (await session.execute(select(ProjectBuyer).where(
        ProjectBuyer.workspace_id == workspace_id, ProjectBuyer.project_id == project_id,
        ProjectBuyer.id == request.buyer_id,
    ).with_for_update())).scalar_one_or_none()
    if buyer is None:
        raise ApiError(404, "NOT_FOUND", "buyer not found")
    if buyer.version != request.buyer_version:
        raise ApiError(412, "STALE_REVISION", "buyer version changed")
    fit = (await session.execute(select(FitAssessment).where(
        FitAssessment.workspace_id == workspace_id,
        FitAssessment.project_buyer_id == buyer.id,
    ).order_by(FitAssessment.created_at.desc(), FitAssessment.id.desc()).limit(1))).scalar_one_or_none()
    review = (await session.execute(select(HumanReview).where(
        HumanReview.workspace_id == workspace_id,
        HumanReview.project_buyer_id == buyer.id,
    ).order_by(HumanReview.created_at.desc(), HumanReview.id.desc()).limit(1))).scalar_one_or_none()
    if (fit is None or fit.verdict != "match" or fit.icp_version_id != icp.id
            or review is None or review.state != "accepted" or review.fit_assessment_id != fit.id
            or (await _fit_freshness(session, workspace_id=workspace_id,
                                     fits=[fit], buyers_by_id={buyer.id: buyer})).get(fit.id) != "current"):
        raise ApiError(412, "STALE_REVISION", "current accepted evidence-backed buyer required")
    decision = await evaluate_current_policy(session, {
        "workspace_id": workspace_id, "project_id": project_id, "company_id": buyer.company_id,
    }, "draft_preparation", datetime.now(timezone.utc))
    if not decision["allowed"]:
        raise ApiError(403, "POLICY_BLOCKED", "draft preparation is not permitted")
    selected_fact_ids = [str(value) for value in request.approved_offer_fact_ids]
    if len(set(selected_fact_ids)) != len(selected_fact_ids):
        raise ApiError(422, "INVALID_REQUEST", "duplicate offer fact")
    fact_map = {str(row.get("id")): row for row in effective_offer_facts(icp)
                if isinstance(row, dict) and row.get("approved") is True}
    if any(value not in fact_map for value in selected_fact_ids):
        raise ApiError(422, "INVALID_REQUEST", "offer fact is not approved in the active profile")
    selected_evidence = []
    fit_evidence = set(fit.evidence_ids or [])
    for ref in request.evidence_refs:
        try:
            evidence_id = uuid.UUID(ref.id)
        except (TypeError, ValueError) as exc:
            raise ApiError(422, "INVALID_REQUEST", "invalid evidence reference") from exc
        if str(evidence_id) not in fit_evidence:
            raise ApiError(422, "INVALID_REQUEST", "evidence is not in the accepted fit")
        row = (await session.execute(select(Evidence, SourceDocument).outerjoin(
            SourceDocument,
            (SourceDocument.workspace_id == Evidence.workspace_id)
            & (SourceDocument.id == Evidence.source_document_id),
        ).where(Evidence.workspace_id == workspace_id, Evidence.id == evidence_id,
                Evidence.project_id == project_id, Evidence.company_id == buyer.company_id))).one_or_none()
        if row is None or row[0].version != ref.version or row[0].stance != "supports" or row[0].is_inference:
            raise ApiError(412, "EVIDENCE_STALE", "evidence changed or is not a supporting observation")
        evidence, source = row
        if (source is None or source.project_id != project_id or source.permission_purpose != "account_research"
                or source.retention_until is None or source.retention_until <= datetime.now(timezone.utc)
                or not source.excerpt):
            raise ApiError(412, "EVIDENCE_STALE", "source is unavailable")
        selected_evidence.append({"id": str(evidence.id), "version": evidence.version})
    if len({row["id"] for row in selected_evidence}) != len(selected_evidence):
        raise ApiError(422, "INVALID_REQUEST", "duplicate evidence")
    if request.parent_draft_id is not None:
        parent = (await session.execute(select(OutreachDraft).where(
            OutreachDraft.workspace_id == workspace_id, OutreachDraft.id == request.parent_draft_id,
            OutreachDraft.project_id == project_id, OutreachDraft.buyer_id == buyer.id,
        ))).scalar_one_or_none()
        if parent is None:
            raise ApiError(404, "NOT_FOUND", "parent draft not found")
    policy_rows = (await session.execute(select(PolicyDecision.id).where(
        PolicyDecision.workspace_id == workspace_id,
        PolicyDecision.purpose == "draft_preparation",
        or_(and_(PolicyDecision.subject_type == "project", PolicyDecision.subject_id == project_id),
            and_(PolicyDecision.subject_type == "company", PolicyDecision.subject_id == buyer.company_id)),
        PolicyDecision.expires_at > datetime.now(timezone.utc),
    ).order_by(PolicyDecision.id))).scalars().all()
    command = {"buyer_id": str(buyer.id), "buyer_version": buyer.version,
               "icp_id": str(icp.id), "icp_hash": icp.content_hash,
               "offer_revision": project.offer_revision,
               "fit_id": str(fit.id), "review_id": str(review.id),
               "sender_id": str(sender.id), "sender_version": sender.version_key,
               "offer_fact_ids": selected_fact_ids, "evidence_refs": selected_evidence,
               "evidence_set_hash": fit.evidence_set_hash,
               "policy_decision_ids": [str(value) for value in policy_rows],
               "objective": request.objective, "tone": request.tone,
               "language": request.language, "kind": request.kind,
               "parent_draft_id": str(request.parent_draft_id) if request.parent_draft_id else None,
               "route": "grounded-template.v1", "max_cost": request.max_cost.amount}
    job = AsyncJob(workspace_id=workspace_id, project_id=project_id, actor_user_id=actor_id,
                   kind="draft_generation", operation="generateDraft", command=command,
                   status="queued", requested=1, processed=0, updated=0, unchanged=0,
                   blocked=0, conflicts=0)
    session.add(job)
    await session.flush()
    session.add(AsyncJobItem(workspace_id=workspace_id, job_id=job.id,
                             buyer_id=buyer.id, ordinal=0,
                             expected_version=buyer.version, status="pending"))
    payload = {"job_id": str(job.id)}
    session.add(OutboxEvent(workspace_id=workspace_id,
                            intent_key=build_intent("draft.generate", payload, 0),
                            event_type="draft.generate", payload=payload,
                            state="ready", attempts=0, fencing_generation=0))
    await session.flush()
    await session.refresh(job)
    return job


def _digest(value: dict) -> str:
    import hashlib
    import json
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                      ensure_ascii=False).encode("utf-8")).hexdigest()


def draft_data(draft, revision, approval=None, *, include_review_context=False,
               context_current=True) -> dict:
    content = revision.content
    data = {
        "id": str(draft.id), "workspace_id": str(draft.workspace_id),
        "version": draft.state_version,
        "created_at": draft.created_at.isoformat(), "updated_at": draft.updated_at.isoformat(),
        "data_mode": "live", "project_id": str(draft.project_id),
        "buyer_id": str(draft.buyer_id),
        "status": "stale" if draft.state in {"review_requested", "approved"}
                  and (not context_current or draft.state == "approved" and approval is None)
                  else draft.state,
        "revision_id": str(revision.id), "revision_number": revision.revision_number,
        "content_hash": revision.content_hash,
        "context_hash": draft.review_context_hash if context_current and (draft.state == "review_requested" or draft.state == "approved" and approval is not None)
                        and draft.review_revision_id == revision.id and draft.review_context_hash
                        else content.get("context_hash", "0" * 64),
        "icp_version_id": content["icp_version_id"],
        "evidence_set_hash": str(content["evidence_set_hash"]).removeprefix("sha256:"),
        "policy_decision_ids": draft.review_context["policy"]["active_ids"]
                               if context_current and (draft.state == "review_requested" or draft.state == "approved" and approval is not None) and draft.review_context
                               else content.get("policy_decision_ids", []),
        "kind": content["kind"], "subject": content["subject"], "body": content["body"],
        "language": content["language"], "evidence_refs": content.get("evidence_refs", []),
        "claims": content.get("claims", []),
        "approval_id": str(approval.id) if approval else None,
        "delivery_enabled": False,
        "value_proposition_fact_ids": content["value_proposition_fact_ids"],
    }
    if include_review_context and context_current and draft.review_context and draft.review_revision_id == revision.id:
        context = draft.review_context
        data["approval_review"] = {
            "recipient": {key: context["recipient"][key] for key in
                          ("id", "version", "value", "validity")},
            "sender": {key: context["sender"][key] for key in
                       ("version_key", "display_name", "organization", "business_email")},
            "evidence": [{key: row[key] for key in ("id", "version", "source_id")}
                         for row in context["evidence"]],
            "policy_decision_ids": context["policy"]["active_ids"],
            "fit_id": context["fit"]["id"], "review_id": context["review"]["id"],
            "icp_version_id": context["icp"]["id"],
            "context_hash": draft.review_context_hash,
        }
    for name in ("objective", "tone", "sender_identity_version", "recipient_contact_id", "parent_draft_id"):
        value = content.get(name)
        if value is not None or name == "recipient_contact_id":
            data[name] = value
    return data


async def edit_draft(session, *, workspace_id, draft, expected_version: int, changes: dict):
    import uuid
    from datetime import datetime, timezone
    from sqlalchemy import select, update

    from ..api.errors import ApiError
    from ..db.buyers import Evidence, SourceDocument
    from ..db.drafts import Approval, DraftRevision, SenderIdentityVersion
    from ..db.icp import IcpVersion, Project, canonical_hash

    if draft.state_version != expected_version:
        raise ApiError(412, "STALE_REVISION", "draft state changed")
    project = (await session.execute(select(Project).where(
        Project.workspace_id == workspace_id, Project.id == draft.project_id,
    ).with_for_update())).scalar_one_or_none()
    if project is None or project.status != "active":
        raise ApiError(404, "NOT_FOUND", "project not available")
    current = (await session.execute(select(DraftRevision).where(
        DraftRevision.workspace_id == workspace_id, DraftRevision.draft_id == draft.id,
        DraftRevision.revision_number == draft.current_revision,
    ))).scalar_one_or_none()
    if current is None:
        raise ApiError(409, "INVALID_STATE", "draft revision missing")
    content = dict(current.content)
    if "recipient_contact_id" in changes and changes["recipient_contact_id"] is not None:
        raise ApiError(503, "PROVIDER_UNAVAILABLE", "addressed draft preparation is not enabled")
    if "sender_identity_version" in changes:
        sender = (await session.execute(select(SenderIdentityVersion).where(
            SenderIdentityVersion.workspace_id == workspace_id,
            SenderIdentityVersion.project_id == project.id,
            SenderIdentityVersion.id == project.active_sender_identity_version_id,
            SenderIdentityVersion.retired.is_(False),
        ))).scalar_one_or_none()
        if sender is None or sender.version_key != changes["sender_identity_version"]:
            raise ApiError(412, "STALE_REVISION", "sender version is not active in this project")
    if "value_proposition_fact_ids" in changes:
        icp = (await session.execute(select(IcpVersion).where(
            IcpVersion.workspace_id == workspace_id,
            IcpVersion.project_id == project.id,
            IcpVersion.id == project.active_icp_version_id,
        ))).scalar_one_or_none()
        if (icp is None or icp.approved_at is None or icp.superseded_at is not None
                or icp.content_hash != canonical_hash(icp.content)):
            raise ApiError(412, "STALE_REVISION", "active approved profile required")
        allowed = {str(fact.get("id")) for fact in effective_offer_facts(icp)
                   if isinstance(fact, dict) and fact.get("approved") is True}
        if not set(changes["value_proposition_fact_ids"]).issubset(allowed):
            raise ApiError(422, "INVALID_REQUEST", "offer fact is not approved")
    if "evidence_refs" in changes:
        from ..db.buyers import ProjectBuyer
        buyer = (await session.execute(select(ProjectBuyer).where(
            ProjectBuyer.workspace_id == workspace_id, ProjectBuyer.id == draft.buyer_id,
            ProjectBuyer.project_id == project.id,
        ))).scalar_one_or_none()
        if buyer is None:
            raise ApiError(404, "NOT_FOUND", "buyer not found")
        for ref in changes["evidence_refs"]:
            try:
                evidence_id = uuid.UUID(ref["id"])
            except (TypeError, ValueError, KeyError) as exc:
                raise ApiError(422, "INVALID_REQUEST", "invalid evidence reference") from exc
            row = (await session.execute(select(Evidence, SourceDocument).outerjoin(
                SourceDocument, (SourceDocument.workspace_id == Evidence.workspace_id)
                & (SourceDocument.id == Evidence.source_document_id),
            ).where(Evidence.workspace_id == workspace_id, Evidence.id == evidence_id,
                    Evidence.project_id == project.id, Evidence.company_id == buyer.company_id))).one_or_none()
            if (row is None or row[0].version != ref["version"] or row[1] is None
                    or row[1].retention_until is None
                    or row[1].retention_until <= datetime.now(timezone.utc)):
                raise ApiError(412, "EVIDENCE_STALE", "evidence is unavailable")
    for key, value in changes.items():
        content[key] = value
    # Human edits are retained but lose machine grounding until separately reviewed.
    content["claims"] = []
    content["grounding_status"] = "needs_review"
    context = {key: content.get(key) for key in (
        "recipient_contact_id", "sender_identity_version", "evidence_refs", "icp_version_id",
        "evidence_set_hash", "policy_decision_ids", "objective", "tone", "language",
        "value_proposition_fact_ids")}
    content["context_hash"] = _digest(context)
    revision = DraftRevision(workspace_id=workspace_id, draft_id=draft.id,
        revision_number=draft.current_revision + 1, content=content,
        content_hash=_digest(content),
        evidence_ids=[row["id"] for row in content.get("evidence_refs", [])],
        offer_fact_ids=content["value_proposition_fact_ids"])
    session.add(revision)
    draft.current_revision += 1
    draft.state_version += 1
    draft.state = "draft"
    draft.review_context_hash = None
    draft.review_revision_id = None
    draft.review_context = None
    await session.execute(update(Approval).where(
        Approval.workspace_id == workspace_id, Approval.draft_id == draft.id,
        Approval.invalidated_reason.is_(None),
    ).values(invalidated_reason="draft_edited", invalidated_at=datetime.now(timezone.utc)))
    await session.flush()
    await session.refresh(draft)
    await session.refresh(revision)
    return revision
