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
