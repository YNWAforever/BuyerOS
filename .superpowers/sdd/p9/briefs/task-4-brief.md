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
