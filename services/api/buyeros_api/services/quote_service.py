"""Server-priced optional business-contact quote; no reservation or dispatch (BO-017)."""

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import and_, or_, select

from ..api.errors import ApiError
from ..db.buyers import Company, FitAssessment, HumanReview, ProjectBuyer
from ..db.contact import EnrichmentJob, EnrichmentQuote
from ..db.icp import IcpVersion, Project, canonical_hash
from ..db.policy import PolicyDecision, Suppression
from ..db.runs import ContactPoint
from ..providers.contact import contact_activation_blockers
from .buyer_read import _fit_freshness
from .buyer_review import _resolve_items
from .policy_service import evaluate_current_policy, normalize_domain

MAX_QUOTED_BUYERS = 100
QUOTE_TTL = timedelta(minutes=5)
MAX_MONEY = Decimal("99999999999999.999999")


def quote_hash(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def eligible(gates: dict) -> tuple[bool, list[str]]:
    """Legacy pure gate, retained for existing callers; live quotes use stable codes."""
    reasons: list[str] = []
    if not gates.get("accepted"):
        reasons.append("buyer not accepted")
    if gates.get("policy") != "permitted":
        reasons.append(f"policy is {gates.get('policy')}")
    if gates.get("suppressed"):
        reasons.append("suppressed")
    if not gates.get("role_supported", True):
        reasons.append("unsupported role/contact type")
    return (not reasons), reasons


def _verified_capability(capability, project: Project, roles: list[str], environment: str) -> None:
    if capability is None or capability.service != "contact" or not capability.roles:
        raise ApiError(503, "PROVIDER_UNAVAILABLE", "verified contact pricing is unavailable")
    for market in project.markets or []:
        for language in project.language_preferences or []:
            blockers = contact_activation_blockers(capability, market=market, language=language,
                role=sorted(capability.roles)[0], environment=environment)
            if blockers:
                raise ApiError(503, "PROVIDER_UNAVAILABLE", "verified contact pricing is unavailable")
    if not project.markets or not project.language_preferences:
        raise ApiError(503, "PROVIDER_UNAVAILABLE", "project market/language is not verified")
    if capability.max_liability is None or capability.max_liability.amount <= 0:
        raise ApiError(503, "PROVIDER_UNAVAILABLE", "bounded contact pricing is unavailable")


async def _latest(session, model, workspace_id, buyer_id):
    return (await session.execute(select(model).where(
        model.workspace_id == workspace_id, model.project_buyer_id == buyer_id,
    ).order_by(model.created_at.desc(), model.id.desc()).limit(1))).scalar_one_or_none()


async def _policy_basis(session, workspace_id, project_id, company: Company) -> dict:
    decisions = (await session.execute(select(PolicyDecision).where(
        PolicyDecision.workspace_id == workspace_id,
        PolicyDecision.purpose == "contact_research",
        or_(and_(PolicyDecision.subject_type == "project", PolicyDecision.subject_id == project_id),
            and_(PolicyDecision.subject_type == "company", PolicyDecision.subject_id == company.id)),
    ).order_by(PolicyDecision.id))).scalars().all()
    suppression_scope = [and_(Suppression.subject_type == "company", Suppression.subject_id == company.id)]
    if company.domain:
        try:
            domain = normalize_domain(company.domain)
        except ApiError:
            domain = None
        if domain:
            suppression_scope.append(and_(Suppression.subject_type == "domain",
                                          Suppression.normalized_domain == domain))
    suppressions = (await session.execute(select(Suppression).where(
        Suppression.workspace_id == workspace_id,
        Suppression.purposes.any("contact_research"),
        or_(*suppression_scope),
    ).order_by(Suppression.id))).scalars().all()
    return {
        "decisions": [{"id": str(row.id), "version": row.version, "status": row.status,
                       "expires_at": row.expires_at.isoformat()} for row in decisions],
        "suppressions": [{"id": str(row.id), "version": row.version, "active": row.active,
                          "expires_at": row.expires_at.isoformat() if row.expires_at else None}
                         for row in suppressions],
    }


async def quote_lookup(session, actor_id: uuid.UUID, project_id: uuid.UUID, request, *,
                       workspace_id: uuid.UUID, capability, environment: str,
                       persist: bool = True) -> EnrichmentQuote:
    """Freeze exact eligibility and maximum liability without a provider or budget write."""
    project = (await session.execute(select(Project).where(
        Project.workspace_id == workspace_id, Project.id == project_id,
    ))).scalar_one_or_none()
    if project is None:
        raise ApiError(404, "NOT_FOUND", "project not found")
    if project.status != "active":
        raise ApiError(409, "INVALID_STATE", "project is archived")
    icp = (await session.execute(select(IcpVersion).where(
        IcpVersion.workspace_id == workspace_id,
        IcpVersion.project_id == project_id,
        IcpVersion.id == project.active_icp_version_id,
    ))).scalar_one_or_none()
    if (icp is None or icp.approved_at is None or icp.superseded_at is not None or
            icp.basis_offer_revision != project.offer_revision or
            icp.content_hash != canonical_hash(icp.content)):
        raise ApiError(412, "STALE_REVISION", "current approved buyer profile is required")
    _verified_capability(capability, project, request.roles, environment)
    selection = request.selection.model_dump(mode="json")
    selected = await _resolve_items(session, workspace_id=workspace_id, project_id=project_id,
                                    actor_user_id=actor_id, selection=selection)
    if len(selected) > MAX_QUOTED_BUYERS:
        raise ApiError(422, "INVALID_REQUEST", "quote selection exceeds 100 buyers")
    active_quotes = (await session.execute(select(EnrichmentQuote).join(
        EnrichmentJob,
        (EnrichmentJob.workspace_id == EnrichmentQuote.workspace_id) &
        (EnrichmentJob.quote_id == EnrichmentQuote.id),
    ).where(
        EnrichmentQuote.workspace_id == workspace_id,
        EnrichmentQuote.project_id == project_id,
        EnrichmentJob.state.in_(["reserved", "queued", "submitting", "unknown", "reconciling"]),
    ))).scalars().all()
    active_lookup_buyers = {
        row.get("buyer_id") for existing in active_quotes for row in (existing.eligibility or [])
        if row.get("eligible") is True
    }
    now = datetime.now(timezone.utc)
    lines = []
    basis_rows = []
    for buyer_id, expected_version in selected:
        buyer = (await session.execute(select(ProjectBuyer).where(
            ProjectBuyer.workspace_id == workspace_id, ProjectBuyer.project_id == project_id,
            ProjectBuyer.id == buyer_id,
        ))).scalar_one_or_none()
        if buyer is None:
            raise ApiError(404, "NOT_FOUND", "buyer not found")
        if buyer.version != expected_version:
            raise ApiError(412, "STALE_REVISION", "buyer selection version changed")
        company = (await session.execute(select(Company).where(
            Company.workspace_id == workspace_id, Company.id == buyer.company_id,
        ))).scalar_one()
        fit = await _latest(session, FitAssessment, workspace_id, buyer_id)
        review = await _latest(session, HumanReview, workspace_id, buyer_id)
        reasons = []
        if fit is None or fit.verdict != "match" or fit.icp_version_id != icp.id:
            reasons.append("fit_not_current_match")
        elif not fit.evidence_ids or (await _fit_freshness(session, workspace_id=workspace_id,
                fits=[fit], buyers_by_id={buyer_id: buyer})).get(fit.id) != "current":
            reasons.append("evidence_stale")
        if review is None or review.state != "accepted" or fit is None or review.fit_assessment_id != fit.id:
            reasons.append("review_not_accepted")
        policy = await evaluate_current_policy(session, {
            "workspace_id": workspace_id, "project_id": project_id, "company_id": company.id,
        }, "contact_research", now)
        reasons.extend(policy["reason_codes"])
        if any(role not in capability.roles for role in request.roles):
            reasons.append("unsupported_role")
        already = (await session.execute(select(ContactPoint.id).where(
            ContactPoint.workspace_id == workspace_id, ContactPoint.company_id == company.id,
            ContactPoint.type == "business_email", ContactPoint.validity == "provider_marked_valid",
            ContactPoint.quarantined.is_(False),
        ).limit(1))).scalar_one_or_none()
        if already is not None:
            reasons.append("already_researched")
        if str(buyer_id) in active_lookup_buyers:
            reasons.append("lookup_in_progress")
        reasons = list(dict.fromkeys(reasons))
        line = {"buyer_id": str(buyer_id), "buyer_version": buyer.version,
                "eligible": not reasons, "reason_codes": reasons}
        if fit is not None:
            line["assessment_id"] = str(fit.id)
        lines.append(line)
        basis_rows.append({"buyer_id": str(buyer_id), "buyer_version": buyer.version,
                           "company_id": str(company.id),
                           "fit_id": str(fit.id) if fit else None,
                           "evidence_set_hash": fit.evidence_set_hash if fit else None,
                           "review_id": str(review.id) if review else None,
                           "policy": policy, "policy_basis": await _policy_basis(
                               session, workspace_id, project_id, company),
                           "eligible": not reasons, "reason_codes": reasons})
    eligible_ids = [row["buyer_id"] for row in lines if row["eligible"]]
    max_cost = capability.max_liability.amount * len(eligible_ids)
    if max_cost > MAX_MONEY:
        raise ApiError(503, "PROVIDER_UNAVAILABLE", "quote liability exceeds fixed-point money bound")
    request_data = request.model_dump(mode="json")
    request_fingerprint = quote_hash({"actor_id": str(actor_id), "project_id": str(project_id),
                                      "request": request_data})
    context = {"actor_id": str(actor_id), "project_id": str(project_id),
               "offer_revision": project.offer_revision, "icp_id": str(icp.id),
               "icp_content_hash": icp.content_hash,
               "provider": capability.provider, "adapter_version": capability.adapter_version,
               "pricing_version": capability.pricing_version,
               "per_buyer_max_cost": format(capability.max_liability.amount, ".6f"),
               "roles": request.roles, "contact_type": request.contact_type,
               "rows": basis_rows}
    expires_at = now + QUOTE_TTL
    quote = EnrichmentQuote(
        workspace_id=workspace_id, project_id=project_id, actor_id=actor_id,
        purpose=request.purpose, selection={"request": request_data, "resolved": basis_rows,
                                            "context_hash": quote_hash(context)},
        request_hash=request_fingerprint,
        quote_hash=quote_hash({"context": context, "expires_at": expires_at.isoformat()}),
        adapter_version=capability.adapter_version, price_version=capability.pricing_version,
        roles=request.roles, contact_type=request.contact_type, eligibility=lines,
        max_cost=max_cost, status="quoted", expires_at=expires_at,
    )
    if persist:
        session.add(quote)
        await session.flush()
        await session.refresh(quote)
    return quote


def quote_data(quote: EnrichmentQuote, *, now: datetime | None = None) -> dict:
    if quote.project_id is None or quote.actor_id is None or quote.adapter_version is None:
        raise ApiError(404, "NOT_FOUND", "quote not found")
    now = now or datetime.now(timezone.utc)
    status = ("expired" if quote.status == "quoted" and
              (quote.expires_at is None or quote.expires_at <= now) else quote.status)
    eligibility = quote.eligibility or []
    return {
        "id": str(quote.id), "workspace_id": str(quote.workspace_id),
        "project_id": str(quote.project_id), "actor_id": str(quote.actor_id),
        "version": quote.version, "created_at": quote.created_at.isoformat(),
        "updated_at": quote.updated_at.isoformat(), "data_mode": "live",
        "status": status, "purpose": quote.purpose,
        "request_hash": quote.request_hash, "quote_hash": quote.quote_hash,
        "eligibility": eligibility,
        "eligible_buyer_ids": [row["buyer_id"] for row in eligibility if row["eligible"]],
        "roles": quote.roles or [], "provider_adapter_version": quote.adapter_version,
        "pricing_version": quote.price_version,
        "max_cost": {"amount": format(quote.max_cost, ".6f"), "currency": "USD"},
        "expires_at": quote.expires_at.isoformat() if quote.expires_at else now.isoformat(),
        "reservation_id": str(quote.reservation_id) if quote.reservation_id else None,
        "consumed_job_id": str(quote.consumed_job_id) if quote.consumed_job_id else None,
    }


async def require_quote(session, workspace_id: uuid.UUID, quote_id: uuid.UUID, *, lock=False) -> EnrichmentQuote:
    query = select(EnrichmentQuote).where(EnrichmentQuote.workspace_id == workspace_id,
                                          EnrichmentQuote.id == quote_id)
    quote = (await session.execute(query.with_for_update() if lock else query)).scalar_one_or_none()
    if quote is None or quote.actor_id is None or quote.project_id is None:
        raise ApiError(404, "NOT_FOUND", "quote not found")
    return quote


async def cancel_quote(session, workspace_id: uuid.UUID, quote_id: uuid.UUID,
                       actor_id: uuid.UUID, *, expected_version: int) -> EnrichmentQuote:
    quote = await require_quote(session, workspace_id, quote_id, lock=True)
    if quote.actor_id != actor_id:
        raise ApiError(403, "PERMISSION_DENIED", "only the quote actor can cancel it")
    if quote.version != expected_version:
        raise ApiError(412, "STALE_REVISION", "quote version changed")
    if quote.status != "quoted" or quote.reservation_id is not None or quote.consumed_job_id is not None:
        raise ApiError(409, "INVALID_STATE", "only an unconsumed quote can be cancelled")
    if quote.expires_at is None or quote.expires_at <= datetime.now(timezone.utc):
        raise ApiError(409, "QUOTE_EXPIRED", "quote expired")
    quote.status = "cancelled"
    quote.version += 1
    await session.flush()
    await session.refresh(quote)
    return quote
