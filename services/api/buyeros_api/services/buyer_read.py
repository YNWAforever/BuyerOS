"""Load the contract Buyer view for a project buyer (BO-008)."""

from sqlalchemy import func, select

from ..db.buyers import Evidence, FitAssessment, HumanReview
from ..db.models import Membership
from .buyer_view import buyer_data


async def _latest(session, model, workspace_id, buyer_id):
    return (
        await session.execute(
            select(model)
            .where(model.workspace_id == workspace_id, model.project_buyer_id == buyer_id)
            .order_by(model.created_at.desc(), model.id)
        )
    ).scalars().first()


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
    return buyer_data(
        buyer, company, fit=fit, review=review,
        owner_membership_id=owner_membership_id, evidence_count=evidence_count,
    )
