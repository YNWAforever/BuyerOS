# P9 API Surface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **Build is NOT authorized by this document**; execution requires explicit approval under a dependency waiver.

**Goal:** Expose the first HTTP surface over the existing BuyerOS domain services with a fail-closed auth/tenant boundary, one working route slice, contract conformance, and generated TypeScript types.

**Architecture:** A FastAPI app factory wraps thin routers that call existing `buyeros_api` services inside a membership-checked, tenant-scoped database session. Auth is a pluggable dependency that fails closed (401) when no Auth0 verifier is configured and otherwise verifies RS256 JWTs against a cached JWKS; roles always come from the database. `contracts/openapi.proposed.yaml` stays authoritative and a conformance test enforces it.

**Tech Stack:** Python 3.12+ (installed 3.14.6), FastAPI, Pydantic v2, SQLAlchemy 2 + psycopg, pytest + httpx TestClient, uv; disposable PostgreSQL for tests.

## Global Constraints

- Canonical repository: `YNWAforever/BuyerOS`; branch `p9-api-surface` from `main` @ `4cd159a`.
- Plan-only artifact: no remote commits/pushes, deploys, cloud resources, real-data migrations, paid calls, mailboxes, or sends.
- Fail closed: with no `auth0_issuer`/`auth0_audience` configured, every route except liveness returns `401 UNAUTHENTICATED`. Roles come from Postgres membership, never token claims.
- Contract-first: `contracts/openapi.proposed.yaml` is authoritative; implemented routes match its `operationId`, method, path, and schema names. Anything outside the slice returns `501 NOT_IMPLEMENTED`.
- Live responses are `{data, request_id, data_mode:"live"}`; no demo fixture may appear in a live response.
- Mutations require `Idempotency-Key`; versioned edits require `If-Match`.
- Every unexecuted check is **NOT RUN**.

**Existing interfaces this plan consumes (already implemented):**
- `buyeros_api.settings.get_settings()` → `Settings` with `database_url`, `database_migration_url`, `auth0_issuer`, `auth0_audience`, `jwks_cache_seconds`, `environment`.
- `buyeros_api.db.session.tenant_session(engine, workspace_id)` → async context manager yielding a session with `SET LOCAL app.workspace_id`.
- `buyeros_api.db.{models,icp,policy,budget,outbox,buyers,runs,contact,drafts,outcomes}` models; `buyeros_api.db.icp.canonical_hash(content)` and `IcpVersion`, `Project`.
- `buyeros_api.db.models.{Workspace,User,Membership}`.

---

### Task 3: Membership and tenant-scoped session dependency

**Files:**
- Create: `services/api/buyeros_api/api/deps.py`
- Create: `services/api/tests/test_api_deps.py`

**Interfaces:**
- Produces: `get_engine()` (cached per process); `async def require_membership(principal, workspace_id, session) -> Membership` raising `ApiError(404)` for foreign/absent workspace and `ApiError(403)` when inactive; `permission_for_roles(roles, permission) -> bool`; `async def tenant_scoped(workspace_id)` yielding a session.
- Consumes: `Principal` (Task 2), `ApiError` (Task 1), `tenant_session`, `get_settings`.

- [ ] **Step 1: Write the failing test** (pure permission mapping, no DB)

```python
# services/api/tests/test_api_deps.py
from buyeros_api.api.deps import permission_for_roles


def test_viewer_cannot_write():
    assert permission_for_roles(["viewer"], "project.write") is False
    assert permission_for_roles(["viewer"], "project.read") is True


def test_admin_allows_everything():
    assert permission_for_roles(["admin"], "budget.write") is True


def test_unknown_role_denied():
    assert permission_for_roles(["ghost"], "project.read") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_api_deps.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# services/api/buyeros_api/api/deps.py
import contextlib
import uuid

from ..settings import get_settings

ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "viewer": frozenset({"project.read", "buyer.read", "evidence.read", "usage.read"}),
    "operator": frozenset({"project.read", "buyer.read", "evidence.read", "usage.read", "run.write", "buyer.note", "outcome.write", "quote.request"}),
    "reviewer": frozenset({"project.read", "buyer.read", "evidence.read", "usage.read", "run.write", "buyer.note", "outcome.write", "quote.request", "buyer.review", "draft.approve", "quote.confirm", "project.write"}),
    "admin": frozenset({"*"}),
}


def permission_for_roles(roles: list[str], permission: str) -> bool:
    for role in roles:
        granted = ROLE_PERMISSIONS.get(role)
        if granted and ("*" in granted or permission in granted):
            return True
    return False


@contextlib.asynccontextmanager
async def tenant_scoped(workspace_id: uuid.UUID):
    from sqlalchemy.ext.asyncio import create_async_engine

    from ..db.session import tenant_session

    engine = create_async_engine(get_settings().database_url)
    try:
        async with tenant_session(engine, workspace_id) as session:
            yield session
    finally:
        await engine.dispose()
```

Also add, in the same file, the DB-backed membership check used by routers:

```python
async def load_membership(session, *, principal, workspace_id) -> dict:
    from sqlalchemy import select, text

    from ..db.models import Membership, User
    from .errors import ApiError

    await session.execute(text("SELECT set_config('app.workspace_id', :ws, true)"), {"ws": str(workspace_id)})
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_api_deps.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add services/api/buyeros_api/api/deps.py services/api/tests/test_api_deps.py
git commit -m "feat(api): membership and tenant-scoped session dependencies"
```

---
