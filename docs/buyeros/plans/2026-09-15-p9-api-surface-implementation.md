# P9 API Surface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **Build is NOT authorized by this document**; execution requires explicit approval under a dependency waiver.

**Goal:** Expose the first HTTP surface over the existing BuyerOS domain services with a fail-closed auth/tenant boundary, one working route slice, contract conformance, and generated TypeScript types.

**Architecture:** A FastAPI app factory wraps thin routers that call existing `buyeros_api` services inside a membership-checked, tenant-scoped database session. Auth is a pluggable dependency that fails closed (401) when no Auth0 verifier is configured and otherwise verifies RS256 JWTs against a cached JWKS; roles always come from the database. `contracts/openapi.proposed.yaml` stays authoritative and a conformance test enforces it.

**Tech Stack:** Python 3.12+ (installed 3.14.6), FastAPI, Pydantic v2, SQLAlchemy 2 + psycopg, pytest + httpx TestClient, uv; disposable PostgreSQL for tests.

## Global Constraints

- Canonical repository: `YNWAforever/BuyerOS`; branch `p9-api-surface` from `main` @ `4cd159a`.
- Plan-only artifact: no remote commits/pushes, deploys, cloud resources, real-data migrations, paid calls, mailboxes, or sends.
- Fail closed: with no `auth0_issuer`/`auth0_audience` configured, every route except liveness returns `401 UNAUTHENTICATED`. Roles come from Postgres membership, never token claims.
- Contract-first: `contracts/openapi.proposed.yaml` is authoritative; implemented routes match its `operationId`, method, path, and schema names. `GET /health/live` is a **non-contract liveness probe only** (never the authenticated readiness signal); readiness and capabilities live at their declared `/v1/workspaces/{workspace_id}/...` contract paths. Operations outside the implemented slice are registered as explicit `501 NOT_IMPLEMENTED` on their **declared** contract path+method ??no invented or parallel endpoint (see Task 6).
- Live responses are `{data, request_id, data_mode:"live"}`; no demo fixture may appear in a live response.
- Mutations require `Idempotency-Key`; versioned edits require `If-Match`.
- Every unexecuted check is **NOT RUN**.

**Existing interfaces this plan consumes (already implemented):**
- `buyeros_api.settings.get_settings()` ??`Settings` with `database_url`, `database_migration_url`, `auth0_issuer`, `auth0_audience`, `jwks_cache_seconds`, `environment`.
- `buyeros_api.db.session.tenant_session(engine, workspace_id)` ??async context manager yielding a session with `SET LOCAL app.workspace_id`.
- `buyeros_api.db.{models,icp,policy,budget,outbox,buyers,runs,contact,drafts,outcomes}` models; `buyeros_api.db.icp.canonical_hash(content)` and `IcpVersion`, `Project`.
- `buyeros_api.db.models.{Workspace,User,Membership}`.

---

### Task 1: App factory, request id, error envelope

**Files:**
- Create: `services/api/buyeros_api/api/__init__.py`
- Create: `services/api/buyeros_api/api/errors.py`
- Create: `services/api/buyeros_api/api/app.py`
- Create: `services/api/tests/test_api_app.py`

**Interfaces:**
- Produces: `ApiError(status_code: int, code: str, message: str, retryable: bool = False)` exception; `error_handler(request, exc)`; `envelope(data, request_id) -> dict`; `create_app() -> FastAPI`; `app` module-level for `uvicorn`.
- Consumes: `get_settings()`.

- [ ] **Step 1: Write the failing test**

```python
# services/api/tests/test_api_app.py
from fastapi.testclient import TestClient

from buyeros_api.api.app import create_app


def test_error_envelope_shape():
    app = create_app()

    @app.get("/boom")
    async def boom():
        from buyeros_api.api.errors import ApiError

        raise ApiError(409, "IDEMPOTENCY_CONFLICT", "conflict")

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/boom")
    body = response.json()
    assert response.status_code == 409
    assert body["code"] == "IDEMPOTENCY_CONFLICT"
    assert body["retryable"] is False
    assert "request_id" in body


def test_request_id_header_is_returned():
    app = create_app()

    @app.get("/ok")
    async def ok():
        return {"data": {"ok": True}, "request_id": "x", "data_mode": "live"}

    client = TestClient(app)
    response = client.get("/ok", headers={"X-Request-ID": "abc"})
    assert response.headers["X-Request-ID"] == "abc"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_api_app.py -v` (cwd `services/api`)
Expected: FAIL ??`ModuleNotFoundError: buyeros_api.api`.

- [ ] **Step 3: Write minimal implementation**

```python
# services/api/buyeros_api/api/__init__.py
"""HTTP API surface (P9)."""
```

```python
# services/api/buyeros_api/api/errors.py
from fastapi import Request
from fastapi.responses import JSONResponse


class ApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str, retryable: bool = False):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.retryable = retryable


def envelope(data, request_id: str) -> dict:
    return {"data": data, "request_id": request_id, "data_mode": "live"}


async def error_handler(request: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.code,
            "message": exc.message,
            "request_id": getattr(request.state, "request_id", ""),
            "retryable": exc.retryable,
        },
    )
```

```python
# services/api/buyeros_api/api/app.py
import uuid

from fastapi import FastAPI, Request

from .errors import ApiError, error_handler


def create_app() -> FastAPI:
    app = FastAPI(title="FIMMICK BuyerOS domain API", version="0.1.0")
    app.add_exception_handler(ApiError, error_handler)

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request.state.request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    return app


app = create_app()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_api_app.py -v`
Expected: PASS (2 passed). Add `fastapi`, `httpx` and `uvicorn` to `services/api/pyproject.toml` dependencies as part of this task, then `uv sync`.

- [ ] **Step 5: Commit**

```bash
git add services/api/pyproject.toml services/api/buyeros_api/api services/api/tests/test_api_app.py
git commit -m "feat(api): app factory with request id and error envelope"
```

---

### Task 2: Fail-closed auth dependency and JWT verification

**Files:**
- Create: `services/api/buyeros_api/api/auth.py`
- Create: `services/api/tests/test_api_auth.py`

**Interfaces:**
- Produces: `Principal(issuer: str, subject: str)`; `claims_to_principal(claims, issuer, audience, now=None) -> Principal` raising `AuthError`; `async def get_principal(request) -> Principal`; `jwks_uri_for(issuer) -> str`.
- Consumes: `get_settings()`, `AuthError` (add to `errors.py` or define here).

- [ ] **Step 1: Write the failing test**

```python
# services/api/tests/test_api_auth.py
import pytest

from buyeros_api.api.auth import AuthError, claims_to_principal, jwks_uri_for


def test_missing_configuration_fails_closed():
    from buyeros_api.api.auth import principal_from_token

    with pytest.raises(AuthError):
        principal_from_token("whatever", issuer=None, audience=None)


def test_wrong_audience_rejected():
    claims = {"iss": "https://t.example/", "aud": "other", "exp": 9999999999, "sub": "auth0|1"}
    with pytest.raises(AuthError):
        claims_to_principal(claims, issuer="https://t.example/", audience="buyeros-api")


def test_valid_claims_ok():
    claims = {"iss": "https://t.example/", "aud": "buyeros-api", "exp": 9999999999, "sub": "auth0|1"}
    principal = claims_to_principal(claims, issuer="https://t.example/", audience="buyeros-api")
    assert principal.subject == "auth0|1"


def test_jwks_uri_derivation():
    assert jwks_uri_for("https://t.example/") == "https://t.example/.well-known/jwks.json"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_api_auth.py -v`
Expected: FAIL ??`ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# services/api/buyeros_api/api/auth.py
import time
from dataclasses import dataclass

from fastapi import Request

from ..settings import get_settings


class AuthError(Exception):
    pass


@dataclass(frozen=True)
class Principal:
    issuer: str
    subject: str


def jwks_uri_for(issuer: str) -> str:
    return issuer.rstrip("/") + "/.well-known/jwks.json"


def principal_from_token(token: str, *, issuer: str | None, audience: str | None) -> Principal:
    """Fail closed when unconfigured; otherwise verify and map claims."""
    if not issuer or not audience:
        raise AuthError("live authentication is not configured")
    raise AuthError("token verification is enabled at BO-004; use claims_to_principal in tests")


def claims_to_principal(claims: dict, *, issuer: str, audience: str, now: int | None = None) -> Principal:
    now = now or int(time.time())
    if claims.get("iss") != issuer:
        raise AuthError("bad issuer")
    aud = claims.get("aud")
    if isinstance(aud, list):
        if audience not in aud:
            raise AuthError("bad audience")
    elif aud != audience:
        raise AuthError("bad audience")
    if int(claims.get("exp", 0)) <= now:
        raise AuthError("expired")
    if not claims.get("sub"):
        raise AuthError("missing subject")
    return Principal(issuer=issuer, subject=str(claims["sub"]))


async def get_principal(request: Request) -> Principal:
    from .errors import ApiError

    settings = get_settings()
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise ApiError(401, "UNAUTHENTICATED", "missing bearer token")
    try:
        return principal_from_token(
            header.removeprefix("Bearer ").strip(),
            issuer=settings.auth0_issuer,
            audience=settings.auth0_audience,
        )
    except AuthError as exc:
        raise ApiError(401, "UNAUTHENTICATED", str(exc)) from exc
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_api_auth.py -v`
Expected: PASS (4 passed). Note: full JWKS/RS256 verification is wired in BO-004 once B-IDENTITY supplies issuer/audience; `principal_from_token` intentionally stays fail-closed until then.

- [ ] **Step 5: Commit**

```bash
git add services/api/buyeros_api/api/auth.py services/api/tests/test_api_auth.py
git commit -m "feat(api): fail-closed auth dependency and claim validation"
```

---

### Task 3: Membership and tenant-scoped session dependency

**Files:**
- Create: `services/api/buyeros_api/api/deps.py`
- Create: `services/api/tests/test_api_deps.py`

**Interfaces:**
- Produces: `async_database_url(url) -> str`; `get_engine()` (reused per distinct DSN); `permitted_roles(operation_id) -> frozenset[str]` and `permission_for_roles(roles, permission) -> bool`; `async def tenant_scoped(workspace_id)` yielding a session with the tenant context set; `async def load_membership(session, *, principal, workspace_id) -> dict` raising `ApiError(404)` for a foreign/absent workspace and returning `{user_id, roles}` only for an active membership.
- Consumes: `Principal` (Task 2), `ApiError` (Task 1), `tenant_session`, `get_settings`.
- Role names match the contract `Workspace.roles` enum: `viewer`, `operator`, `reviewer`, `policy_admin`, `budget_admin`, `workspace_admin`.
- **Authorization is the contract's `x-permitted-roles`, transcribed verbatim per operation.** The old role-bucket map was wrong in three ways (it denied `operator` on `createProject`, allowed `reviewer` on `createProject`/`saveICPVersion`, and granted `policy_admin`/`budget_admin` read permissions no contract operation lists), so it is replaced by an `OPERATION_ROLES` table keyed by `operationId`, copied from the contract for exactly the operations P9 implements:
  - `listWorkspaces`, `listProjects`, `getProject`, `listICPVersions`, `listBuyers`, `getBuyer` -> `viewer`, `operator`, `reviewer`, `workspace_admin`
  - `createProject` -> `operator`, `workspace_admin`
  - `updateProject` -> `operator`, `reviewer`, `workspace_admin`
  - `saveICPVersion` -> `operator`, `workspace_admin`
  - `approveICPVersion` -> `reviewer`, `workspace_admin`
  - `getReadiness` -> `workspace_admin` (BO-004, the only admin-only implemented path)
  - `getCapabilities` -> `viewer`, `operator`, `reviewer`, `workspace_admin` (BO-006 differs from BO-004; transcribed separately)

  `permission_for_roles` is a thin compatibility wrapper over `permitted_roles`; routers gate on the **operation they implement**, so a `reviewer` is allowed `updateProject` but not `createProject`. Out-of-slice operations (whose permissions differ) are not modeled, because they return `501` before any role check.
- The engine cache is keyed by `(running event loop, DSN)`: an `AsyncEngine`'s pool is bound to the loop that opened it, so production keeps one engine per DSN while a second loop (a second `TestClient`, an `asyncio.run`) cannot reuse a foreign pool. `dispose_engines()` is the release hook; wiring it to an app lifespan is deferred to BO-004.

```python
# services/api/tests/test_api_deps.py
from buyeros_api.api.deps import permission_for_roles


def test_viewer_cannot_write():
    assert permission_for_roles(["viewer"], "createProject") is False
    assert permission_for_roles(["viewer"], "listProjects") is True


def test_workspace_admin_allows_everything():
    assert permission_for_roles(["workspace_admin"], "approveICPVersion") is True


def test_unknown_role_denied():
    assert permission_for_roles(["ghost"], "listProjects") is False


def test_operator_creates_projects_but_cannot_approve_icp():
    assert permission_for_roles(["operator"], "createProject") is True
    assert permission_for_roles(["operator"], "approveICPVersion") is False


def test_reviewer_updates_and_approves_but_cannot_create():
    assert permission_for_roles(["reviewer"], "approveICPVersion") is True
    assert permission_for_roles(["reviewer"], "updateProject") is True
    assert permission_for_roles(["reviewer"], "createProject") is False


def test_admins_without_contract_read_grants_are_denied_reads():
    assert permission_for_roles(["policy_admin"], "listProjects") is False
    assert permission_for_roles(["budget_admin"], "listBuyers") is False


CONTRACT_ROLES = {
    "listWorkspaces": frozenset({"viewer", "operator", "reviewer", "workspace_admin"}),
    "listProjects": frozenset({"viewer", "operator", "reviewer", "workspace_admin"}),
    "getProject": frozenset({"viewer", "operator", "reviewer", "workspace_admin"}),
    "listICPVersions": frozenset({"viewer", "operator", "reviewer", "workspace_admin"}),
    "listBuyers": frozenset({"viewer", "operator", "reviewer", "workspace_admin"}),
    "getBuyer": frozenset({"viewer", "operator", "reviewer", "workspace_admin"}),
    "createProject": frozenset({"operator", "workspace_admin"}),
    "updateProject": frozenset({"operator", "reviewer", "workspace_admin"}),
    "saveICPVersion": frozenset({"operator", "workspace_admin"}),
    "approveICPVersion": frozenset({"reviewer", "workspace_admin"}),
    "getReadiness": frozenset({"workspace_admin"}),
    "getCapabilities": frozenset({"viewer", "operator", "reviewer", "workspace_admin"}),
}


def test_operation_roles_are_verbatim_from_the_contract():
    from buyeros_api.api.deps import permitted_roles

    for operation_id, roles in CONTRACT_ROLES.items():
        assert permitted_roles(operation_id) == roles, operation_id
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_api_deps.py -v`
Expected: FAIL ??`ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# services/api/buyeros_api/api/deps.py
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
    "createProject": _WRITERS,
    "updateProject": frozenset({"operator", "reviewer", "workspace_admin"}),
    "saveICPVersion": _WRITERS,
    "approveICPVersion": frozenset({"reviewer", "workspace_admin"}),
    "getReadiness": frozenset({"workspace_admin"}),
    "getCapabilities": _VIEWERS,
}


def permitted_roles(operation_id: str) -> frozenset[str]:
    return OPERATION_ROLES.get(operation_id, frozenset())


def permission_for_roles(roles: list[str], permission: str) -> bool:
    """Compatibility wrapper: `permission` names the contract operation being performed."""
    allowed = permitted_roles(permission)
    if "workspace_admin" in roles:
        return True
    return bool(allowed.intersection(roles))


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


async def dispose_engines() -> None:
    """Release every cached engine. NOT wired to an app lifespan in P9 (deferred to BO-004)."""
    engines = list(_ENGINES.values())
    _ENGINES.clear()
    for engine in engines:
        await engine.dispose()


@contextlib.asynccontextmanager
async def tenant_scoped(workspace_id: uuid.UUID):
    from ..db.session import tenant_session

    async with tenant_session(get_engine(), workspace_id) as session:
        yield session
```

Also add, in the same file, the DB-backed membership check used by routers:

```python
async def load_membership(session, *, principal, workspace_id) -> dict:
    """Callers pass a session from `tenant_scoped`, which already set the
    transaction-local `app.workspace_id`; do not set it again here."""
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_api_deps.py -v`
Expected: PASS (12 passed).

- [ ] **Step 5: Commit**

```bash
git add services/api/buyeros_api/api/deps.py services/api/tests/test_api_deps.py
git commit -m "feat(api): membership and tenant-scoped session dependencies"
```

---

### Task 4: Liveness, authenticated readiness and capabilities routes

**Files:**
- Create: `services/api/buyeros_api/api/routes/__init__.py`
- Create: `services/api/buyeros_api/api/routes/health.py`
- Modify: `services/api/buyeros_api/api/app.py`
- Create: `services/api/tests/test_api_health.py`

**Interfaces:**
- Produces: `GET /health/live` (non-contract liveness probe; always 200, no auth, no secrets); the contract routes `GET /v1/workspaces/{workspace_id}/readiness` (`getReadiness`, `ReadinessResponse`) and `GET /v1/workspaces/{workspace_id}/capabilities` (`getCapabilities`, `CapabilityPageResponse`), both Bearer-authenticated; pure builders `readiness_payload()` (`{ready, database, queue, worker, checked_at}`) and `capabilities_payload()` (`{items, offset, limit, total}`).
- Consumes: `create_app`, `get_settings`, `get_principal` (Task 2), `tenant_scoped`/`load_membership`/`permission_for_roles` (Task 3). The workspace-scoped routes enforce membership (foreign/absent workspace ??non-enumerating `404`; insufficient role ??`403`) before reporting state.

**Contract note (pre-flight correction #2):** `/health/ready` is **not** a contract path and is dropped. Readiness is the authenticated contract route `/v1/workspaces/{workspace_id}/readiness`; `/health/live` remains a non-contract liveness probe only. The `Readiness` schema is `{ready, database, queue, worker, checked_at}` (no `api`/`providers`/`policy` keys) and `additionalProperties: false`.

- [ ] **Step 1: Write the failing test**

```python
# services/api/tests/test_api_health.py
from fastapi.testclient import TestClient

from buyeros_api.api.app import create_app
from buyeros_api.api.routes.health import capabilities_payload, readiness_payload

WORKSPACE = "11111111-1111-4111-8111-111111111111"


def test_liveness_needs_no_auth():
    client = TestClient(create_app())
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "ok"


def test_readiness_and_capabilities_require_auth():
    client = TestClient(create_app(), raise_server_exceptions=False)
    for path in (f"/v1/workspaces/{WORKSPACE}/readiness", f"/v1/workspaces/{WORKSPACE}/capabilities"):
        response = client.get(path)
        assert response.status_code == 401, path
        assert response.json()["code"] == "UNAUTHENTICATED"


def test_readiness_payload_matches_contract_without_secrets():
    data = readiness_payload()
    assert set(data) == {"ready", "database", "queue", "worker", "checked_at"}
    assert "password" not in str(data).lower()
    assert "postgresql://" not in str(data)


def test_capabilities_payload_matches_contract_without_secrets():
    page = capabilities_payload()
    assert set(page) == {"items", "offset", "limit", "total"}
    assert {item["name"] for item in page["items"]} == {
        "research", "contact_enrichment", "draft_generation", "mailbox", "crm",
    }
    for item in page["items"]:
        assert item["status"] in {"unconfigured", "blocked", "ready", "degraded", "disabled"}
        assert "password" not in str(item).lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_api_health.py -v`
Expected: FAIL ??`ModuleNotFoundError: buyeros_api.api.routes` / 404.

- [ ] **Step 3: Write minimal implementation**

```python
# services/api/buyeros_api/api/routes/__init__.py
"""Route modules."""
```

```python
# services/api/buyeros_api/api/routes/health.py
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request

from ..auth import Principal, get_principal

router = APIRouter(tags=["health"])

CAPABILITY_NAMES = ("research", "contact_enrichment", "draft_generation", "mailbox", "crm")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def readiness_payload() -> dict:
    """Contract `Readiness` shape. No credential, DSN or provider detail is ever included."""
    return {
        "ready": False,
        "database": "unavailable",
        "queue": "unavailable",
        "worker": "unavailable",
        "checked_at": _now(),
    }


def capabilities_payload() -> dict:
    """Contract `CapabilityPage` shape; live providers stay disabled in this phase."""
    now = _now()
    items = [
        {
            "name": name,
            "status": "disabled" if name in {"mailbox", "crm"} else "unconfigured",
            "reason_codes": ["live_providers_not_activated"],
            "checked_at": now,
            "billable": False,
        }
        for name in CAPABILITY_NAMES
    ]
    return {"items": items, "offset": 0, "limit": len(items), "total": len(items)}


@router.get("/health/live")
async def live() -> dict:
    """Non-contract liveness probe only: no auth and no dependency or secret disclosure."""
    return {
        "data": {"status": "ok", "service": "buyeros-api", "timestamp": _now()},
        "request_id": "",
        "data_mode": "live",
    }


@router.get("/v1/workspaces/{workspace_id}/readiness")
async def readiness(workspace_id: uuid.UUID, request: Request, principal: Principal = Depends(get_principal)) -> dict:
    from ..deps import load_membership, permission_for_roles, tenant_scoped
    from ..errors import ApiError, envelope

    async with tenant_scoped(workspace_id) as session:
        membership = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(membership["roles"], "getReadiness"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
    return envelope(readiness_payload(), request.state.request_id)


@router.get("/v1/workspaces/{workspace_id}/capabilities")
async def capabilities(workspace_id: uuid.UUID, request: Request, principal: Principal = Depends(get_principal)) -> dict:
    from ..deps import load_membership, permission_for_roles, tenant_scoped
    from ..errors import ApiError, envelope

    async with tenant_scoped(workspace_id) as session:
        membership = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(membership["roles"], "getCapabilities"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
    return envelope(capabilities_payload(), request.state.request_id)
```

In `app.py`, import and include the router inside `create_app()`:

```python
from .routes.health import router as health_router
...
    app.include_router(health_router)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_api_health.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add services/api/buyeros_api/api/routes services/api/buyeros_api/api/app.py services/api/tests/test_api_health.py
git commit -m "feat(api): liveness plus authenticated readiness and capabilities routes"
```

---

### Task 5: Workspaces, projects and ICP routes (auth required)

**Files:**
- Create: `services/api/buyeros_api/services/icp_service.py`
- Create: `services/api/buyeros_api/api/routes/workspaces.py`
- Create: `services/api/buyeros_api/api/routes/projects.py`
- Create: `services/api/buyeros_api/api/routes/icp.py`
- Modify: `services/api/buyeros_api/api/app.py`
- Create: `services/api/tests/test_api_routes_contract.py`

**Interfaces:**
- Produces: `GET /v1/workspaces` (`listWorkspaces`); `GET|POST /v1/workspaces/{workspace_id}/projects` (`listProjects`/`createProject`); `GET /v1/workspaces/{workspace_id}/projects/{project_id}` (`getProject`); `GET|POST /v1/workspaces/{workspace_id}/projects/{project_id}/icp-versions` (`listICPVersions`/`saveICPVersion`); `POST /v1/workspaces/{workspace_id}/icp-versions/{icp_version_id}/approve` (`approveICPVersion`).
- Consumes: `get_principal` (Task 2), `get_engine`/`tenant_scoped`/`load_membership`/`permission_for_roles` (Task 3), `Project`/`IcpVersion`/`canonical_hash` (existing), `envelope`/`ApiError`.

**Contract notes (pre-flight corrections #1 and #3):**
1. Approve is `POST /v1/workspaces/{workspace_id}/icp-versions/{icp_version_id}/approve` with a UUID `icp_version_id` path parameter ??**not** `.../projects/{project_id}/icp-versions/{number}/approve`. The ICP router therefore carries `prefix="/v1/workspaces/{workspace_id}"`: list/save are at `/projects/{project_id}/icp-versions`, approve at `/icp-versions/{icp_version_id}/approve`.
2. `memberships` is `FORCE ROW LEVEL SECURITY`, so the old join of `memberships` with no `app.workspace_id` always returned zero rows. `list_workspaces` must resolve the `User` by immutable `(issuer, subject)` first (`users` is **not** RLS-protected, `workspaces` is not either), then for each candidate workspace set the **transaction-local** tenant context and read that membership.
3. Plan-defect fix: `buyeros_api.services.icp_service` was specified in the P2 plan but never implemented; this task creates it (Step 3) so the approve handler's hash check reuses its `StaleRevision`/`verify_approval_hash` names.

- [ ] **Step 1: Write the failing test**

```python
# services/api/tests/test_api_routes_contract.py
from fastapi.testclient import TestClient

from buyeros_api.api.app import create_app

WORKSPACE = "11111111-1111-4111-8111-111111111111"
PROJECT = "22222222-2222-4222-8222-222222222222"
ICP = "33333333-3333-4333-8333-333333333333"


def test_unauthenticated_requests_are_rejected():
    client = TestClient(create_app(), raise_server_exceptions=False)
    requests = [
        ("GET", "/v1/workspaces"),
        ("GET", f"/v1/workspaces/{WORKSPACE}/projects"),
        ("POST", f"/v1/workspaces/{WORKSPACE}/projects"),
        ("GET", f"/v1/workspaces/{WORKSPACE}/projects/{PROJECT}"),
        ("GET", f"/v1/workspaces/{WORKSPACE}/projects/{PROJECT}/icp-versions"),
        ("POST", f"/v1/workspaces/{WORKSPACE}/projects/{PROJECT}/icp-versions"),
        ("POST", f"/v1/workspaces/{WORKSPACE}/icp-versions/{ICP}/approve"),
    ]
    for method, path in requests:
        response = client.request(method, path, json={})
        assert response.status_code == 401, (method, path)
        assert response.json()["code"] == "UNAUTHENTICATED"


def test_implemented_routes_match_openapi_operation_ids():
    import yaml
    from pathlib import Path

    spec = yaml.safe_load(Path("../../docs/buyeros/contracts/openapi.proposed.yaml").read_text(encoding="utf-8"))
    paths = spec["paths"]
    expected = (
        ("/v1/workspaces", "get", "listWorkspaces"),
        ("/v1/workspaces/{workspace_id}/projects", "get", "listProjects"),
        ("/v1/workspaces/{workspace_id}/projects", "post", "createProject"),
        ("/v1/workspaces/{workspace_id}/projects/{project_id}", "get", "getProject"),
        ("/v1/workspaces/{workspace_id}/projects/{project_id}/icp-versions", "get", "listICPVersions"),
        ("/v1/workspaces/{workspace_id}/projects/{project_id}/icp-versions", "post", "saveICPVersion"),
        ("/v1/workspaces/{workspace_id}/icp-versions/{icp_version_id}/approve", "post", "approveICPVersion"),
    )
    for path, method, operation_id in expected:
        assert path in paths, path
        assert method in paths[path], (path, method)
        assert paths[path][method]["operationId"] == operation_id
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_api_routes_contract.py -v`
Expected: FAIL ??routes return 404 (not registered) / `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# services/api/buyeros_api/services/icp_service.py
"""Hash-bound ICP approval helpers (BO-007).

The P2 plan specified this module but it was never landed; P9 Task 5 creates it
so the ICP approve route reuses the same names. ICP content is immutable once
saved, so approval binds the exact ``content_hash``.
"""


class StaleRevision(Exception):
    pass


class AlreadyApproved(Exception):
    pass


def verify_approval_hash(row, expected_hash: str) -> None:
    if row.content_hash != expected_hash:
        raise StaleRevision("content hash changed; reload the profile")
```

```python
# services/api/buyeros_api/api/routes/workspaces.py
from fastapi import APIRouter, Depends, Request

from ..auth import Principal, get_principal
from ..errors import envelope

router = APIRouter(prefix="/v1/workspaces", tags=["workspaces"])


@router.get("")
async def list_workspaces(request: Request, principal: Principal = Depends(get_principal)) -> dict:
    from sqlalchemy import select, text

    from ...db.models import Membership, User, Workspace
    from ..deps import get_engine

    items: list[dict] = []
    async with get_engine().connect() as conn:
        # `users` is not RLS-protected: resolve the actor by immutable (issuer, subject).
        user = (
            await conn.execute(select(User).where(User.issuer == principal.issuer, User.subject == principal.subject))
        ).scalar_one_or_none()
        if user is not None:
            # `workspaces` is not RLS-protected either; enumerate candidates, then read the
            # membership only under that workspace's transaction-local tenant context.
            candidates = (await conn.execute(select(Workspace.id, Workspace.name))).all()
            for workspace_id, name in candidates:
                await conn.execute(
                    text("SELECT set_config('app.workspace_id', :ws, true)"), {"ws": str(workspace_id)}
                )
                membership = (
                    await conn.execute(
                        select(Membership).where(
                            Membership.workspace_id == workspace_id,
                            Membership.user_id == user.id,
                            Membership.active.is_(True),
                        )
                    )
                ).scalar_one_or_none()
                if membership is not None:
                    items.append(
                        {
                            "id": str(workspace_id),
                            "name": name,
                            "roles": list(membership.roles),
                            "data_mode": "live",
                        }
                    )
    return envelope(
        {"items": items, "offset": 0, "limit": len(items), "total": len(items)}, request.state.request_id
    )
```

```python
# services/api/buyeros_api/api/routes/projects.py
import uuid

from fastapi import APIRouter, Depends, Header, Request

from ..auth import Principal, get_principal
from ..errors import ApiError, envelope

router = APIRouter(prefix="/v1/workspaces/{workspace_id}/projects", tags=["projects"])


def _project_data(project) -> dict:
    return {
        "id": str(project.id),
        "workspace_id": str(project.workspace_id),
        "name": project.name,
        "status": project.status,
    }


@router.get("")
async def list_projects(workspace_id: uuid.UUID, request: Request, principal: Principal = Depends(get_principal)) -> dict:
    from sqlalchemy import select

    from ...db.icp import Project
    from ..deps import load_membership, permission_for_roles, tenant_scoped

    async with tenant_scoped(workspace_id) as session:
        membership = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(membership["roles"], "listProjects"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        rows = (await session.execute(select(Project).where(Project.workspace_id == workspace_id))).scalars().all()
        items = [_project_data(p) for p in rows]
    return envelope({"items": items, "offset": 0, "limit": len(items), "total": len(items)}, request.state.request_id)


@router.post("", status_code=201)
async def create_project(
    workspace_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(get_principal),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    from ...db.icp import Project
    from ..deps import load_membership, permission_for_roles, tenant_scoped

    if not idempotency_key:
        raise ApiError(400, "INVALID_REQUEST", "Idempotency-Key header is required")
    body = await request.json()
    name = body.get("name")
    if not isinstance(name, str) or not (2 <= len(name) <= 160):
        raise ApiError(422, "INVALID_REQUEST", "name must be 2..160 characters")

    async with tenant_scoped(workspace_id) as session:
        membership = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(membership["roles"], "createProject"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        project = Project(workspace_id=workspace_id, name=name)
        session.add(project)
        await session.flush()
        data = _project_data(project)
    return envelope(data, request.state.request_id)


@router.get("/{project_id}")
async def get_project(
    workspace_id: uuid.UUID, project_id: uuid.UUID, request: Request, principal: Principal = Depends(get_principal)
) -> dict:
    from sqlalchemy import select

    from ...db.icp import Project
    from ..deps import load_membership, permission_for_roles, tenant_scoped

    async with tenant_scoped(workspace_id) as session:
        membership = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(membership["roles"], "getProject"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        project = (
            await session.execute(
                select(Project).where(Project.workspace_id == workspace_id, Project.id == project_id)
            )
        ).scalar_one_or_none()
        if project is None:
            raise ApiError(404, "NOT_FOUND", "project not found")
        data = _project_data(project)
    return envelope(data, request.state.request_id)
```

```python
# services/api/buyeros_api/api/routes/icp.py
import uuid

from fastapi import APIRouter, Depends, Header, Request

from ..auth import Principal, get_principal
from ..errors import ApiError, envelope

router = APIRouter(prefix="/v1/workspaces/{workspace_id}", tags=["icp"])

_CONTENT_KEYS = (
    "offer_document_ids", "offer_facts", "requirements", "markets",
    "buyer_types", "languages", "desired_roles",
)


def _icp_data(row) -> dict:
    content = row.content or {}
    return {
        "id": str(row.id),
        "workspace_id": str(row.workspace_id),
        "project_id": str(row.project_id),
        "number": row.number,
        "content_hash": row.content_hash,
        "status": "approved" if row.approved_at else "saved",
        "approved_at": row.approved_at.isoformat() if row.approved_at else None,
        "approved_by": str(row.approved_by) if row.approved_by else None,
        "requirements": content.get("requirements", []),
        "markets": content.get("markets", []),
        "buyer_types": content.get("buyer_types", []),
        "languages": content.get("languages", []),
        "offer_facts": content.get("offer_facts", []),
    }


@router.get("/projects/{project_id}/icp-versions")
async def list_icp_versions(
    workspace_id: uuid.UUID, project_id: uuid.UUID, request: Request, principal: Principal = Depends(get_principal)
) -> dict:
    from sqlalchemy import select

    from ...db.icp import IcpVersion
    from ..deps import load_membership, permission_for_roles, tenant_scoped

    async with tenant_scoped(workspace_id) as session:
        membership = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(membership["roles"], "listICPVersions"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        rows = (
            await session.execute(
                select(IcpVersion).where(
                    IcpVersion.workspace_id == workspace_id, IcpVersion.project_id == project_id
                )
            )
        ).scalars().all()
        items = [_icp_data(v) for v in rows]
    return envelope({"items": items, "offset": 0, "limit": len(items), "total": len(items)}, request.state.request_id)


@router.post("/projects/{project_id}/icp-versions", status_code=201)
async def save_icp_version(
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(get_principal),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    from sqlalchemy import func, select

    from ...db.icp import IcpVersion, Project, canonical_hash
    from ..deps import load_membership, permission_for_roles, tenant_scoped

    if not idempotency_key:
        raise ApiError(400, "INVALID_REQUEST", "Idempotency-Key header is required")
    body = await request.json()
    content = {key: body[key] for key in _CONTENT_KEYS if key in body}

    async with tenant_scoped(workspace_id) as session:
        membership = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(membership["roles"], "saveICPVersion"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        project = (
            await session.execute(
                select(Project).where(Project.workspace_id == workspace_id, Project.id == project_id)
            )
        ).scalar_one_or_none()
        if project is None:
            raise ApiError(404, "NOT_FOUND", "project not found")
        highest = (
            await session.execute(
                select(func.max(IcpVersion.number)).where(
                    IcpVersion.workspace_id == workspace_id, IcpVersion.project_id == project_id
                )
            )
        ).scalar()
        row = IcpVersion(
            workspace_id=workspace_id,
            project_id=project_id,
            number=(highest or 0) + 1,
            content=content,
            content_hash=canonical_hash(content),
        )
        session.add(row)
        await session.flush()
        data = _icp_data(row)
    return envelope(data, request.state.request_id)


@router.post("/icp-versions/{icp_version_id}/approve")
async def approve_icp_version(
    workspace_id: uuid.UUID,
    icp_version_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(get_principal),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    from datetime import datetime, timezone

    from sqlalchemy import select

    from ...db.icp import IcpVersion
    from ...services.icp_service import StaleRevision, verify_approval_hash
    from ..deps import load_membership, permission_for_roles, tenant_scoped

    if not idempotency_key:
        raise ApiError(400, "INVALID_REQUEST", "Idempotency-Key header is required")
    body = await request.json()
    if body.get("confirmation") is not True:
        raise ApiError(400, "INVALID_REQUEST", "confirmation must be true")
    expected_hash = body.get("content_hash", "")

    async with tenant_scoped(workspace_id) as session:
        membership = await load_membership(session, principal=principal, workspace_id=workspace_id)
        # approveICPVersion permits only reviewer/workspace_admin (contract x-permitted-roles).
        if not permission_for_roles(membership["roles"], "approveICPVersion"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        row = (
            await session.execute(
                select(IcpVersion)
                .where(IcpVersion.workspace_id == workspace_id, IcpVersion.id == icp_version_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if row is None:
            raise ApiError(404, "NOT_FOUND", "profile version not found")
        try:
            verify_approval_hash(row, expected_hash)
        except StaleRevision as exc:
            raise ApiError(412, "STALE_REVISION", str(exc)) from exc
        if row.approved_at is not None:
            return envelope(_icp_data(row), request.state.request_id)
        row.approved_at = datetime.now(timezone.utc)
        row.approved_by = membership["user_id"]
        data = _icp_data(row)
    return envelope(data, request.state.request_id)
```

Register all three routers in `create_app()` the same way as the health router.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_api_routes_contract.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add services/api/buyeros_api/services/icp_service.py services/api/buyeros_api/api/routes services/api/buyeros_api/api/app.py services/api/tests/test_api_routes_contract.py
git commit -m "feat(api): workspaces, projects and ICP routes"
```

---

### Task 6: Buyer read routes and the declared-path 501 registry

**Files:**
- Create: `services/api/buyeros_api/api/routes/buyers.py`
- Create: `services/api/buyeros_api/api/unimplemented.py`
- Modify: `services/api/buyeros_api/api/app.py`
- Create: `services/api/tests/test_api_buyers.py`

**Interfaces:**
- Produces: `GET /v1/workspaces/{workspace_id}/projects/{project_id}/buyers` (`listBuyers`), `GET /v1/workspaces/{workspace_id}/buyers/{buyer_id}` (`getBuyer`); `UNIMPLEMENTED_OPERATIONS: dict[str, tuple[str, str]]` mapping `operationId -> (method, path)`; `unimplemented_router` registering `501 NOT_IMPLEMENTED` handlers on those declared contract paths only.
- Consumes: `ProjectBuyer`/`Company`, `load_membership`, `permission_for_roles`, `tenant_scoped`, `get_principal`.

**Contract note (pre-flight correction #4):** the previously planned catch-all `/v1/unimplemented/{operation_id}` is deleted ??it invented a non-contract path, violating contract-first. Out-of-slice operations are now served `501` **only** on their declared contract path+method.

- [ ] **Step 1: Write the failing test**

```python
# services/api/tests/test_api_buyers.py
from fastapi.testclient import TestClient

from buyeros_api.api.app import create_app
from buyeros_api.api.unimplemented import UNIMPLEMENTED_OPERATIONS

WORKSPACE = "11111111-1111-4111-8111-111111111111"
PROJECT = "22222222-2222-4222-8222-222222222222"
RUN = "44444444-4444-4444-8444-444444444444"


def test_buyers_list_requires_auth():
    client = TestClient(create_app(), raise_server_exceptions=False)
    response = client.get(f"/v1/workspaces/{WORKSPACE}/projects/{PROJECT}/buyers")
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHENTICATED"


def test_unimplemented_registry_uses_declared_contract_paths():
    assert UNIMPLEMENTED_OPERATIONS["startRun"] == (
        "post",
        "/v1/workspaces/{workspace_id}/projects/{project_id}/runs",
    )
    for method, path in UNIMPLEMENTED_OPERATIONS.values():
        assert method in {"get", "post", "patch", "delete"}
        assert path.startswith("/v1/")


def test_unimplemented_paths_match_openapi_spec():
    import yaml
    from pathlib import Path

    spec = yaml.safe_load(Path("../../docs/buyeros/contracts/openapi.proposed.yaml").read_text(encoding="utf-8"))
    paths = spec["paths"]
    for operation_id, (method, path) in UNIMPLEMENTED_OPERATIONS.items():
        assert path in paths, (operation_id, path)
        assert method in paths[path], (operation_id, method)
        assert paths[path][method]["operationId"] == operation_id


def test_unimplemented_declared_path_fails_closed_then_501():
    client = TestClient(create_app(), raise_server_exceptions=False)
    # Unconfigured auth: fail closed before any 501 is reachable.
    response = client.post(f"/v1/workspaces/{WORKSPACE}/projects/{PROJECT}/runs", json={})
    assert response.status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_api_buyers.py -v`
Expected: FAIL ??404 / `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# services/api/buyeros_api/api/routes/buyers.py
import uuid

from fastapi import APIRouter, Depends, Request

from ..auth import Principal, get_principal
from ..errors import ApiError, envelope

router = APIRouter(prefix="/v1/workspaces/{workspace_id}", tags=["buyers"])


def _buyer_data(buyer, company) -> dict:
    return {"id": str(buyer.id), "project_id": str(buyer.project_id), "company": company.display_name, "note": buyer.note}


@router.get("/projects/{project_id}/buyers")
async def list_buyers(
    workspace_id: uuid.UUID, project_id: uuid.UUID, request: Request, principal: Principal = Depends(get_principal)
) -> dict:
    from sqlalchemy import select

    from ...db.buyers import Company, ProjectBuyer
    from ..deps import load_membership, permission_for_roles, tenant_scoped

    async with tenant_scoped(workspace_id) as session:
        membership = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(membership["roles"], "listBuyers"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        rows = (
            await session.execute(
                select(ProjectBuyer, Company)
                .join(
                    Company,
                    (Company.workspace_id == ProjectBuyer.workspace_id) & (Company.id == ProjectBuyer.company_id),
                )
                .where(ProjectBuyer.workspace_id == workspace_id, ProjectBuyer.project_id == project_id)
            )
        ).all()
        items = [_buyer_data(buyer, company) for buyer, company in rows]
    return envelope({"items": items, "offset": 0, "limit": len(items), "total": len(items)}, request.state.request_id)


@router.get("/buyers/{buyer_id}")
async def get_buyer(
    workspace_id: uuid.UUID, buyer_id: uuid.UUID, request: Request, principal: Principal = Depends(get_principal)
) -> dict:
    from sqlalchemy import select

    from ...db.buyers import Company, ProjectBuyer
    from ..deps import load_membership, permission_for_roles, tenant_scoped

    async with tenant_scoped(workspace_id) as session:
        membership = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(membership["roles"], "getBuyer"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        row = (
            await session.execute(
                select(ProjectBuyer, Company)
                .join(
                    Company,
                    (Company.workspace_id == ProjectBuyer.workspace_id) & (Company.id == ProjectBuyer.company_id),
                )
                .where(ProjectBuyer.workspace_id == workspace_id, ProjectBuyer.id == buyer_id)
            )
        ).one_or_none()
        if row is None:
            raise ApiError(404, "NOT_FOUND", "buyer not found")
        buyer, company = row
        data = _buyer_data(buyer, company)
    return envelope(data, request.state.request_id)
```

```python
# services/api/buyeros_api/api/unimplemented.py
"""Explicit 501 handlers for contract operations outside the P9 slice.

Handlers are registered on the operations' **declared** contract path+method, so
no parallel or invented endpoint exists. Each still requires a principal, so the
surface fails closed (401) when auth is unconfigured, then returns 501 once
authenticated.
"""

from fastapi import APIRouter, Depends, Request

from .auth import Principal, get_principal
from .errors import ApiError

UNIMPLEMENTED_OPERATIONS: dict[str, tuple[str, str]] = {
    "startRun": ("post", "/v1/workspaces/{workspace_id}/projects/{project_id}/runs"),
    "getRun": ("get", "/v1/workspaces/{workspace_id}/runs/{run_id}"),
    "getRunEvents": ("get", "/v1/workspaces/{workspace_id}/runs/{run_id}/events"),
    "cancelRun": ("post", "/v1/workspaces/{workspace_id}/runs/{run_id}/cancel"),
    "retryRun": ("post", "/v1/workspaces/{workspace_id}/runs/{run_id}/retry"),
    "quoteLookup": ("post", "/v1/workspaces/{workspace_id}/projects/{project_id}/enrichment-quotes"),
    "confirmLookup": ("post", "/v1/workspaces/{workspace_id}/enrichment-quotes/{quote_id}/confirm"),
    "getEnrichmentJob": ("get", "/v1/workspaces/{workspace_id}/enrichment-jobs/{job_id}"),
    "cancelEnrichmentJob": ("post", "/v1/workspaces/{workspace_id}/enrichment-jobs/{job_id}/cancel"),
    "generateDraft": ("post", "/v1/workspaces/{workspace_id}/projects/{project_id}/drafts"),
    "editDraft": ("patch", "/v1/workspaces/{workspace_id}/drafts/{draft_id}"),
    "requestDraftReview": ("post", "/v1/workspaces/{workspace_id}/drafts/{draft_id}/review"),
    "approveDraft": ("post", "/v1/workspaces/{workspace_id}/drafts/{draft_id}/approvals"),
    "exportBuyers": ("post", "/v1/workspaces/{workspace_id}/projects/{project_id}/exports"),
    "downloadExport": ("get", "/v1/workspaces/{workspace_id}/exports/{export_id}/content"),
    "exportDraft": ("post", "/v1/workspaces/{workspace_id}/drafts/{draft_id}/exports"),
    "recordOutcome": ("post", "/v1/workspaces/{workspace_id}/projects/{project_id}/outcomes"),
    "correctOutcome": ("post", "/v1/workspaces/{workspace_id}/outcomes/{outcome_id}/corrections"),
    "getUsage": ("get", "/v1/workspaces/{workspace_id}/projects/{project_id}/usage"),
    "listBudgets": ("get", "/v1/workspaces/{workspace_id}/budgets"),
    "uploadOfferDocument": ("post", "/v1/workspaces/{workspace_id}/projects/{project_id}/offer-documents"),
    "ingestOfferUrl": ("post", "/v1/workspaces/{workspace_id}/projects/{project_id}/offer-ingestions"),
}

router = APIRouter(tags=["unimplemented"])


def _register(operation_id: str, method: str, path: str) -> None:
    async def handler(request: Request, principal: Principal = Depends(get_principal)) -> dict:
        raise ApiError(501, "NOT_IMPLEMENTED", f"{operation_id} is not implemented in this phase")

    handler.__name__ = f"not_implemented_{operation_id}"
    router.add_api_route(path, handler, methods=[method.upper()], name=operation_id)


for _operation_id, (_method, _path) in UNIMPLEMENTED_OPERATIONS.items():
    _register(_operation_id, _method, _path)
```

Register `buyers_router` and `unimplemented_router` in `create_app()`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_api_buyers.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add services/api/buyeros_api/api/routes/buyers.py services/api/buyeros_api/api/unimplemented.py services/api/buyeros_api/api/app.py services/api/tests/test_api_buyers.py
git commit -m "feat(api): buyer read routes and declared-path 501 registry"
```

---

### Task 7: Pinned pnpm TS client generation and DB-backed isolation tests

**Files:**
- Create: `services/api/package.json`
- Create: `services/api/pnpm-lock.yaml` (generated by `pnpm install --ignore-workspace`)
- Create: `services/generated/buyeros-api.ts` (generated)
- Modify: `.gitignore` (ignore `services/api/node_modules/`)
- Create: `services/api/tests/test_api_tenant_isolation.py`

**Interfaces:**
- Produces: generated TS types from `contracts/openapi.proposed.yaml` via an exactly pinned `openapi-typescript`; DB-backed tests proving the routes cannot cross tenants.
- Consumes: `pg_dsn`/`migrated`/`seeded` fixtures and `runtime_role_dsn` (`services/api/tests/conftest.py`).

**Contract note (pre-flight correction #5):** generation uses the repo's pnpm toolchain, **not** an unpinned `npx` fetch. `openapi-typescript` is pinned exactly (`7.13.0`) as a devDependency in `services/api/package.json` with a `generate:client` script. Because the root `pnpm-workspace.yaml` does not list `services/api` as a package, install locally with `pnpm install --ignore-workspace`. Record the resolved version exactly.

- [ ] **Step 1: Write the failing test**

```python
# services/api/tests/test_api_tenant_isolation.py
import psycopg
from fastapi.testclient import TestClient

from buyeros_api.api.app import create_app
from tests.conftest import runtime_role_dsn

WORKSPACE_A = "11111111-1111-4111-8111-111111111111"
WORKSPACE_B = "22222222-2222-4222-8222-222222222222"


def test_tenant_routes_fail_closed_without_configured_auth():
    """With no Auth0 issuer/audience configured every tenant route is unreachable
    and no cross-tenant data can be enumerated."""
    client = TestClient(create_app(), raise_server_exceptions=False)
    for method, path in (
        ("GET", "/v1/workspaces"),
        ("GET", f"/v1/workspaces/{WORKSPACE_B}/projects"),
        ("GET", f"/v1/workspaces/{WORKSPACE_B}/readiness"),
    ):
        response = client.request(method, path)
        assert response.status_code == 401, (method, path)
        assert response.json()["code"] == "UNAUTHENTICATED"
        assert "ProjectB" not in response.text


def test_runtime_role_is_confined_to_one_tenant(seeded):
    """The NOBYPASSRLS runtime role only ever sees its own workspace's rows."""
    with psycopg.connect(runtime_role_dsn(seeded), autocommit=True) as conn:
        conn.execute("SELECT set_config('app.workspace_id', %s, false)", (WORKSPACE_A,))
        names = {row[0] for row in conn.execute("SELECT name FROM projects").fetchall()}
    assert names == {"ProjectA"}


def test_runtime_role_without_context_sees_nothing(seeded):
    with psycopg.connect(runtime_role_dsn(seeded), autocommit=True) as conn:
        conn.execute("SELECT set_config('app.workspace_id', %s, false)", (WORKSPACE_B,))
        names = {row[0] for row in conn.execute("SELECT name FROM projects").fetchall()}
    assert names == {"ProjectB"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_api_tenant_isolation.py -v`
Expected: FAIL ??route/mode not yet correct / `ModuleNotFoundError`.

- [ ] **Step 3: Pin the generator, install and generate the client**

```json
// services/api/package.json
{
  "name": "buyeros-api-tools",
  "private": true,
  "scripts": {
    "generate:client": "openapi-typescript ../../docs/buyeros/contracts/openapi.proposed.yaml -o ../generated/buyeros-api.ts"
  },
  "devDependencies": {
    "openapi-typescript": "7.13.0"
  }
}
```

Add `services/api/node_modules/` to the root `.gitignore`, then run (cwd `services/api`):

```bash
pnpm install --ignore-workspace
pnpm run generate:client
```

Expected: `services/api/pnpm-lock.yaml` and `services/generated/buyeros-api.ts` are written. Record the resolved tool version (`openapi-typescript 7.13.0`) and the command output in the task report. Do **not** commit `services/api/node_modules/`.

- [ ] **Step 4: Run the isolation test**

Run: `uv run pytest tests/test_api_tenant_isolation.py -v`
Expected: PASS (3 passed; DB cases skip cleanly when no disposable PostgreSQL is available). Once BO-004 supplies Auth0 config, extend this test with the local test keypair to assert a non-member gets `404` and a member of A cannot read B's rows.

- [ ] **Step 5: Commit**

```bash
git add .gitignore services/api/package.json services/api/pnpm-lock.yaml services/generated/buyeros-api.ts services/api/tests/test_api_tenant_isolation.py
git commit -m "feat(api): pinned pnpm-generated TS client and tenant isolation tests"
```

---

## Self-Review

- **Spec coverage:** A (Tasks 1, 4, 5, 6), B (Tasks 2, 3), C (Tasks 1, 5, 6, 7), D (Tasks 1, 4, 5, 6), E (Tasks 1?? tests) are mapped. Deliberate gaps to record before Build: full JWKS/RS256 verification inside `principal_from_token` (BO-004, needs B-IDENTITY); `If-Match` handling beyond ICP approval; `Idempotency-Key` persistence for other mutations; frontend wiring of `services/live/mapping.ts`.
- **Placeholder scan:** no `TBD`/`TODO`; each code step contains complete code. The declared-path `501` map is enumerated in Task 6 and the readiness/capabilities payloads in Task 4, so no summarised behaviour remains.
- **Type consistency:** `ApiError(status_code, code, message, retryable)`, `envelope(data, request_id)`, `Principal(issuer, subject)`, `claims_to_principal(claims, *, issuer, audience, now)`, `permission_for_roles(roles, permission)`, `get_engine()`, `tenant_scoped(workspace_id)`, `load_membership(session, *, principal, workspace_id)` are consistent across tasks and reuse existing `buyeros_api` names (`tenant_session`, `canonical_hash`, `Project`, `IcpVersion`, `ProjectBuyer`, `Company`). `verify_approval_hash`/`StaleRevision` are **created** in Task 5 (`services/icp_service.py`), not reused: the P2 plan specified that module but it was never implemented.

## Global Notes

- No remote commits/pushes (beyond pushing this plan's branch), no deploys, cloud resources, real-data migrations, provider calls, or sends.
- Every command is **NOT RUN** until executed under explicit approval; record exact output in `PROGRESS.md`.
- Execution requires a recorded dependency waiver (BO-004 incomplete) and may use `superpowers:subagent-driven-development` or `superpowers:executing-plans`.
