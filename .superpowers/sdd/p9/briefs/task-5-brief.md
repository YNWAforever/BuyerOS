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
