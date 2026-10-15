"""Synchronous cited preparations. No formal draft, model, worker or email admission."""
from dataclasses import replace
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.errors import ApiError
from ..api.lead_schemas import LeadScope, LeadPreparationInput, LeadPreparationView
from ..db.buyers import BuyerSourceCheck
from ..db.icp import Project, IcpVersion, canonical_hash
from ..db.ingestion import OfferDocument
from ..db.lead_workflow import (
    LeadPreparation, LeadPreparationRevision, LeadPreparationEvidence, LeadPreparationContentReview,
)
from ..db.policy import PolicyDecision
from ..db.runs import Person, ContactPoint
from .audit_service import append_audit
from .icp_service import effective_offer_facts
from .lead_evidence_service import (
    require_permission, personal_policy, save_private_payload, retained_payload, assert_active_project,
)
from .lead_review_service import review_observations
from .policy_service import evaluate_current_policy


async def _row(session, scope, identity, *, lock=False):
    query = select(LeadPreparation).where(
        LeadPreparation.workspace_id == scope.workspace_id, LeadPreparation.project_id == scope.project_id,
        LeadPreparation.id == identity,
    )
    if scope.buyer_id:
        query = query.where(LeadPreparation.buyer_id == scope.buyer_id)
    row = await session.scalar(query.with_for_update() if lock else query)
    if row is None:
        raise ApiError(404, "NOT_FOUND", "preparation not found")
    return row, replace(scope, buyer_id=row.buyer_id, company_id=row.company_id)


async def _revision(session, scope, row):
    revision = await session.scalar(select(LeadPreparationRevision).where(
        LeadPreparationRevision.workspace_id == scope.workspace_id,
        LeadPreparationRevision.project_id == scope.project_id, LeadPreparationRevision.preparation_id == row.id,
        LeadPreparationRevision.revision_number == row.current_revision,
    ))
    if revision is None:
        raise ApiError(409, "INVALID_STATE", "current preparation revision unavailable")
    return revision


async def _fact_context(session, scope, references, now):
    if not references:
        return [], {}, []
    project = await session.scalar(select(Project).where(
        Project.workspace_id == scope.workspace_id, Project.id == scope.project_id,
    ))
    icp = await session.scalar(select(IcpVersion).where(
        IcpVersion.workspace_id == scope.workspace_id, IcpVersion.project_id == scope.project_id,
        IcpVersion.id == project.active_icp_version_id,
    ))
    if (icp is None or icp.approved_at is None or icp.approved_by is None
            or icp.superseded_at is not None or icp.basis_offer_revision != project.offer_revision
            or icp.content_hash != canonical_hash(icp.content)):
        raise ApiError(412, "STALE_REVISION", "current approved product facts required")
    facts = {str(row.get("id")): row for row in effective_offer_facts(icp) if row.get("approved") is True}
    selected, documents = [], []
    for reference in references:
        if (reference.icp_version_id != icp.id or reference.icp_content_hash != icp.content_hash
                or reference.offer_revision != project.offer_revision or str(reference.id) not in facts):
            raise ApiError(412, "STALE_REVISION", "selected product facts changed")
        fact = dict(facts[str(reference.id)])
        if fact.get("provenance") == "document_excerpt":
            document = await session.scalar(select(OfferDocument).where(
                OfferDocument.workspace_id == scope.workspace_id, OfferDocument.project_id == scope.project_id,
                OfferDocument.id == UUID(str(fact.get("source_document_id"))),
            ))
            if (document is None or document.status != "ready" or document.deleted_at is not None
                    or document.retention_until is None or document.retention_until <= now
                    or not fact.get("excerpt")
                    or (document.extraction_metadata or {}).get("classification") == "image_only"):
                raise ApiError(412, "EVIDENCE_STALE", "product document is unavailable or has no supported text")
            documents.append({"id": str(document.id), "version": document.version, "sha256": document.sha256,
                              "retention_until": document.retention_until.isoformat()})
            fact["source_filename"] = document.filename
            # The existing fact contract has an excerpt/document, not a page
            # field. Preserve that precision instead of inventing a slide.
            fact["source_page"] = None
        selected.append(fact)
    return selected, {"icp_id": str(icp.id), "hash": icp.content_hash,
                      "offer_revision": project.offer_revision, "documents": documents}, documents


async def preparation_context(session, scope, data, now, *, case_view=None):
    from .lead_progress_service import get_lead_case
    deadline = await personal_policy(session, scope, now, data.contact_id)
    gate = await evaluate_current_policy(session, {
        "workspace_id": scope.workspace_id, "project_id": scope.project_id, "company_id": scope.company_id,
        **({"contact_point_id": data.contact_id} if data.contact_id else {}),
    }, "draft_preparation", now)
    if not gate["allowed"]:
        raise ApiError(403, "POLICY_BLOCKED", "preparation purpose requires permission")
    for model, identity in ((Person, data.person_id), (ContactPoint, data.contact_id)):
        if identity is not None:
            entity = await session.scalar(select(model).where(
                model.workspace_id == scope.workspace_id, model.company_id == scope.company_id, model.id == identity,
            ))
            if entity is None:
                raise ApiError(404, "NOT_FOUND", "selected subject not found")
            if entity.retention_expires_at is None or entity.retention_expires_at <= now:
                raise ApiError(403, "POLICY_BLOCKED", "selected subject is no longer retained")
            deadline = min(deadline, entity.retention_expires_at)
            if isinstance(entity, ContactPoint) and (entity.quarantined or entity.person_id != data.person_id):
                raise ApiError(403, "POLICY_BLOCKED", "channel is unavailable for selected person")
    facts, product, documents = await _fact_context(session, scope, data.product_fact_refs, now)
    case = case_view or await get_lead_case(session, scope=scope, now=now, include_preparations=False)
    if not isinstance(case, dict):
        case = case.model_dump(mode="json")
    observations = await review_observations(session, scope, now)
    selected = {row.id: row for row in observations if row.id in data.observation_ids}
    if set(selected) != set(data.observation_ids):
        raise ApiError(404, "NOT_FOUND", "cited observation not found")
    if any(row.redacted for row in selected.values()):
        raise ApiError(403, "POLICY_BLOCKED", "cited observation is unavailable")
    company_checks = list((await session.scalars(select(BuyerSourceCheck).where(
        BuyerSourceCheck.workspace_id == scope.workspace_id, BuyerSourceCheck.project_id == scope.project_id,
        BuyerSourceCheck.buyer_id == scope.buyer_id,
    ).order_by(BuyerSourceCheck.created_at, BuyerSourceCheck.id))).all())
    check_map = {row.id: row for row in company_checks}
    if any(identity not in check_map for identity in data.company_source_check_ids):
        raise ApiError(404, "NOT_FOUND", "company source check not found")
    policies = list((await session.scalars(select(PolicyDecision).where(
        PolicyDecision.workspace_id == scope.workspace_id,
        PolicyDecision.subject_id.in_([scope.project_id, scope.company_id] + ([data.contact_id] if data.contact_id else [])),
        PolicyDecision.purpose.in_(("account_research", "contact_research", "draft_preparation")),
    ).order_by(PolicyDecision.id))).all())
    frame = {
        "company_name": case["company_name"], "person_id": str(data.person_id), "contact_id": str(data.contact_id),
        "lead_review_id": str(data.lead_review_id), "selected_person": str(case["selected_person_id"]),
        "selected_contact": str(case["selected_contact_id"]), "quality": case["quality"],
        "latest_review": case["reviews"][-1] if case["reviews"] else None,
        "observations": [{"id": str(row.id), "hash": row.content_hash, "checked_at": row.checked_at.isoformat(),
                          "person": row.person, "channel": row.channel, "availability": row.availability}
                         for row in sorted(selected.values(), key=lambda row: str(row.id))],
        "product": product, "facts": facts,
        "company_check_history": [
            {"id": str(row.id), "hash": canonical_hash({"grade": row.grade, "rationale": row.rationale,
                                                       "limitations": row.limitations, "sources": row.sources})}
            for row in company_checks],
        "selected_company_checks": [str(value) for value in data.company_source_check_ids],
        "policies": [{"id": str(row.id), "version": row.version, "expires_at": row.expires_at.isoformat()} for row in policies],
    }
    blockers = []
    if not facts:
        blockers.append("approved_product_fact_required")
    if not data.company_source_check_ids:
        blockers.append("company_source_required")
    latest = case["reviews"][-1] if case["reviews"] else None
    if (not latest or str(data.lead_review_id) != latest["id"]
            or str(data.person_id) != case["selected_person_id"]
            or str(data.contact_id) != case["selected_contact_id"]
            or not case["quality"]["direct_channel"]
            or set(map(str, data.observation_ids)) != set(latest["observation_ids"])):
        blockers.append("current_person_and_source_verified_channel_required")
    links = [source.model_dump(mode="json") for row in selected.values() for source in row.sources]
    links.extend({**source, "kind": "company_source_check", "checked_on": check_map[identity].checked_on.isoformat()}
                 for identity in data.company_source_check_ids for source in check_map[identity].sources)
    return {"hash": canonical_hash(frame), "facts": facts, "source_references": links,
            "deadline": deadline, "blockers": blockers, "documents": documents, "case": case}


async def validate_preparation_input(session, scope, data, now):
    require_permission(scope, "editDraft")
    await assert_active_project(session, scope)
    return await preparation_context(session, scope, data, now)


def _template(data, context):
    if data.subject.strip() or data.body.strip() or not context["facts"]:
        return data
    facts = "; ".join(str(row["value"]) for row in context["facts"])
    if data.language == "zh-HK":
        subject, body = "產品供應合作交流", f"你好，\n\n希望了解貴公司的採購需求，並交流以下已確認產品：{facts}。\n\n請問你是否合適的採購聯絡人？"
    else:
        subject, body = "Product supply discussion", f"Hello,\n\nCould we discuss your purchasing requirements for {facts}?\n\nAre you the appropriate purchasing contact?"
    return LeadPreparationInput.model_validate({**data.model_dump(mode="json"), "subject": subject, "body": body})


async def _append_revision(session, scope, row, data, context):
    body = data.model_dump(mode="json")
    stored = {"input": body, "facts": context["facts"], "source_references": context["source_references"],
              "offer_document_ids": [item["id"] for item in context["documents"]]}
    payload = await save_private_payload(session, scope, stored, context["deadline"], data.person_id, data.contact_id)
    revision = LeadPreparationRevision(id=uuid4(), workspace_id=scope.workspace_id, project_id=scope.project_id,
        buyer_id=scope.buyer_id, company_id=scope.company_id, preparation_id=row.id,
        revision_number=row.current_revision, payload_id=payload.id, person_id=data.person_id,
        contact_id=data.contact_id, lead_review_id=data.lead_review_id, context_hash=context["hash"],
        content_hash=canonical_hash(body), recorded_by_user_id=scope.actor_id)
    session.add(revision)
    await session.flush()
    for identity in data.observation_ids:
        session.add(LeadPreparationEvidence(workspace_id=scope.workspace_id, project_id=scope.project_id,
            buyer_id=scope.buyer_id, company_id=scope.company_id, revision_id=revision.id, observation_id=identity))
    await session.flush()
    return revision


async def create_preparation(session: AsyncSession, *, scope: LeadScope, data: LeadPreparationInput, now: datetime):
    context = await validate_preparation_input(session, scope, data, now)
    data = _template(data, context)
    row = LeadPreparation(id=uuid4(), workspace_id=scope.workspace_id, project_id=scope.project_id,
        buyer_id=scope.buyer_id, company_id=scope.company_id, state="editing", version=1, current_revision=1)
    session.add(row)
    await session.flush()
    await _append_revision(session, scope, row, data, context)
    append_audit(session, workspace_id=scope.workspace_id, actor_id=scope.actor_id,
                 action="lead.preparation.created", entity_type="lead_preparation", entity_id=row.id)
    return await get_preparation(session, scope=scope, preparation_id=row.id, now=now)


async def revise_preparation(
    session: AsyncSession, *, scope: LeadScope, preparation_id: UUID, data: LeadPreparationInput,
    expected_version: int, now: datetime,
):
    require_permission(scope, "editDraft")
    row, scope = await _row(session, scope, preparation_id, lock=True)
    if row.version != expected_version or row.state == "archived":
        raise ApiError(412, "STALE_REVISION", "preparation changed")
    previous = await _revision(session, scope, row)
    if data.previous_revision_id and data.previous_revision_id != previous.id:
        raise ApiError(412, "STALE_REVISION", "preparation revision changed")
    context = await validate_preparation_input(session, scope, data, now)
    row.current_revision += 1
    row.version += 1
    row.state = "editing"
    await _append_revision(session, scope, row, _template(data, context), context)
    return await get_preparation(session, scope=scope, preparation_id=row.id, now=now)


async def get_preparation(
    session: AsyncSession, *, scope: LeadScope, preparation_id: UUID, now: datetime, case_view=None,
):
    require_permission(scope, "getDraft")
    row, scope = await _row(session, scope, preparation_id)
    revision = await _revision(session, scope, row)
    _, stored = await retained_payload(session, scope, revision.payload_id, now)
    facts, sources, content, blockers = [], [], None, []
    current = False
    if stored:
        try:
            content = LeadPreparationInput.model_validate(stored["input"])
            context = await preparation_context(session, scope, content, now, case_view=case_view)
            facts, sources = context["facts"], context["source_references"]
            current = context["hash"] == revision.context_hash
            blockers = context["blockers"]
            if not current:
                blockers.append("source_context_changed")
        except ApiError as error:
            blockers = [error.code]
            if error.code == "POLICY_BLOCKED":
                content, stored = None, None
    else:
        blockers = ["retained_preparation_unavailable"]
    proof = await session.scalar(select(LeadPreparationContentReview).where(
        LeadPreparationContentReview.workspace_id == scope.workspace_id,
        LeadPreparationContentReview.project_id == scope.project_id,
        LeadPreparationContentReview.revision_id == revision.id,
        LeadPreparationContentReview.content_hash == revision.content_hash,
        LeadPreparationContentReview.context_hash == revision.context_hash,
    ).order_by(LeadPreparationContentReview.created_at.desc(), LeadPreparationContentReview.id.desc()).limit(1))
    state = row.state
    if state in {"reviewed", "review_requested"} and (not current or blockers or proof is None and state == "reviewed"):
        state = "needs_review"
    return LeadPreparationView(
        id=row.id, workspace_id=row.workspace_id, project_id=row.project_id, buyer_id=row.buyer_id,
        company_id=row.company_id, version=row.version, revision_id=revision.id, revision_number=revision.revision_number,
        state=state, stored_state=row.state, context_hash=revision.context_hash, content_hash=revision.content_hash,
        content=content, facts=facts, source_references=sources, blockers=list(dict.fromkeys(blockers)),
        context_current=current, redacted=stored is None, reviewed_by_user_id=proof.recorded_by_user_id if proof else None,
        reviewed_at=proof.created_at if proof else None, created_at=row.created_at,
    ).model_dump(mode="json")


async def review_preparation(
    session: AsyncSession, *, scope: LeadScope, preparation_id: UUID, expected_version: int,
    revision_id: UUID, context_hash: str, reason: str, now: datetime,
):
    require_permission(scope, "approveDraft")
    row, scope = await _row(session, scope, preparation_id, lock=True)
    view = await get_preparation(session, scope=scope, preparation_id=row.id, now=now)
    if (row.version != expected_version or row.state == "archived" or view["revision_id"] != str(revision_id)
            or view["context_hash"] != context_hash or not view["context_current"] or view["blockers"]
            or not view["content"] or not view["content"]["subject"].strip() or not view["content"]["body"].strip()):
        raise ApiError(412, "STALE_REVISION", "current complete preparation and exact source context required")
    row.state, row.version = "reviewed", row.version + 1
    session.add(LeadPreparationContentReview(workspace_id=scope.workspace_id, project_id=scope.project_id,
        buyer_id=scope.buyer_id, company_id=scope.company_id, revision_id=revision_id,
        context_hash=context_hash, content_hash=view["content_hash"], recorded_by_user_id=scope.actor_id))
    append_audit(session, workspace_id=scope.workspace_id, actor_id=scope.actor_id,
                 action="lead.preparation.content_reviewed", entity_type="lead_preparation", entity_id=row.id,
                 reason=reason, detail_digest=canonical_hash({"revision": str(revision_id), "context": context_hash}))
    await session.flush()
    return await get_preparation(session, scope=scope, preparation_id=row.id, now=now)


async def change_preparation_state(session, *, scope, preparation_id, expected_version, reason, now, archive):
    require_permission(scope, "editDraft")
    row, scope = await _row(session, scope, preparation_id, lock=True)
    if row.version != expected_version or row.state == "archived":
        raise ApiError(412, "STALE_REVISION", "preparation changed")
    if not archive:
        view = await get_preparation(session, scope=scope, preparation_id=row.id, now=now)
        if (not view["context_current"] or view["blockers"] or not view["content"]
                or not view["content"]["subject"].strip() or not view["content"]["body"].strip()):
            raise ApiError(412, "STALE_REVISION", "complete cited content required")
    row.state, row.version = ("archived" if archive else "review_requested"), row.version + 1
    append_audit(session, workspace_id=scope.workspace_id, actor_id=scope.actor_id,
                 action="lead.preparation.archived" if archive else "lead.preparation.review_requested",
                 entity_type="lead_preparation", entity_id=row.id, reason=reason)
    await session.flush()
    return await get_preparation(session, scope=scope, preparation_id=row.id, now=now)


async def archive_preparation(session, *, scope, preparation_id, expected_version, reason, now):
    return await change_preparation_state(session, scope=scope, preparation_id=preparation_id,
        expected_version=expected_version, reason=reason, now=now, archive=True)


async def list_preparations(session, *, scope, offset, limit, now):
    require_permission(scope, "listDrafts")
    conditions = (LeadPreparation.workspace_id == scope.workspace_id,
                  LeadPreparation.project_id == scope.project_id, LeadPreparation.buyer_id == scope.buyer_id)
    total = await session.scalar(select(func.count()).select_from(LeadPreparation).where(*conditions))
    ids = (await session.scalars(select(LeadPreparation.id).where(*conditions)
        .order_by(LeadPreparation.created_at.desc(), LeadPreparation.id).offset(offset).limit(limit))).all()
    return {"items": [await get_preparation(session, scope=scope, preparation_id=identity, now=now) for identity in ids],
            "offset": offset, "limit": limit, "total": total}


async def has_current_reviewed_preparation(session, scope, case_view, now):
    ids = (await session.scalars(select(LeadPreparation.id).where(
        LeadPreparation.workspace_id == scope.workspace_id, LeadPreparation.project_id == scope.project_id,
        LeadPreparation.buyer_id == scope.buyer_id, LeadPreparation.state == "reviewed",
    ))).all()
    for identity in ids:
        view = await get_preparation(session, scope=scope, preparation_id=identity, now=now, case_view=case_view)
        if view["state"] == "reviewed" and view["context_current"] and not view["redacted"]:
            return True
    return False


async def list_preparation_revisions(session, *, scope, preparation_id, offset, limit, now):
    require_permission(scope, "getDraft")
    root, scope = await _row(session, scope, preparation_id)
    conditions = (
        LeadPreparationRevision.workspace_id == scope.workspace_id,
        LeadPreparationRevision.project_id == scope.project_id,
        LeadPreparationRevision.preparation_id == root.id,
    )
    total = await session.scalar(select(func.count()).select_from(LeadPreparationRevision).where(*conditions))
    rows = (await session.scalars(select(LeadPreparationRevision).where(*conditions)
        .order_by(LeadPreparationRevision.revision_number.desc()).offset(offset).limit(limit))).all()
    items = []
    for row in rows:
        _, stored = await retained_payload(session, scope, row.payload_id, now)
        if await personal_policy(session, scope, now, row.contact_id, required=False) is None:
            stored = None
        gate = await evaluate_current_policy(session, {
            "workspace_id": scope.workspace_id, "project_id": scope.project_id, "company_id": scope.company_id,
            **({"contact_point_id": row.contact_id} if row.contact_id else {}),
        }, "draft_preparation", now)
        if not gate["allowed"]:
            stored = None
        items.append({"id": str(row.id), "preparation_id": str(root.id),
                      "revision_number": row.revision_number, "content_hash": row.content_hash,
                      "context_hash": row.context_hash, "created_at": row.created_at,
                      "content": stored["input"] if stored else None,
                      "historical": True, "redacted": stored is None})
    return {"items": items, "offset": offset, "limit": limit, "total": total}
