import contextlib
import uuid

from ..settings import get_settings

ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "viewer": frozenset({"project.read", "buyer.read", "evidence.read", "usage.read"}),
    "operator": frozenset({"project.read", "buyer.read", "evidence.read", "usage.read", "run.write", "buyer.note", "outcome.write", "quote.request"}),
    "reviewer": frozenset({"project.read", "buyer.read", "evidence.read", "usage.read", "run.write", "buyer.note", "outcome.write", "quote.request", "buyer.review", "draft.approve", "quote.confirm", "project.write"}),
    "policy_admin": frozenset({"project.read", "policy.write", "suppression.write"}),
    "budget_admin": frozenset({"project.read", "budget.write", "usage.read"}),
    "workspace_admin": frozenset({"*"}),
}

_ENGINES: dict[str, object] = {}


def async_database_url(url: str) -> str:
    """SQLAlchemy async engines need the explicit `+psycopg` driver (as in the P8 worker)."""
    if url.startswith("postgresql+"):
        return url
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def get_engine():
    """One async engine per distinct DSN, so tests may swap BUYEROS_DATABASE_URL."""
    from sqlalchemy.ext.asyncio import create_async_engine

    url = async_database_url(get_settings().database_url)
    engine = _ENGINES.get(url)
    if engine is None:
        engine = create_async_engine(url)
        _ENGINES[url] = engine
    return engine


def permission_for_roles(roles: list[str], permission: str) -> bool:
    for role in roles:
        granted = ROLE_PERMISSIONS.get(role)
        if granted and ("*" in granted or permission in granted):
            return True
    return False


@contextlib.asynccontextmanager
async def tenant_scoped(workspace_id: uuid.UUID):
    from ..db.session import tenant_session

    async with tenant_session(get_engine(), workspace_id) as session:
        yield session


async def load_membership(session, *, principal, workspace_id) -> dict:
    from sqlalchemy import select

    from ..db.models import Membership, User
    from .errors import ApiError

    user = (
        await session.execute(select(User).where(User.issuer == principal.issuer, User.subject == principal.subject))
    ).scalar_one_or_none()
    if user is None:
        raise ApiError(404, "NOT_FOUND", "workspace not found")
    membership = (
        await session.execute(
            select(Membership).where(Membership.workspace_id == workspace_id, Membership.user_id == user.id)
        )
    ).scalar_one_or_none()
    if membership is None or not membership.active:
        raise ApiError(404, "NOT_FOUND", "workspace not found")
    return {"user_id": user.id, "roles": list(membership.roles)}
