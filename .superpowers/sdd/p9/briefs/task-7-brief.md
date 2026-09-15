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
