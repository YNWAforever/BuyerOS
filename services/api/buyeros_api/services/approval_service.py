"""Exact-context approval rules (BO-022)."""

from .approval_fingerprint import MATERIAL_FIELDS, PRESENTATION_FIELDS
from .icp_service import effective_offer_facts


class StaleApproval(Exception):
    pass


def material_change(old: dict, new: dict) -> bool:
    for field in MATERIAL_FIELDS:
        if field in PRESENTATION_FIELDS:
            continue
        if old.get(field) != new.get(field):
            return True
    return False


def stale(*, expected_hash: str, actual_hash: str, expected_revision: int, actual_revision: int) -> bool:
    return expected_hash != actual_hash or expected_revision != actual_revision


async def invalidate_approvals_for_subject(session, *, workspace_id, subject_type: str,
                                          subject_id=None, normalized_domain=None, reason: str) -> int:
    """Synchronously invalidate matching draft approvals in the policy write transaction."""
    from sqlalchemy import func, select, update
    from ..db.buyers import Company, ProjectBuyer
    from ..db.drafts import Approval, OutreachDraft
    from ..db.runs import ContactPoint

    if subject_type == "project" and subject_id is not None:
        drafts = select(OutreachDraft.id).where(OutreachDraft.workspace_id == workspace_id,
                                                OutreachDraft.project_id == subject_id)
    else:
        if subject_type == "contact_point" and subject_id is not None:
            companies = select(ContactPoint.company_id).where(ContactPoint.workspace_id == workspace_id,
                                                               ContactPoint.id == subject_id)
        elif subject_type == "company" and subject_id is not None:
            companies = select(Company.id).where(Company.workspace_id == workspace_id, Company.id == subject_id)
        elif subject_type == "domain" and normalized_domain:
            companies = select(Company.id).where(Company.workspace_id == workspace_id,
                                                 func.lower(Company.domain) == normalized_domain)
        else:
            return 0
        buyers = select(ProjectBuyer.id).where(ProjectBuyer.workspace_id == workspace_id,
                                               ProjectBuyer.company_id.in_(companies))
        drafts = select(OutreachDraft.id).where(OutreachDraft.workspace_id == workspace_id,
                                                OutreachDraft.buyer_id.in_(buyers))
    result = await session.execute(update(Approval).where(Approval.workspace_id == workspace_id,
        Approval.draft_id.in_(drafts), Approval.invalidated_reason.is_(None)).values(
            invalidated_reason=reason, invalidated_at=datetime.now(timezone.utc)))
    return result.rowcount or 0


from datetime import datetime, timezone
import uuid

from sqlalchemy import and_, or_, select, update

from ..api.errors import ApiError
from ..db.buyers import Company, Evidence, FitAssessment, HumanReview, ProjectBuyer, SourceDocument
from ..db.drafts import Approval, DraftRevision, OutreachDraft, SenderIdentityVersion
from ..db.icp import IcpVersion, Project, canonical_hash
from ..db.models import Membership
from ..db.policy import PolicyDecision, Suppression
from ..db.runs import ContactPoint
from .approval_fingerprint import CURRENT_SERIALIZER_VERSION, fingerprint_current
from .buyer_read import _fit_freshness
from .draft_service import _digest
from .policy_service import evaluate_current_policy, normalize_domain, policy_workspace_lock

_APPROVAL_ROLES = frozenset({"reviewer", "workspace_admin"})
_REVIEW_ROLES = frozenset({"operator", "reviewer", "workspace_admin"})
_VIEW_ROLES = frozenset({"viewer", "operator", "reviewer", "workspace_admin"})


def _raw_hash(value: str) -> str:
    return value.removeprefix("sha256:")


async def _locked_draft(session, *, workspace_id, draft_id, actor_id, roles):
    """Shared order: policy gate, membership, project, draft, then context rows."""
    await policy_workspace_lock(session, workspace_id)
    member = (await session.execute(select(Membership).where(
        Membership.workspace_id == workspace_id, Membership.user_id == actor_id,
    ).with_for_update())).scalar_one_or_none()
    if member is None or not member.active or not roles.intersection(member.roles):
        raise ApiError(403, "PERMISSION_DENIED", "current membership cannot perform this action")
    locator = (await session.execute(select(OutreachDraft.project_id).where(
        OutreachDraft.workspace_id == workspace_id, OutreachDraft.id == draft_id,
    ))).scalar_one_or_none()
    if locator is None:
        raise ApiError(404, "NOT_FOUND", "draft not found")
    project = (await session.execute(select(Project).where(
        Project.workspace_id == workspace_id, Project.id == locator,
    ).with_for_update())).scalar_one_or_none()
    if project is None or project.status != "active":
        raise ApiError(412, "STALE_REVISION", "project changed")
    draft = (await session.execute(select(OutreachDraft).where(
        OutreachDraft.workspace_id == workspace_id, OutreachDraft.id == draft_id,
    ).with_for_update())).scalar_one_or_none()
    if draft is None or draft.project_id != project.id:
        raise ApiError(404, "NOT_FOUND", "draft not found")
    revision = (await session.execute(select(DraftRevision).where(
        DraftRevision.workspace_id == workspace_id, DraftRevision.draft_id == draft.id,
        DraftRevision.revision_number == draft.current_revision,
    ))).scalar_one_or_none()
    if revision is None:
        raise ApiError(409, "INVALID_STATE", "draft revision missing")
    return project, draft, revision


def _check_preconditions(draft, revision, *, expected_version, binding):
    if draft.state_version != expected_version or revision.id != binding.revision_id:
        raise ApiError(412, "STALE_REVISION", "draft revision changed")
    if revision.content_hash != binding.content_hash or revision.content_hash != _digest(revision.content):
        raise ApiError(412, "STALE_REVISION", "draft content changed")


async def current_approval_context(session, *, workspace_id, project, draft, revision):
    """Resolve all material inputs from current tenant data inside the locked transaction."""
    now = datetime.now(timezone.utc)
    content = revision.content
    if (content.get("grounding_status") != "grounded" or not content.get("subject", "").strip()
            or not content.get("body", "").strip() or not content.get("claims")):
        raise ApiError(412, "STALE_REVISION", "grounded nonempty draft required")
    if content.get("kind") not in {"initial", "follow_up"}:
        raise ApiError(412, "STALE_REVISION", "draft kind changed")
    try:
        recipient_id = uuid.UUID(str(content["recipient_contact_id"]))
        icp_id = uuid.UUID(str(content["icp_version_id"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise ApiError(412, "STALE_REVISION", "addressed draft and current profile required") from exc
    buyer = (await session.execute(select(ProjectBuyer).where(
        ProjectBuyer.workspace_id == workspace_id, ProjectBuyer.project_id == project.id,
        ProjectBuyer.id == draft.buyer_id,
    ))).scalar_one_or_none()
    if buyer is None:
        raise ApiError(412, "STALE_REVISION", "buyer changed")
    company = (await session.execute(select(Company).where(
        Company.workspace_id == workspace_id, Company.id == buyer.company_id,
    ))).scalar_one_or_none()
    if company is None:
        raise ApiError(412, "STALE_REVISION", "buyer company changed")
    icp = (await session.execute(select(IcpVersion).where(
        IcpVersion.workspace_id == workspace_id, IcpVersion.project_id == project.id,
        IcpVersion.id == icp_id, IcpVersion.id == project.active_icp_version_id,
    ))).scalar_one_or_none()
    if (icp is None or icp.approved_at is None or icp.superseded_at is not None
            or icp.basis_offer_revision != project.offer_revision
            or icp.content_hash != canonical_hash(icp.content)):
        raise ApiError(412, "STALE_REVISION", "approved profile changed")
    sender = (await session.execute(select(SenderIdentityVersion).where(
        SenderIdentityVersion.workspace_id == workspace_id,
        SenderIdentityVersion.project_id == project.id,
        SenderIdentityVersion.id == project.active_sender_identity_version_id,
        SenderIdentityVersion.retired.is_(False),
    ))).scalar_one_or_none()
    if sender is None or sender.reviewed_at is None or sender.version_key != content.get("sender_identity_version"):
        raise ApiError(412, "STALE_REVISION", "reviewed sender changed")
    contact = (await session.execute(select(ContactPoint).where(
        ContactPoint.workspace_id == workspace_id, ContactPoint.id == recipient_id,
        ContactPoint.company_id == buyer.company_id,
    ))).scalar_one_or_none()
    if (contact is None or contact.quarantined or contact.validity != "provider_marked_valid"
            or contact.type != "business_email" or not contact.normalized_value
            or contact.retention_expires_at is None or contact.retention_expires_at <= now):
        raise ApiError(412, "STALE_REVISION", "eligible recipient changed")
    fit = (await session.execute(select(FitAssessment).where(
        FitAssessment.workspace_id == workspace_id, FitAssessment.project_buyer_id == buyer.id,
    ).order_by(FitAssessment.created_at.desc(), FitAssessment.id.desc()).limit(1))).scalar_one_or_none()
    review = (await session.execute(select(HumanReview).where(
        HumanReview.workspace_id == workspace_id, HumanReview.project_buyer_id == buyer.id,
    ).order_by(HumanReview.created_at.desc(), HumanReview.id.desc()).limit(1))).scalar_one_or_none()
    if (fit is None or fit.verdict != "match" or fit.icp_version_id != icp.id
            or review is None or review.state != "accepted" or review.fit_assessment_id != fit.id
            or (await _fit_freshness(session, workspace_id=workspace_id, fits=[fit],
                                     buyers_by_id={buyer.id: buyer})).get(fit.id) != "current"
            or _raw_hash(str(fit.evidence_set_hash)) != _raw_hash(str(content.get("evidence_set_hash")))):
        raise ApiError(412, "STALE_REVISION", "accepted evidence-backed buyer changed")
    selected_facts = [str(item) for item in content.get("value_proposition_fact_ids", [])]
    approved_facts = {str(row.get("id")) for row in effective_offer_facts(icp)
                      if isinstance(row, dict) and row.get("approved") is True}
    if not selected_facts or len(set(selected_facts)) != len(selected_facts) or not set(selected_facts) <= approved_facts:
        raise ApiError(412, "STALE_REVISION", "selected offer facts changed")
    evidence_context = []
    fit_evidence = {str(item) for item in fit.evidence_ids or []}
    for ref in content.get("evidence_refs", []):
        try:
            evidence_id, expected_version = uuid.UUID(str(ref["id"])), int(ref["version"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ApiError(412, "EVIDENCE_STALE", "invalid cited evidence") from exc
        row = (await session.execute(select(Evidence, SourceDocument).outerjoin(
            SourceDocument, and_(SourceDocument.workspace_id == Evidence.workspace_id,
                                 SourceDocument.id == Evidence.source_document_id),
        ).where(Evidence.workspace_id == workspace_id, Evidence.id == evidence_id,
                Evidence.project_id == project.id, Evidence.company_id == buyer.company_id))).one_or_none()
        if (str(evidence_id) not in fit_evidence or row is None or row[1] is None
                or row[0].version != expected_version or row[0].stance != "supports"
                or row[0].is_inference or row[1].project_id != project.id
                or row[1].permission_purpose != "account_research"
                or row[1].retention_until is None or row[1].retention_until <= now
                or not row[1].excerpt):
            raise ApiError(412, "EVIDENCE_STALE", "cited evidence changed")
        evidence, source = row
        evidence_context.append({"id": str(evidence.id), "version": evidence.version,
                                 "content_hash": evidence.content_hash, "source_id": str(source.id),
                                 "source_digest": source.digest,
                                 "source_retention_until": source.retention_until.isoformat()})
    if not evidence_context or len({row["id"] for row in evidence_context}) != len(evidence_context):
        raise ApiError(412, "EVIDENCE_STALE", "unique current supporting evidence required")
    evidence_context.sort(key=lambda row: row["id"])
    claims = content.get("claims", [])
    for claim in claims:
        if not isinstance(claim, dict) or not claim.get("text"):
            raise ApiError(412, "STALE_REVISION", "invalid grounded claim")
        if not set(map(str, claim.get("evidence_ids", []))) <= {row["id"] for row in evidence_context}:
            raise ApiError(412, "EVIDENCE_STALE", "claim cites unselected evidence")
        if not set(map(str, claim.get("offer_fact_ids", []))) <= set(selected_facts):
            raise ApiError(412, "STALE_REVISION", "claim cites unapproved offer fact")
        if not claim.get("evidence_ids") and not claim.get("offer_fact_ids"):
            raise ApiError(412, "STALE_REVISION", "uncited claim")
    subject = {"workspace_id": workspace_id, "project_id": project.id,
               "company_id": buyer.company_id, "contact_point_id": contact.id}
    for purpose in ("draft_preparation", "outreach", "export_contacts"):
        gate = await evaluate_current_policy(session, subject, purpose, now)
        if not gate["allowed"]:
            raise ApiError(403, "POLICY_BLOCKED", f"{purpose} is not permitted")
    scopes = [and_(PolicyDecision.subject_type == kind, PolicyDecision.subject_id == value)
              for kind, value in (("project", project.id), ("company", company.id),
                                  ("contact_point", contact.id))]
    policy_rows = (await session.execute(select(PolicyDecision).where(
        PolicyDecision.workspace_id == workspace_id,
        PolicyDecision.controller_scope_id == workspace_id,
        PolicyDecision.purpose.in_(("draft_preparation", "outreach", "export_contacts")),
        or_(*scopes),
    ).order_by(PolicyDecision.id))).scalars().all()
    policies = [{"id": str(row.id), "version": row.version, "purpose": row.purpose,
                 "status": row.status, "subject_type": row.subject_type,
                 "subject_id": str(row.subject_id), "expires_at": row.expires_at.isoformat()}
                for row in policy_rows]
    policy_ids = sorted(str(row.id) for row in policy_rows if row.expires_at > now)
    domain = normalize_domain(company.domain) if company.domain else None
    suppressions = (await session.execute(select(Suppression).where(
        Suppression.workspace_id == workspace_id, or_(
            and_(Suppression.subject_type == "company", Suppression.subject_id == company.id),
            and_(Suppression.subject_type == "contact_point", Suppression.subject_id == contact.id),
            and_(Suppression.subject_type == "domain", Suppression.normalized_domain == domain)
            if domain else and_(Suppression.subject_type == "company", Suppression.subject_id == company.id),
        ),
    ).order_by(Suppression.id))).scalars().all()
    suppression_context = [{"id": str(row.id), "version": row.version, "active": row.active,
                            "purposes": sorted(row.purposes), "removed_at": row.removed_at.isoformat()
                            if row.removed_at else None} for row in suppressions]
    context = {
        "draft_id": str(draft.id), "revision_id": str(revision.id),
        "revision_number": revision.revision_number, "content_hash": revision.content_hash,
        "subject": content["subject"], "body": content["body"], "kind": content["kind"],
        "language": content["language"],
        "recipient": {"id": str(contact.id), "version": contact.version,
                      "value": contact.normalized_value, "type": contact.type,
                      "validity": contact.validity, "checked_at": contact.checked_at.isoformat()
                      if contact.checked_at else None, "quarantined": contact.quarantined},
        "sender": {"id": str(sender.id), "version_key": sender.version_key,
                   "display_name": sender.display_name, "role": sender.role,
                   "organization": sender.organization, "business_email": sender.business_email,
                   "country": sender.country, "reviewed_at": sender.reviewed_at.isoformat()},
        "icp": {"id": str(icp.id), "content_hash": icp.content_hash,
                "number": icp.number, "offer_revision": project.offer_revision},
        "buyer": {"id": str(buyer.id), "version": buyer.version, "company_id": str(company.id)},
        "fit": {"id": str(fit.id), "evidence_set_hash": _raw_hash(str(fit.evidence_set_hash))},
        "review": {"id": str(review.id), "state": review.state,
                   "fit_assessment_id": str(review.fit_assessment_id)},
        "evidence": evidence_context, "offer_fact_ids": sorted(selected_facts),
        "policy": {"rows": policies, "active_ids": policy_ids},
        "suppression": suppression_context,
    }
    return context, policy_ids


async def request_draft_review(session, *, workspace_id, actor_id, draft_id, expected_version, binding):
    project, draft, revision = await _locked_draft(session, workspace_id=workspace_id,
        draft_id=draft_id, actor_id=actor_id, roles=_REVIEW_ROLES)
    _check_preconditions(draft, revision, expected_version=expected_version, binding=binding)
    if binding.context_hash != revision.content.get("context_hash"):
        raise ApiError(412, "STALE_REVISION", "draft context changed")
    context, policy_ids = await current_approval_context(session, workspace_id=workspace_id,
        project=project, draft=draft, revision=revision)
    digest = fingerprint_current(context).removeprefix("sha256:")
    draft.review_context_hash = digest
    draft.review_revision_id = revision.id
    draft.review_context = context
    draft.state = "review_requested"
    draft.state_version += 1
    await session.execute(update(Approval).where(
        Approval.workspace_id == workspace_id, Approval.draft_id == draft.id,
        Approval.invalidated_reason.is_(None),
    ).values(invalidated_reason="new_review_request", invalidated_at=datetime.now(timezone.utc)))
    await session.flush()
    await session.refresh(draft)
    return draft, revision, policy_ids


async def approve_draft(session, *, workspace_id, actor_id, draft_id, expected_version,
                        confirmation: bool, binding):
    if not confirmation:
        raise ApiError(422, "INVALID_REQUEST", "exact revision confirmation required")
    project, draft, revision = await _locked_draft(session, workspace_id=workspace_id,
        draft_id=draft_id, actor_id=actor_id, roles=_APPROVAL_ROLES)
    _check_preconditions(draft, revision, expected_version=expected_version, binding=binding)
    if draft.state != "review_requested" or draft.review_revision_id != revision.id:
        raise ApiError(412, "STALE_REVISION", "request review of the current revision")
    context, policy_ids = await current_approval_context(session, workspace_id=workspace_id,
        project=project, draft=draft, revision=revision)
    digest = fingerprint_current(context).removeprefix("sha256:")
    recipient = context["recipient"]
    expected = (binding.context_hash == digest == draft.review_context_hash
                and binding.recipient_contact_id == uuid.UUID(recipient["id"])
                and binding.recipient_contact_version == recipient["version"]
                and binding.evidence_set_hash == context["fit"]["evidence_set_hash"]
                and binding.icp_version_id == uuid.UUID(context["icp"]["id"])
                and sorted(str(row) for row in binding.policy_decision_ids) == policy_ids
                and binding.sender_identity_version == context["sender"]["version_key"])
    if not expected:
        raise ApiError(412, "STALE_REVISION", "reviewed approval context changed")
    existing = (await session.execute(select(Approval).where(
        Approval.workspace_id == workspace_id, Approval.draft_id == draft.id,
        Approval.invalidated_reason.is_(None),
    ))).scalar_one_or_none()
    if existing is not None:
        raise ApiError(409, "INVALID_STATE", "draft already has a current approval")
    approval = Approval(workspace_id=workspace_id, draft_id=draft.id,
        revision_number=revision.revision_number, content_hash=revision.content_hash,
        context_fingerprint="sha256:" + digest, serializer_version=CURRENT_SERIALIZER_VERSION,
        approver_id=actor_id, draft_revision_id=revision.id,
        recipient_contact_id=binding.recipient_contact_id,
        recipient_contact_version=binding.recipient_contact_version,
        evidence_set_hash=binding.evidence_set_hash, icp_version_id=binding.icp_version_id,
        policy_decision_ids=policy_ids, sender_identity_version=binding.sender_identity_version,
        context_snapshot=context, approved_at=datetime.now(timezone.utc))
    session.add(approval)
    draft.state = "approved"
    draft.state_version += 1
    await session.flush()
    await session.refresh(approval)
    return approval


def approval_data(approval: Approval) -> dict:
    return {"id": str(approval.id), "workspace_id": str(approval.workspace_id),
            "version": 1, "created_at": approval.created_at.isoformat(),
            "updated_at": approval.updated_at.isoformat(), "data_mode": "live",
            "draft_id": str(approval.draft_id), "draft_revision_id": str(approval.draft_revision_id),
            "content_hash": approval.content_hash,
            "context_hash": approval.context_fingerprint.removeprefix("sha256:"),
            "recipient_contact_id": str(approval.recipient_contact_id),
            "recipient_contact_version": approval.recipient_contact_version,
            "evidence_set_hash": approval.evidence_set_hash,
            "icp_version_id": str(approval.icp_version_id),
            "policy_decision_ids": approval.policy_decision_ids,
            "sender_identity_version": approval.sender_identity_version,
            "approver_id": str(approval.approver_id),
            "approved_at": approval.approved_at.isoformat(), "valid": approval.invalidated_reason is None,
            **({"invalidated_at": approval.invalidated_at.isoformat()}
               if approval.invalidated_at else {}),
            **({"invalidation_reason": approval.invalidated_reason}
               if approval.invalidated_reason else {})}



async def current_review_matches(session, *, workspace_id, project, draft, revision) -> bool:
    """Fail closed for detail reads and idempotency replay after material drift."""
    if not draft.review_context_hash or draft.review_revision_id != revision.id:
        return False
    try:
        context, _ = await current_approval_context(session, workspace_id=workspace_id,
            project=project, draft=draft, revision=revision)
    except ApiError:
        return False
    return fingerprint_current(context).removeprefix("sha256:") == draft.review_context_hash
