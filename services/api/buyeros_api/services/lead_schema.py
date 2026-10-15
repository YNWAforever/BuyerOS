"""Compatibility only for the two reviewed pre-feature rollback/cutover boundaries."""
from sqlalchemy import text
from ..api.errors import ApiError

LEGACY_WITHOUT_LEAD_SCHEMA = frozenset({"0039_c61_user_identities", "0054_buyer_source_checks"})


async def lead_schema_available(session):
    present = await session.scalar(text("SELECT to_regclass('public.pilot_budget_policies') IS NOT NULL"))
    if present:
        return True
    heads = list((await session.scalars(text("SELECT version_num FROM alembic_version"))).all())
    if len(heads) == 1 and heads[0] in LEGACY_WITHOUT_LEAD_SCHEMA:
        return False
    raise ApiError(409, "POLICY_BLOCKED", "lead schema boundary is unavailable")
