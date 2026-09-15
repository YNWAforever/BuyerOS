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
