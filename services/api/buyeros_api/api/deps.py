import contextlib
import uuid

from ..settings import get_settings

_VIEWERS = frozenset({"viewer", "operator", "reviewer", "workspace_admin"})
_WRITERS = frozenset({"operator", "workspace_admin"})

# Transcribed from the contract's `x-permitted-roles`, for the operations P9 implements.
OPERATION_ROLES: dict[str, frozenset[str]] = {
    "listWorkspaces": _VIEWERS,
    "listProjects": _VIEWERS,
    "getProject": _VIEWERS,
    "listICPVersions": _VIEWERS,
    "listBuyers": _VIEWERS,
    "getBuyer": _VIEWERS,
    "listBuyerEvidence": _VIEWERS,
    "getEvidence": _VIEWERS,
    "createBuyerSnapshot": _VIEWERS,
    "updateBuyer": frozenset({"operator", "reviewer", "workspace_admin"}),
    "reviewBuyers": frozenset({"reviewer", "workspace_admin"}),
    "listBuyerLists": _VIEWERS,
    "createBuyerList": frozenset({"operator", "reviewer", "workspace_admin"}),
    "getBuyerList": _VIEWERS,
    "renameBuyerList": frozenset({"operator", "reviewer", "workspace_admin"}),
    "changeListMemberships": frozenset({"operator", "reviewer", "workspace_admin"}),
    "previewBulkManifest": frozenset({"operator", "reviewer", "workspace_admin"}),
    "executeBulkManifest": frozenset({"operator", "reviewer", "workspace_admin"}),
    "getBulkManifest": _VIEWERS,
    "assignBuyerOwners": frozenset({"operator", "workspace_admin"}),
    "getAsyncJob": _VIEWERS,
    "getAsyncJobSummary": _VIEWERS,
    "listAsyncJobs": _VIEWERS,
    "listFilterPresets": _VIEWERS,
    "saveFilterPreset": _VIEWERS,
    "listPolicyDecisions": frozenset({"workspace_admin"}),
    "recordPolicyDecision": frozenset({"workspace_admin"}),
    "listSuppressions": frozenset({"operator", "reviewer", "workspace_admin"}),
    "createSuppression": frozenset({"workspace_admin"}),
    "removeSuppression": frozenset({"workspace_admin"}),
    "createProject": _WRITERS,
    "updateProject": frozenset({"operator", "reviewer", "workspace_admin"}),
    "archiveProject": frozenset({"workspace_admin"}),
    "saveICPVersion": _WRITERS,
    "startRun": _WRITERS,
    "listRuns": _VIEWERS,
    "getRun": _VIEWERS,
    "getRunEvents": _VIEWERS,
    "cancelRun": _WRITERS,
    "retryRun": _WRITERS,
    "quoteLookup": _WRITERS,
    "getLookupQuote": _WRITERS,
    "cancelLookupQuote": _WRITERS,
    "confirmLookup": _WRITERS,
    "getEnrichmentJob": _VIEWERS,
    "cancelEnrichmentJob": _WRITERS,
    "reconcileEnrichmentJob": frozenset({"workspace_admin"}),
    "listDrafts": _VIEWERS,
    "generateDraft": frozenset({"operator", "reviewer", "workspace_admin"}),
    "getDraft": _VIEWERS,
    "editDraft": frozenset({"operator", "reviewer", "workspace_admin"}),
    "requestDraftReview": frozenset({"operator", "reviewer", "workspace_admin"}),
    "reviewDraftGrounding": frozenset({"reviewer", "workspace_admin"}),
    "approveDraft": frozenset({"reviewer", "workspace_admin"}),
    "getUsage": _VIEWERS,
    "listOutcomes": _VIEWERS,
    "recordOutcome": frozenset({"operator", "reviewer", "workspace_admin"}),
    "correctOutcome": frozenset({"operator", "reviewer", "workspace_admin"}),
    "exportBuyers": frozenset({"operator", "reviewer", "workspace_admin"}),
    "exportBulkFailures": frozenset({"operator", "reviewer", "workspace_admin"}),
    "exportDraft": frozenset({"operator", "reviewer", "workspace_admin"}),
    "getExport": _VIEWERS,
    "downloadExport": frozenset({"operator", "reviewer", "workspace_admin"}),
    "approveICPVersion": frozenset({"reviewer", "workspace_admin"}),
    "getPreferences": _VIEWERS,
    "updatePreferences": _VIEWERS,
    "listAuditEvents": frozenset({"workspace_admin"}),
    "listMemberships": frozenset({"workspace_admin"}),
    "updateMembership": frozenset({"workspace_admin"}),
    "getReadiness": frozenset({"workspace_admin"}),
    "getCapabilities": _VIEWERS,
    "listBudgets": frozenset({"operator", "reviewer", "workspace_admin"}),
    "updateBudget": frozenset({"workspace_admin"}),
    "ingestOfferUrl": _WRITERS,
    "uploadOfferDocument": _WRITERS,
    "getOfferDocument": _VIEWERS,
    "listOfferDocuments": _VIEWERS,
    "deleteOfferDocument": _WRITERS,
}


def permitted_roles(operation_id: str) -> frozenset[str]:
    return OPERATION_ROLES.get(operation_id, frozenset())

# Engine cache keyed by (event loop, DSN).
#
# An AsyncEngine's connection pool is bound to the loop that opened it, and this
# process serves one uvicorn loop in production. Keying by loop keeps the
# singleton in production while preventing a second loop (a second TestClient, or
# an `asyncio.run` in a test) from reusing a pool created on the first one.
# `dispose_engines()` is called by the FastAPI lifespan shutdown hook.
_ENGINES: dict[tuple[object, str], object] = {}
# Rate admission commits independently so failed business requests still consume a slot.
# It must not borrow the domain pool while that request holds a tenant transaction.
_RATE_ENGINES: dict[tuple[object, str], object] = {}


def async_database_url(url: str) -> str:
    """SQLAlchemy async engines need the explicit `+psycopg` driver (as in the P8 worker)."""
    if url.startswith("postgresql+"):
        return url
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def _current_loop_key() -> object:
    import asyncio

    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        return None


def get_engine():
    """One async engine per (event loop, DSN), so tests may swap BUYEROS_DATABASE_URL."""
    from sqlalchemy.ext.asyncio import create_async_engine

    url = async_database_url(get_settings().database_url)
    key = (_current_loop_key(), url)
    engine = _ENGINES.get(key)
    if engine is None:
        engine = create_async_engine(url)
        _ENGINES[key] = engine
    return engine


def get_rate_engine():
    """A small independent pool prevents nested rate writes exhausting tenant reads."""
    from sqlalchemy.ext.asyncio import create_async_engine

    url = async_database_url(get_settings().database_url)
    key = (_current_loop_key(), url)
    engine = _RATE_ENGINES.get(key)
    if engine is None:
        engine = create_async_engine(url, pool_size=2, max_overflow=2, pool_timeout=5)
        _RATE_ENGINES[key] = engine
    return engine


async def dispose_engines() -> None:
    """Release every cached engine during application shutdown."""
    engines = list(_ENGINES.values()) + list(_RATE_ENGINES.values())
    _ENGINES.clear()
    _RATE_ENGINES.clear()
    for engine in engines:
        await engine.dispose()


def permission_for_roles(roles: list[str], permission: str) -> bool:
    """Compatibility wrapper: `permission` names the contract operation being performed."""
    allowed = permitted_roles(permission)
    if not allowed:
        return False
    if "workspace_admin" in roles:
        return True
    return bool(allowed.intersection(roles))


@contextlib.asynccontextmanager
async def tenant_scoped(workspace_id: uuid.UUID):
    from ..db.session import tenant_session

    async with tenant_session(get_engine(), workspace_id) as session:
        yield session


async def load_membership(session, *, principal, workspace_id) -> dict:
    from sqlalchemy import select

    from ..db.models import Membership
    from ..services.identity_resolver import resolve_user_id
    from .errors import ApiError

    user_id = await resolve_user_id(session, principal)
    if user_id is None:
        raise ApiError(404, "NOT_FOUND", "workspace not found")
    membership = (
        await session.execute(
            select(Membership).where(Membership.workspace_id == workspace_id, Membership.user_id == user_id)
        )
    ).scalar_one_or_none()
    if membership is None or not membership.active:
        raise ApiError(404, "NOT_FOUND", "workspace not found")
    from ..services.api_rate_limit import enforce_rate_limit
    await enforce_rate_limit(get_rate_engine(), workspace_id, user_id)
    return {"user_id": user_id, "roles": list(membership.roles)}
