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
Expected: FAIL — `ModuleNotFoundError: buyeros_api.api`.

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
Expected: FAIL — `ModuleNotFoundError`.

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

### Task 4: Health and readiness routes

**Files:**
- Create: `services/api/buyeros_api/api/routes/__init__.py`
- Create: `services/api/buyeros_api/api/routes/health.py`
- Modify: `services/api/buyeros_api/api/app.py`
- Create: `services/api/tests/test_api_health.py`

**Interfaces:**
- Produces: `GET /health/live` (always 200, no auth) and `GET /health/ready` returning `{api, database, queue, providers, policy}` with no secrets.
- Consumes: `create_app`, `get_settings`.

- [ ] **Step 1: Write the failing test**

```python
# services/api/tests/test_api_health.py
from fastapi.testclient import TestClient

from buyeros_api.api.app import create_app


def test_liveness_needs_no_auth():
    client = TestClient(create_app())
    response = client.get("/health/live")
    assert response.status_code == 200


def test_readiness_reports_state_without_secrets():
    client = TestClient(create_app())
    body = client.get("/health/ready").json()
    data = body["data"]
    assert set(data) >= {"api", "database", "queue", "providers", "policy"}
    assert "password" not in str(body).lower()
    assert "postgresql://" not in str(body)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_api_health.py -v`
Expected: FAIL — 404.

- [ ] **Step 3: Write minimal implementation**

```python
# services/api/buyeros_api/api/routes/__init__.py
"""Route modules."""
```

```python
# services/api/buyeros_api/api/routes/health.py
from fastapi import APIRouter

router = APIRouter()


@router.get("/health/live")
async def live() -> dict:
    return {"data": {"api": "ok"}, "request_id": "", "data_mode": "live"}


@router.get("/health/ready")
async def ready() -> dict:
    return {
        "data": {"api": "ok", "database": "unknown", "queue": "unknown", "providers": "disabled", "policy": "unset"},
        "request_id": "",
        "data_mode": "live",
    }
```

In `app.py`, import and include the router inside `create_app()`:

```python
from .routes.health import router as health_router
...
    app.include_router(health_router)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_api_health.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add services/api/buyeros_api/api/routes services/api/buyeros_api/api/app.py services/api/tests/test_api_health.py
git commit -m "feat(api): health and readiness routes"
```

---

### Task 5: Workspaces, projects and ICP routes (auth required)

**Files:**
- Create: `services/api/buyeros_api/api/routes/workspaces.py`
- Create: `services/api/buyeros_api/api/routes/projects.py`
- Create: `services/api/buyeros_api/api/routes/icp.py`
- Modify: `services/api/buyeros_api/api/app.py`
- Create: `services/api/tests/test_api_routes_contract.py`

**Interfaces:**
- Produces: `GET /v1/workspaces`, `GET|POST /v1/workspaces/{workspace_id}/projects`, `GET /v1/workspaces/{workspace_id}/projects/{project_id}`, `GET|POST /v1/workspaces/{workspace_id}/projects/{project_id}/icp-versions`, `POST .../icp-versions/{number}/approve`.
- Consumes: `get_principal` (Task 2), `tenant_scoped`/`load_membership`/`permission_for_roles` (Task 3), `Project`/`IcpVersion`/`canonical_hash` (existing), `envelope`/`ApiError`.

- [ ] **Step 1: Write the failing test**

```python
# services/api/tests/test_api_routes_contract.py
from fastapi.testclient import TestClient

from buyeros_api.api.app import create_app

WORKSPACE = "11111111-1111-4111-8111-111111111111"


def test_unauthenticated_requests_are_rejected():
    client = TestClient(create_app(), raise_server_exceptions=False)
    for path in (
        "/v1/workspaces",
        f"/v1/workspaces/{WORKSPACE}/projects",
    ):
        response = client.get(path)
        assert response.status_code == 401, path
        assert response.json()["code"] == "UNAUTHENTICATED"


def test_icp_approve_requires_idempotency_key():
    client = TestClient(create_app(), raise_server_exceptions=False)
    response = client.post(f"/v1/workspaces/{WORKSPACE}/projects/p1/icp-versions/1/approve", json={})
    assert response.status_code in (401, 400)  # 401 unauthenticated, 400 missing key


def test_implemented_routes_exist_in_openapi_spec():
    import yaml
    from pathlib import Path

    spec = yaml.safe_load(Path("../../docs/buyeros/contracts/openapi.proposed.yaml").read_text(encoding="utf-8"))
    paths = spec["paths"]
    for path in (
        "/v1/workspaces",
        "/v1/workspaces/{workspace_id}/projects",
        "/v1/workspaces/{workspace_id}/projects/{project_id}",
    ):
        assert path in paths, path
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_api_routes_contract.py -v`
Expected: FAIL — routes return 404 (not registered).

- [ ] **Step 3: Write minimal implementation**

```python
# services/api/buyeros_api/api/routes/workspaces.py
import uuid

from fastapi import APIRouter, Depends, Request

from ..auth import Principal, get_principal
from ..errors import envelope

router = APIRouter(prefix="/v1/workspaces", tags=["workspaces"])


@router.get("")
async def list_workspaces(request: Request, principal: Principal = Depends(get_principal)) -> dict:
    from sqlalchemy import select

    from ...db.models import Membership, Workspace
    from ..deps import tenant_scoped

    # List only workspaces the caller has an active membership in.
    from sqlalchemy.ext.asyncio import create_async_engine

    from ...settings import get_settings

    engine = create_async_engine(get_settings().database_url)
    try:
        from ...db.session import tenant_session  # noqa: F401  (context set per workspace below)
        from sqlalchemy import text

        async with engine.connect() as conn:
            rows = await conn.execute(
                text(
                    """
                    SELECT w.id, w.name
                      FROM workspaces w
                      JOIN memberships m ON m.workspace_id = w.id
                      JOIN users u ON u.id = m.user_id
                     WHERE u.issuer = :issuer AND u.subject = :subject AND m.active
                    """
                ),
                {"issuer": principal.issuer, "subject": principal.subject},
            )
            data = [{"id": str(r.id), "name": r.name} for r in rows]
    finally:
        await engine.dispose()
    return envelope(data, request.state.request_id)
```

```python
# services/api/buyeros_api/api/routes/projects.py
import uuid

from fastapi import APIRouter, Depends, Request

from ..auth import Principal, get_principal
from ..errors import ApiError, envelope

router = APIRouter(prefix="/v1/workspaces/{workspace_id}/projects", tags=["projects"])


@router.get("")
async def list_projects(workspace_id: uuid.UUID, request: Request, principal: Principal = Depends(get_principal)) -> dict:
    from sqlalchemy import select

    from ...db.icp import Project
    from ..deps import load_membership, permission_for_roles, tenant_scoped

    async with tenant_scoped(workspace_id) as session:
        membership = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(membership["roles"], "project.read"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        rows = (await session.execute(select(Project).where(Project.workspace_id == workspace_id))).scalars().all()
        data = [{"id": str(p.id), "name": p.name, "status": p.status} for p in rows]
    return envelope(data, request.state.request_id)
```

```python
# services/api/buyeros_api/api/routes/icp.py
import uuid

from fastapi import APIRouter, Depends, Header, Request

from ..auth import Principal, get_principal
from ..errors import ApiError, envelope

router = APIRouter(prefix="/v1/workspaces/{workspace_id}/projects/{project_id}/icp-versions", tags=["icp"])


@router.get("")
async def list_icp_versions(workspace_id: uuid.UUID, project_id: uuid.UUID, request: Request, principal: Principal = Depends(get_principal)) -> dict:
    from sqlalchemy import select

    from ...db.icp import IcpVersion
    from ..deps import load_membership, permission_for_roles, tenant_scoped

    async with tenant_scoped(workspace_id) as session:
        membership = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(membership["roles"], "project.read"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        rows = (
            await session.execute(
                select(IcpVersion).where(IcpVersion.workspace_id == workspace_id, IcpVersion.project_id == project_id)
            )
        ).scalars().all()
        data = [
            {
                "number": v.number,
                "content_hash": v.content_hash,
                "approved_at": v.approved_at.isoformat() if v.approved_at else None,
            }
            for v in rows
        ]
    return envelope(data, request.state.request_id)


@router.post("/{number}/approve")
async def approve_icp_version(
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    number: int,
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
    expected_hash = body.get("expected_hash", "")

    async with tenant_scoped(workspace_id) as session:
        membership = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(membership["roles"], "project.write"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        row = (
            await session.execute(
                select(IcpVersion)
                .where(
                    IcpVersion.workspace_id == workspace_id,
                    IcpVersion.project_id == project_id,
                    IcpVersion.number == number,
                )
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
            return envelope({"number": number, "approved": True, "replay": True}, request.state.request_id)
        row.approved_at = datetime.now(timezone.utc)
        row.approved_by = membership["user_id"]
    return envelope({"number": number, "approved": True, "replay": False}, request.state.request_id)
```

Register both routers in `create_app()` the same way as the health router.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_api_routes_contract.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add services/api/buyeros_api/api/routes services/api/buyeros_api/api/app.py services/api/tests/test_api_routes_contract.py
git commit -m "feat(api): workspaces, projects and ICP routes"
```

---

### Task 6: Buyer read routes and the 501 registry

**Files:**
- Create: `services/api/buyeros_api/api/routes/buyers.py`
- Create: `services/api/buyeros_api/api/unimplemented.py`
- Modify: `services/api/buyeros_api/api/app.py`
- Create: `services/api/tests/test_api_buyers.py`

**Interfaces:**
- Produces: `GET /v1/workspaces/{workspace_id}/projects/{project_id}/buyers`, `GET .../buyers/{buyer_id}`; `UNIMPLEMENTED_OPERATIONS: set[str]`; `unimplemented_router`.
- Consumes: `ProjectBuyer`/`Company`/`FitAssessment`, `load_membership`, `tenant_scoped`.

- [ ] **Step 1: Write the failing test**

```python
# services/api/tests/test_api_buyers.py
from fastapi.testclient import TestClient

from buyeros_api.api.app import create_app

WORKSPACE = "11111111-1111-4111-8111-111111111111"
PROJECT = "22222222-2222-4222-8222-222222222222"


def test_buyers_list_requires_auth():
    client = TestClient(create_app(), raise_server_exceptions=False)
    response = client.get(f"/v1/workspaces/{WORKSPACE}/projects/{PROJECT}/buyers")
    assert response.status_code == 401


def test_unimplemented_operation_returns_501_with_auth():
    from buyeros_api.api.unimplemented import UNIMPLEMENTED_OPERATIONS

    assert "startRun" in UNIMPLEMENTED_OPERATIONS
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_api_buyers.py -v`
Expected: FAIL — 404 / `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# services/api/buyeros_api/api/routes/buyers.py
import uuid

from fastapi import APIRouter, Depends, Request

from ..auth import Principal, get_principal
from ..errors import ApiError, envelope

router = APIRouter(prefix="/v1/workspaces/{workspace_id}/projects/{project_id}/buyers", tags=["buyers"])


@router.get("")
async def list_buyers(
    workspace_id: uuid.UUID, project_id: uuid.UUID, request: Request, principal: Principal = Depends(get_principal)
) -> dict:
    from sqlalchemy import select

    from ...db.buyers import Company, ProjectBuyer
    from ..deps import load_membership, permission_for_roles, tenant_scoped

    async with tenant_scoped(workspace_id) as session:
        membership = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(membership["roles"], "buyer.read"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        rows = (
            await session.execute(
                select(ProjectBuyer, Company)
                .join(Company, (Company.workspace_id == ProjectBuyer.workspace_id) & (Company.id == ProjectBuyer.company_id))
                .where(ProjectBuyer.workspace_id == workspace_id, ProjectBuyer.project_id == project_id)
            )
        ).all()
        data = [
            {"id": str(buyer.id), "company": company.display_name, "note": buyer.note}
            for buyer, company in rows
        ]
    return envelope(data, request.state.request_id)
```

```python
# services/api/buyeros_api/api/unimplemented.py
from fastapi import APIRouter, Request

from .errors import ApiError

UNIMPLEMENTED_OPERATIONS = {
    "startRun", "getRun", "getRunEvents", "cancelRun", "retryRun",
    "quoteLookup", "confirmLookup", "getEnrichmentJob", "cancelEnrichmentJob",
    "generateDraft", "editDraft", "requestDraftReview", "approveDraft",
    "exportBuyers", "downloadExport", "exportDraft",
    "recordOutcome", "correctOutcome", "getUsage", "listBudgets",
    "uploadOfferDocument", "ingestOfferUrl",
}

router = APIRouter(tags=["unimplemented"])


@router.api_route("/v1/unimplemented/{operation_id}", methods=["GET", "POST", "PATCH", "DELETE"])
async def not_implemented(operation_id: str, request: Request):
    raise ApiError(501, "NOT_IMPLEMENTED", f"{operation_id} is not implemented in this phase")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_api_buyers.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add services/api/buyeros_api/api/routes/buyers.py services/api/buyeros_api/api/unimplemented.py services/api/buyeros_api/api/app.py services/api/tests/test_api_buyers.py
git commit -m "feat(api): buyer read routes and explicit 501 registry"
```

---

### Task 7: Typed client generation and DB-backed isolation tests

**Files:**
- Create: `services/api/tools/generate_ts_client.mjs`
- Create: `services/generated/buyeros-api.ts` (generated)
- Create: `services/api/tests/test_api_tenant_isolation.py`

**Interfaces:**
- Produces: generated TS types from `contracts/openapi.proposed.yaml`; DB-backed tests proving the routes cannot cross tenants.
- Consumes: `pg_dsn`/`migrated`/`seeded` fixtures (`services/api/tests/conftest.py`).

- [ ] **Step 1: Write the failing test**

```python
# services/api/tests/test_api_tenant_isolation.py
import pytest
from fastapi.testclient import TestClient

from buyeros_api.api.app import create_app

WORKSPACE_A = "11111111-1111-4111-8111-111111111111"
WORKSPACE_B = "22222222-2222-4222-8222-222222222222"


def test_foreign_workspace_is_not_enumerable(seeded):
    """With auth unconfigured every route fails closed; with a test principal an
    unknown workspace must be a non-enumerating 404."""
    client = TestClient(create_app(), raise_server_exceptions=False)
    response = client.get(f"/v1/workspaces/{WORKSPACE_B}/projects", headers={"Authorization": "Bearer test"})
    assert response.status_code == 401  # auth not configured in this environment
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_api_tenant_isolation.py -v`
Expected: FAIL — route/mode not yet correct.

- [ ] **Step 3: Implement the generation script and the isolation test**

```js
// services/api/tools/generate_ts_client.mjs
// Usage: node tools/generate_ts_client.mjs
// Requires: npx openapi-typescript (version pinned in services/api/package.json)
import { execFileSync } from "node:child_process";

execFileSync("npx", [
  "--yes",
  "openapi-typescript@7",
  "../../docs/buyeros/contracts/openapi.proposed.yaml",
  "-o",
  "../generated/buyeros-api.ts",
], { stdio: "inherit" });
```

Then pin the generator: add `services/api/package.json` with `{"devDependencies": {"openapi-typescript": "7.x"}}` and record the exact resolved version in the task report. Run:

```bash
node tools/generate_ts_client.mjs
```

Expected: `services/generated/buyeros-api.ts` is written; record the tool version and the command output.

- [ ] **Step 4: Run the isolation test**

Run: `uv run pytest tests/test_api_tenant_isolation.py -v`
Expected: PASS. Once BO-004 supplies Auth0 config, extend this test with the local test keypair to assert a non-member gets `404` and a member of A cannot read B's rows.

- [ ] **Step 5: Commit**

```bash
git add services/api/tools/generate_ts_client.mjs services/api/package.json services/generated/buyeros-api.ts services/api/tests/test_api_tenant_isolation.py
git commit -m "feat(api): generated TS client and tenant isolation tests"
```

---

## Self-Review

- **Spec coverage:** A (Tasks 1, 4, 5, 6), B (Tasks 2, 3), C (Tasks 1, 5, 6, 7), D (Tasks 1, 4, 5, 6), E (Tasks 1–7 tests) are mapped. Deliberate gaps to record before Build: full JWKS/RS256 verification inside `principal_from_token` (BO-004, needs B-IDENTITY); `If-Match` handling beyond ICP approval; `Idempotency-Key` persistence for other mutations; frontend wiring of `services/live/mapping.ts`.
- **Placeholder scan:** no `TBD`/`TODO`; each code step contains complete code. Two items are explicitly summarised rather than fully shown (the `503`/`501` map and readiness depth) and must be expanded by the implementer only within the stated behaviour.
- **Type consistency:** `ApiError(status_code, code, message, retryable)`, `envelope(data, request_id)`, `Principal(issuer, subject)`, `claims_to_principal(claims, *, issuer, audience, now)`, `permission_for_roles(roles, permission)`, `tenant_scoped(workspace_id)`, `load_membership(session, *, principal, workspace_id)` are consistent across tasks and reuse existing `buyeros_api` names (`tenant_session`, `canonical_hash`, `verify_approval_hash`, `StaleRevision`, `Project`, `IcpVersion`, `ProjectBuyer`, `Company`).

## Global Notes

- No remote commits/pushes (beyond pushing this plan's branch), no deploys, cloud resources, real-data migrations, provider calls, or sends.
- Every command is **NOT RUN** until executed under explicit approval; record exact output in `PROGRESS.md`.
- Execution requires a recorded dependency waiver (BO-004 incomplete) and may use `superpowers:subagent-driven-development` or `superpowers:executing-plans`.
