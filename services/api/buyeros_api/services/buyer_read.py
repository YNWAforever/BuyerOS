"""Load the contract Buyer view for a project buyer (BO-008)."""

import uuid

from sqlalchemy import func, select

from ..db.buyers import Evidence, FitAssessment, HumanReview, SourceDocument
from ..db.models import Membership
from ..db.runs import RawCandidate
from .buyer_view import buyer_data, evidence_data


async def _latest(session, model, workspace_id, buyer_id):
    return (
        await session.execute(
            select(model)
            .where(model.workspace_id == workspace_id, model.project_buyer_id == buyer_id)
            .order_by(model.created_at.desc(), model.id)
        )
    ).scalars().first()


async def _fit_freshness(session, *, workspace_id, fits, buyers_by_id) -> dict:
    """Evaluate cited source state in one tenant-scoped query per buyer page."""
    ids = set()
    malformed = set()
    for fit in fits:
        for value in fit.evidence_ids or []:
            try:
                ids.add(uuid.UUID(str(value)))
            except (ValueError, TypeError, AttributeError):
                malformed.add(fit.id)
    available = {}
    if ids:
        rows = (await session.execute(
            select(Evidence, SourceDocument, RawCandidate.canonical_company_id)
            .outerjoin(SourceDocument,
                       (SourceDocument.workspace_id == Evidence.workspace_id)
                       & (SourceDocument.id == Evidence.source_document_id))
            .outerjoin(RawCandidate,
                       (RawCandidate.workspace_id == Evidence.workspace_id)
                       & (RawCandidate.id == Evidence.raw_candidate_id))
            .where(Evidence.workspace_id == workspace_id, Evidence.id.in_(ids))
        )).all()
        available = {evidence.id: (
            evidence, evidence_data(evidence, source, mapped_company_id=mapped_company_id)["status"] == "available",
        ) for evidence, source, mapped_company_id in rows}
    result = {}
    for fit in fits:
        buyer = buyers_by_id.get(fit.project_buyer_id)
        valid = fit.id not in malformed and buyer is not None
        for value in fit.evidence_ids or []:
            try:
                evidence_id = uuid.UUID(str(value))
            except (ValueError, TypeError, AttributeError):
                valid = False
                continue
            row = available.get(evidence_id)
            if (buyer is None or row is None or not row[1] or row[0].project_id != fit.project_id
                    or row[0].company_id != buyer.company_id):
                valid = False
        result[fit.id] = "current" if valid else "stale"
    return result


async def view(session, *, workspace_id, buyer, company) -> dict:
    fit = await _latest(session, FitAssessment, workspace_id, buyer.id)
    review = await _latest(session, HumanReview, workspace_id, buyer.id)
    owner_membership_id = None
    if buyer.owner_user_id is not None:
        owner_membership_id = (
            await session.execute(
                select(Membership.id).where(
                    Membership.workspace_id == workspace_id,
                    Membership.user_id == buyer.owner_user_id,
                    Membership.active.is_(True),
                )
            )
        ).scalar_one_or_none()
    evidence_count = (
        await session.execute(
            select(func.count())
            .select_from(Evidence)
            .where(
                Evidence.workspace_id == workspace_id,
                Evidence.project_id == buyer.project_id,
                Evidence.company_id == buyer.company_id,
            )
        )
    ).scalar_one()
    review_fit = None
    if review is not None and review.fit_assessment_id is not None:
        review_fit = fit if fit is not None and fit.id == review.fit_assessment_id else (
            await session.execute(
                select(FitAssessment).where(
                    FitAssessment.workspace_id == workspace_id,
                    FitAssessment.project_buyer_id == buyer.id,
                    FitAssessment.id == review.fit_assessment_id,
                )
            )
        ).scalar_one_or_none()
    freshness = await _fit_freshness(
        session, workspace_id=workspace_id, fits=[fit] if fit else [], buyers_by_id={buyer.id: buyer},
    )
    return buyer_data(
        buyer, company, fit=fit, fit_freshness=freshness.get(fit.id, "current") if fit else "current",
        review=review, review_fit=review_fit,
        owner_membership_id=owner_membership_id, evidence_count=evidence_count,
    )


async def view_many(session, *, workspace_id, rows) -> list[dict]:
    """Render one SQL page with a bounded number of related-data queries."""
    if not rows:
        return []
    buyer_ids = [buyer.id for buyer, _ in rows]
    project_ids = {buyer.project_id for buyer, _ in rows}
    company_ids = {buyer.company_id for buyer, _ in rows}
    owner_ids = {buyer.owner_user_id for buyer, _ in rows if buyer.owner_user_id}
    fits = (
        await session.execute(
            select(FitAssessment)
            .where(FitAssessment.workspace_id == workspace_id,
                   FitAssessment.project_buyer_id.in_(buyer_ids))
            .distinct(FitAssessment.project_buyer_id)
            .order_by(FitAssessment.project_buyer_id, FitAssessment.created_at.desc(), FitAssessment.id.desc())
        )
    ).scalars().all()
    reviews = (
        await session.execute(
            select(HumanReview)
            .where(HumanReview.workspace_id == workspace_id,
                   HumanReview.project_buyer_id.in_(buyer_ids))
            .distinct(HumanReview.project_buyer_id)
            .order_by(HumanReview.project_buyer_id, HumanReview.created_at.desc(), HumanReview.id.desc())
        )
    ).scalars().all()
    fit_by_buyer = {row.project_buyer_id: row for row in fits}
    review_by_buyer = {row.project_buyer_id: row for row in reviews}
    referenced_fit_ids = {row.fit_assessment_id for row in reviews if row.fit_assessment_id}
    fit_by_id = {row.id: row for row in fits}
    missing_fit_ids = referenced_fit_ids - fit_by_id.keys()
    if missing_fit_ids:
        referenced_fits = (
            await session.execute(
                select(FitAssessment).where(FitAssessment.workspace_id == workspace_id,
                                            FitAssessment.id.in_(missing_fit_ids))
            )
        ).scalars().all()
        fit_by_id.update({row.id: row for row in referenced_fits})
    owners = {}
    if owner_ids:
        owner_rows = (
            await session.execute(
                select(Membership.user_id, Membership.id).where(
                    Membership.workspace_id == workspace_id,
                    Membership.user_id.in_(owner_ids),
                    Membership.active.is_(True),
                )
            )
        ).all()
        owners = dict(owner_rows)
    counts = (
        await session.execute(
            select(Evidence.project_id, Evidence.company_id, func.count())
            .where(Evidence.workspace_id == workspace_id,
                   Evidence.project_id.in_(project_ids),
                   Evidence.company_id.in_(company_ids))
            .group_by(Evidence.project_id, Evidence.company_id)
        )
    ).all()
    evidence_counts = {(project_id, company_id): count for project_id, company_id, count in counts}
    freshness = await _fit_freshness(
        session, workspace_id=workspace_id, fits=fits,
        buyers_by_id={buyer.id: buyer for buyer, _ in rows},
    )
    return [
        buyer_data(
            buyer, company, fit=fit_by_buyer.get(buyer.id),
            fit_freshness=freshness.get(fit_by_buyer[buyer.id].id, "current") if buyer.id in fit_by_buyer else "current",
            review=review_by_buyer.get(buyer.id),
            review_fit=fit_by_id.get(review_by_buyer[buyer.id].fit_assessment_id)
            if buyer.id in review_by_buyer else None,
            owner_membership_id=owners.get(buyer.owner_user_id),
            evidence_count=evidence_counts.get((buyer.project_id, buyer.company_id), 0),
        )
        for buyer, company in rows
    ]
