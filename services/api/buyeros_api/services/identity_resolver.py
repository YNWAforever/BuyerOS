"""Resolve a verified principal to the existing canonical user; never create/link."""
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..api.auth import Principal
from ..db.models import User


async def resolve_user_id(session: AsyncSession, principal: Principal) -> uuid.UUID | None:
    return (await session.execute(select(User.id).where(
        User.issuer == principal.issuer, User.subject == principal.subject
    ))).scalar_one_or_none()
