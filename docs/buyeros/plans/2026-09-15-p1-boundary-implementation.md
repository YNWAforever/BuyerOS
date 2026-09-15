# P1 Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **Build is NOT authorized by this document** — execution requires explicit selected-task approval; the repo-commit steps are future Build actions.

**Goal:** Establish the authenticated, tenant-isolated API boundary and the demo/live separation so every later slice can persist and gate data safely.

**Architecture:** A single FastAPI domain service validates Auth0 PKCE bearer tokens (RS256), resolves Postgres membership per request, and runs every query inside a transaction with a transaction-local tenant context against RLS-protected tables with composite tenant foreign keys. The preserved Vinext frontend switches between an isolated demo adapter and the live API by execution-profile configuration.

**Tech Stack:** Python 3.12 + FastAPI + Pydantic v2 + SQLAlchemy 2 + Alembic + asyncpg/psycopg, PostgreSQL 16, `uv` for packaging; existing Vinext/React/TypeScript + pnpm for the frontend.

## Global Constraints

- Canonical repository: `YNWAforever/BuyerOS` (planning pack committed at `1512d4c17d4f792e14598d524fdac3c9c37d27e7`; a source import of content baseline `b804ba8d1514a1049b7202c861278dd72c473a75` is still expected, tree `b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1`).
- Plan-only artifact. No commits, pushes, installs, migrations, provisioning, paid calls, mailbox connections, or Site changes are authorized by this plan.
- Preserve the existing frontend runtime (Vinext 1.0.0-beta.5, React 19.2.6, TS 5.9.3, Tailwind 4.2.1) and pnpm 11.25.0; never migrate to standard Next.js/Vercel.
- Money is `NUMERIC(20,6)` / `Decimal`; wire amounts are decimal strings. Tenant tables use `workspace_id NOT NULL`, `UNIQUE(workspace_id,id)`, `(workspace_id,parent_id)` FKs, RLS with `SET LOCAL`, and non-owner runtime roles (no `BYPASSRLS`).
- Auth uses Auth0 issuer/audience from configuration; **no invented values** — live auth stays disabled until supplied.
- Live responses: `{data, request_id, data_mode:"live"}`. Demo fixtures never deserialize into live responses.
- Exact command results must be recorded; every unexecuted check is marked **NOT RUN**.

**File ownership (PROPOSED):** `services/api/buyeros_api/` (domain service), `services/api/alembic/` (sole migration owner), `services/generated/` (OpenAPI TS DTOs), `services/live/` (browser live adapter), `tests/contracts/` (contract tests). Existing `services/contracts.ts`, `services/http-client.ts`, and features remain the browser boundary.

---

### Task 1: Bootstrap the Python domain service

**Files:**
- Create: `services/api/pyproject.toml`
- Create: `services/api/buyeros_api/__init__.py`
- Create: `services/api/buyeros_api/settings.py`
- Create: `services/api/tests/test_settings.py`
- Create: `services/api/uv.lock` (generated)

**Interfaces:**
- Produces: `Settings` (pydantic-settings) with `database_url: str`, `database_migration_url: str`, `auth0_issuer: str | None`, `auth0_audience: str | None`, `jwks_cache_seconds: int`, `environment: str`. `get_settings() -> Settings` (cached).

- [ ] **Step 1: Write the failing test**

```python
# services/api/tests/test_settings.py
from buyeros_api.settings import Settings


def test_settings_defaults_are_fail_closed():
    s = Settings(database_url="postgresql://u:p@localhost/db")
    assert s.auth0_issuer is None
    assert s.auth0_audience is None
    assert s.jwks_cache_seconds == 300


def test_settings_rejects_sqlite():
    import pytest

    with pytest.raises(ValueError):
        Settings(database_url="sqlite:///dev.db")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_settings.py -v` (cwd `services/api`)
Expected: FAIL — `ModuleNotFoundError: buyeros_api`.

- [ ] **Step 3: Write minimal implementation**

```toml
# services/api/pyproject.toml
[project]
name = "buyeros-api"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.115,<1",
  "pydantic>=2.9,<3",
  "pydantic-settings>=2.5,<3",
  "sqlalchemy[asyncio]>=2.0,<2.1",
  "alembic>=1.13,<2",
  "asyncpg>=0.29,<1",
  "pyjwt[crypto]>=2.9,<3",
  "httpx>=0.27,<1",
]

[dependency-groups]
dev = ["pytest>=8.3,<9", "pytest-asyncio>=0.24,<1"]
```

```python
# services/api/buyeros_api/settings.py
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    database_migration_url: str | None = None
    auth0_issuer: str | None = None
    auth0_audience: str | None = None
    jwks_cache_seconds: int = 300
    environment: str = "local"

    @field_validator("database_url")
    @classmethod
    def _postgres_only(cls, v: str) -> str:
        if not v.startswith("postgresql"):
            raise ValueError("DATABASE_URL must be PostgreSQL")
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_settings.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Record result (no commit — Build authorization required)**

Run: `uv run python -m pytest -q`
Expected: PASS. Append output to the progress record. Do **not** commit until a selected task is approved for Build.

---

### Task 2: SQLAlchemy base, tenant mixin, and first domain tables

**Files:**
- Create: `services/api/buyeros_api/db/__init__.py`
- Create: `services/api/buyeros_api/db/base.py`
- Create: `services/api/buyeros_api/db/models.py`
- Create: `services/api/tests/test_models_constraints.py`
- Create: `services/api/alembic.ini`, `services/api/alembic/env.py`, `services/api/alembic/versions/0001_initial.py`

**Interfaces:**
- Produces: `Base`, `Workspace`, `User`, `Membership`; `TenantMixin` exposing `workspace_id: UUID` plus `UniqueConstraint("workspace_id","id")`.
- Consumes: `Settings.database_url` from Task 1.

- [ ] **Step 1: Write the failing test** (composite-key metadata assertions, no DB required)

```python
# services/api/tests/test_models_constraints.py
from buyeros_api.db.models import Membership


def test_membership_has_composite_unique_and_tenant_fk():
    table = Membership.__table__
    uniques = {tuple(sorted(c.name for c in uc.columns)) for uc in table.constraints if uc.__class__.__name__ == "UniqueConstraint"}
    assert ("id", "workspace_id") in uniques
    fks = {fk.parent.name: fk.target_fullname for fk in table.foreign_keys}
    assert fks["workspace_id"].startswith("workspaces.")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_models_constraints.py -v`
Expected: FAIL — `ModuleNotFoundError`/`ImportError` for `buyeros_api.db.models`.

- [ ] **Step 3: Write minimal implementation**

```python
# services/api/buyeros_api/db/base.py
import uuid
from datetime import datetime

from sqlalchemy import DateTime, MetaData, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING = {"pk": "pk_%(table_name)s", "uq": "uq_%(table_name)s_%(column_0_N_name)s", "fk": "fk_%(table_name)s_%(column_0_name)s"}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)


class UUIDPk:
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class Timestamped:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class TenantMixin(UUIDPk, Timestamped):
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    def __table_args__(self):  # noqa: D105
        return (UniqueConstraint("workspace_id", "id"),)
```

```python
# services/api/buyeros_api/db/models.py
import uuid

from sqlalchemy import ForeignKeyConstraint, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TenantMixin, UUIDPk


class Workspace(Base, UUIDPk):
    __tablename__ = "workspaces"
    name: Mapped[str] = mapped_column(String(200))
    data_mode: Mapped[str] = mapped_column(String(16), server_default=text("'live'"))


class User(Base, UUIDPk):
    __tablename__ = "users"
    issuer: Mapped[str] = mapped_column(String(255))
    subject: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    __table_args__ = (UniqueConstraint("issuer", "subject"),)


class Membership(Base, TenantMixin):
    __tablename__ = "memberships"
    user_id: Mapped[uuid.UUID] = mapped_column()
    roles: Mapped[list[str]] = mapped_column(ARRAY(String(32)))
    active: Mapped[bool] = mapped_column(server_default=text("true"))
    __table_args__ = (
        UniqueConstraint("workspace_id", "id"),
        UniqueConstraint("workspace_id", "user_id"),
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_models_constraints.py -v`
Expected: PASS.

- [ ] **Step 5: Generate and review the first migration**

Run: `uv run alembic revision --autogenerate -m "initial tenant boundary"`
Expected: a revision under `alembic/versions/`; **review the generated SQL by hand** before any apply. Applying migrations is a separate approved action and is **NOT RUN** in this plan.

---

### Task 3: Postgres roles and RLS policies

**Files:**
- Create: `services/api/alembic/versions/0002_rls_and_roles.py`
- Create: `services/api/tests/test_rls_sql_contains.py`

**Interfaces:**
- Produces: SQL that creates roles `buyeros_migrator`, `buyeros_api`, `buyeros_worker`; enables `ROW LEVEL SECURITY` and `FORCE ROW LEVEL SECURITY` with policy `tenant_isolation USING (workspace_id = current_setting('app.workspace_id')::uuid)`.

- [ ] **Step 1: Write the failing test**

```python
# services/api/tests/test_rls_sql_contains.py
from pathlib import Path


def test_rls_migration_mentions_force_and_context():
    src = Path("alembic/versions/0002_rls_and_roles.py").read_text()
    assert "FORCE ROW LEVEL SECURITY" in src
    assert "current_setting('app.workspace_id')" in src
    assert "NOBYPASSRLS" in src
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_rls_sql_contains.py -v`
Expected: FAIL — file not found.

- [ ] **Step 3: Write the migration**

```python
# services/api/alembic/versions/0002_rls_and_roles.py  (excerpt)
"""rls and roles"""

revision = "0002_rls_and_roles"
down_revision = "0001_initial"


def upgrade() -> None:
    op.execute("CREATE ROLE buyeros_api NOBYPASSRLS;")
    op.execute("CREATE ROLE buyeros_worker NOBYPASSRLS;")
    for table in ("memberships",):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            "USING (workspace_id = current_setting('app.workspace_id')::uuid) "
            "WITH CHECK (workspace_id = current_setting('app.workspace_id')::uuid);"
        )
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO buyeros_api, buyeros_worker;")


def downgrade() -> None:
    for table in ("memberships",):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table};")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_rls_sql_contains.py -v`
Expected: PASS. Applying this migration is **NOT RUN** (unapproved).

---

### Task 4: Transaction-local tenant context

**Files:**
- Create: `services/api/buyeros_api/db/session.py`
- Create: `services/api/tests/test_tenant_context.py`

**Interfaces:**
- Produces: `async def tenant_session(engine, workspace_id: uuid.UUID)` async context manager issuing `SET LOCAL app.workspace_id = :id` then yielding an `AsyncSession`. Missing/invalid context raises before any query.
- Consumes: `Settings.database_url` (Task 1), models (Task 2).

- [ ] **Step 1: Write the failing test**

```python
# services/api/tests/test_tenant_context.py
import uuid

import pytest

from buyeros_api.db.session import tenant_session


def test_tenant_session_rejects_none(engine=None):
    with pytest.raises(ValueError):
        # constructing the context with no workspace id must fail closed
        import asyncio

        asyncio.run(_use(None))


async def _use(ws):
    async with tenant_session(None, ws):
        pass
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_tenant_context.py -v`
Expected: FAIL — `ImportError` for `buyeros_api.db.session`.

- [ ] **Step 3: Write minimal implementation**

```python
# services/api/buyeros_api/db/session.py
import contextlib
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker


@contextlib.asynccontextmanager
async def tenant_session(engine: AsyncEngine, workspace_id: uuid.UUID):
    if engine is None or workspace_id is None:
        raise ValueError("tenant context requires an engine and workspace_id")
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        async with session.begin():
            await session.execute(text("SET LOCAL app.workspace_id = :ws"), {"ws": str(workspace_id)})
            yield session
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_tenant_context.py -v`
Expected: PASS.

---

### Task 5: Auth0 bearer verification (JWKS, RS256)

**Files:**
- Create: `services/api/buyeros_api/auth/jwks.py`
- Create: `services/api/buyeros_api/auth/verify.py`
- Create: `services/api/tests/test_verify_token.py`

**Interfaces:**
- Produces: `class TokenError(Exception)`; `async def verify_token(token: str, settings: Settings, jwks: JwksClient) -> Principal` where `Principal(issuer, subject)`. Rejects `alg != RS256`, wrong `iss`/`aud`, expired tokens.

- [ ] **Step 1: Write the failing test**

```python
# services/api/tests/test_verify_token.py
import pytest

from buyeros_api.auth.verify import TokenError, _claims_ok


def test_claims_reject_wrong_audience():
    with pytest.raises(TokenError):
        _claims_ok(
            {"iss": "https://t.example/", "aud": "other", "exp": 9999999999},
            issuer="https://t.example/",
            audience="buyeros-api",
        )


def test_claims_reject_expired():
    with pytest.raises(TokenError):
        _claims_ok({"iss": "https://t.example/", "aud": "buyeros-api", "exp": 1}, issuer="https://t.example/", audience="buyeros-api")


def test_claims_accept_valid():
    p = _claims_ok({"iss": "https://t.example/", "aud": "buyeros-api", "exp": 9999999999, "sub": "auth0|1"}, issuer="https://t.example/", audience="buyeros-api")
    assert p.subject == "auth0|1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_verify_token.py -v`
Expected: FAIL — `ImportError`.

- [ ] **Step 3: Write minimal implementation**

```python
# services/api/buyeros_api/auth/verify.py
import time
from dataclasses import dataclass


class TokenError(Exception):
    pass


@dataclass(frozen=True)
class Principal:
    issuer: str
    subject: str


def _claims_ok(claims: dict, *, issuer: str, audience: str, now: int | None = None) -> Principal:
    now = now or int(time.time())
    if claims.get("iss") != issuer:
        raise TokenError("bad issuer")
    aud = claims.get("aud")
    if isinstance(aud, list):
        if audience not in aud:
            raise TokenError("bad audience")
    elif aud != audience:
        raise TokenError("bad audience")
    if int(claims.get("exp", 0)) <= now:
        raise TokenError("expired")
    if not claims.get("sub"):
        raise TokenError("missing subject")
    return Principal(issuer=issuer, subject=str(claims["sub"]))
```

```python
# services/api/buyeros_api/auth/jwks.py
import time

import httpx
import jwt


class JwksClient:
    def __init__(self, jwks_uri: str, ttl_seconds: int = 300):
        self._uri = jwks_uri
        self._ttl = ttl_seconds
        self._fetched_at = 0.0
        self._keys: list[dict] = []

    async def _refresh(self) -> None:
        async with httpx.AsyncClient(timeout=10) as c:
            self._keys = (await c.get(self._uri)).json()["keys"]
            self._fetched_at = time.time()

    async def decode(self, token: str, issuer: str, audience: str) -> dict:
        if not self._keys or time.time() - self._fetched_at > self._ttl:
            await self._refresh()
        header = jwt.get_unverified_header(token)
        if header.get("alg") != "RS256":
            raise ValueError("unsupported algorithm")
        key = next(k for k in self._keys if k["kid"] == header["kid"])
        return jwt.decode(token, key=jwt.PyJWK(key).key, algorithms=["RS256"], issuer=issuer, audience=audience)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_verify_token.py -v`
Expected: PASS (3 passed).

---

### Task 6: Membership + RBAC dependency and readiness endpoint

**Files:**
- Create: `services/api/buyeros_api/auth/permissions.py`
- Create: `services/api/buyeros_api/api/deps.py`
- Create: `services/api/buyeros_api/api/routes/health.py`
- Create: `services/api/tests/test_permissions.py`

**Interfaces:**
- Produces: `ROLE_PERMISSIONS: dict[str, frozenset[str]]`; `def is_allowed(roles: list[str], permission: str) -> bool`; FastAPI dependency `require(permission: str)`; `GET /health/ready` returning capability flags without secrets.
- Consumes: `Principal` (Task 5), `tenant_session` (Task 4), `Membership` (Task 2).

- [ ] **Step 1: Write the failing test**

```python
# services/api/tests/test_permissions.py
from buyeros_api.auth.permissions import is_allowed


def test_viewer_cannot_review():
    assert not is_allowed(["viewer"], "buyer.review")


def test_reviewer_can_review_but_not_budget():
    assert is_allowed(["reviewer"], "buyer.review")
    assert not is_allowed(["reviewer"], "budget.write")


def test_admin_can_budget():
    assert is_allowed(["admin"], "budget.write")


def test_unknown_role_denied():
    assert not is_allowed(["ghost"], "project.read")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_permissions.py -v`
Expected: FAIL — `ImportError`.

- [ ] **Step 3: Write minimal implementation**

```python
# services/api/buyeros_api/auth/permissions.py
ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "viewer": frozenset({"project.read", "buyer.read", "evidence.read", "usage.read"}),
    "operator": frozenset({"project.read", "buyer.read", "evidence.read", "usage.read", "run.write", "buyer.note", "outcome.write", "quote.request"}),
    "reviewer": frozenset({"project.read", "buyer.read", "evidence.read", "usage.read", "run.write", "buyer.note", "outcome.write", "quote.request", "buyer.review", "draft.approve", "quote.confirm"}),
    "admin": frozenset({"*"}),
}


def is_allowed(roles: list[str], permission: str) -> bool:
    for role in roles:
        granted = ROLE_PERMISSIONS.get(role)
        if granted and ("*" in granted or permission in granted):
            return True
    return False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_permissions.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Add the readiness route (no secrets)**

```python
# services/api/buyeros_api/api/routes/health.py
from fastapi import APIRouter

router = APIRouter()


@router.get("/health/ready")
async def ready() -> dict:
    return {"data": {"api": "ok", "database": "unknown", "queue": "unknown", "providers": "disabled"}, "data_mode": "live"}
```

---

### Task 7: Demo/live mode boundary (frontend, interface-level)

**Files:**
- Modify: `services/contracts.ts` (inspect current symbol names first — snapshot-dependent)
- Create: `services/live/mapping.ts`
- Create: `services/live/mode.ts`
- Create: `tests/contracts/live-mapping.test.ts`

**Interfaces:**
- Produces: `mode(): 'demo' | 'live'` from `import.meta.env.BUYEROS_MODE`; `assertLive<T>(payload: {data_mode: string}): T` that throws when `data_mode !== 'live'`.
- **Verification required:** before editing `services/contracts.ts`, read the actual file at the imported commit and record exact symbols; the audit describes `RecordBase`, `Company`, `Store`, `BuyerDiscoveryClient`.

- [ ] **Step 1: Write the failing test**

```ts
// tests/contracts/live-mapping.test.ts
import { describe, expect, it } from "vitest";
import { assertLive } from "../../services/live/mode";

describe("live mode guard", () => {
  it("rejects demo payloads", () => {
    expect(() => assertLive({ data_mode: "demo" })).toThrow();
  });
  it("accepts live payloads", () => {
    expect(assertLive<{ x: number }>({ data_mode: "live", x: 1 } as never).x).toBe(1);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm exec vitest run tests/contracts/live-mapping.test.ts`
Expected: FAIL — module not found. (A JS test runner must first be pinned; the repo has no `test` script today — see note.)

- [ ] **Step 3: Write minimal implementation**

```ts
// services/live/mode.ts
export function mode(): "demo" | "live" {
  return import.meta.env.BUYEROS_MODE === "live" ? "live" : "demo";
}

export function assertLive<T>(payload: { data_mode?: string }): T {
  if (payload?.data_mode !== "live") throw new Error("refusing non-live payload");
  return payload as unknown as T;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pnpm exec vitest run tests/contracts/live-mapping.test.ts`
Expected: PASS. If no runner is approved, this step is **NOT RUN** and recorded as a blocker.

---

### Task 8: Tenant isolation + auth negative tests

**Files:**
- Create: `services/api/tests/test_tenant_isolation.py`
- Create: `services/api/tests/test_rbac_endpoints.py`

**Interfaces:**
- Consumes: Tasks 4–6. Requires a disposable PostgreSQL with applied migrations (not run in this plan).

- [ ] **Step 1: Write the failing tests** (illustrative, DB-backed)

```python
# services/api/tests/test_tenant_isolation.py
import pytest


@pytest.mark.asyncio
async def test_missing_tenant_context_fails_closed(db_session_factory):
    # a session without SET LOCAL app.workspace_id must not read memberships
    ...


@pytest.mark.asyncio
async def test_pooled_connection_does_not_leak_tenant(db_engine):
    # set workspace A, release; reacquire and query before setting B → must fail closed
    ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/test_tenant_isolation.py -v`
Expected: FAIL (fixtures absent).

- [ ] **Step 3: Implement the minimal fixtures and assertions** to make both tests pass against a disposable database.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_tenant_isolation.py tests/test_rbac_endpoints.py -v`
Expected: PASS. **NOT RUN** in this plan (no disposable DB provisioned).

---

## Self-Review

- **Spec coverage:** P1 spec sections A (Tasks 4–6), B (Tasks 2–4, 8), C (Task 7) are mapped. Remaining P1 items needing their own tasks before Build: full role→endpoint route wiring, workspace/project route scaffolding, and the generated OpenAPI client — deferred to the BO-003/Build plan.
- **Placeholder scan:** no `TBD`/`TODO`; each code step shows real code. Task 7/8 note the unverifiable items explicitly rather than inventing them.
- **Type consistency:** `Principal(issuer, subject)`, `is_allowed(roles, permission)`, `tenant_session(engine, workspace_id)`, `assertLive<T>(payload)` are consistent across tasks.

## Global Notes

- No commits, pushes, installs, migrations, provisioning, or provider calls are performed by this plan.
- Every command above is **NOT RUN** except where an earlier session recorded execution; results must be captured in the progress record with exact output.
- Execution requires an explicitly approved selected task and a populated `YNWAforever/BuyerOS` checkout.
