# P12 Project/Profile Writes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **Build is NOT authorized by this document**; execution requires explicit approval under a dependency waiver.

**Goal:** Make the project/offer/profile workflow real: create or select a project, save the offer and buyer requirements, approve a specific immutable profile revision, and reload it.

**Architecture:** The API gains the contract's project write surface (`createProject` full validation, `updateProject` with `If-Match` versioning, `archiveProject`) plus approval settling the project's active ICP version; a migration adds the missing columns. The P11 client seam gains write support, and a pure `Offer` mapper turns the wizard's free text into contract payloads, rejecting anything it cannot resolve.

**Tech Stack:** Python 3.12+ (installed 3.14.6), FastAPI, Pydantic v2, SQLAlchemy 2 + psycopg, Alembic, pytest + httpx TestClient, uv; TypeScript/React 19 + Next 16, Node 24 for the checks. **No new dependency.**

## Global Constraints

- Spec: `docs/buyeros/specs/2026-09-18-p12-project-profile-writes-design.md`. Contract: `docs/buyeros/contracts/openapi.proposed.yaml` (authoritative). Task: `docs/buyeros/tasks/BO-007-...md`.
- Branch `p12-project-profile-writes` from `p11-demo-live-adapter` @ `cf20b1a` (it extends the P11 seam; it does not build off `main`).
- Plan-only artifact: no remote commits/pushes, deploys, cloud resources, real-data migrations, paid calls, mailboxes, or sends.
- Fail closed: unconfigured auth still returns `401`. Roles come from Postgres membership only.
- Contract-first: every implemented route matches the contract's `operationId`, method, path and schema names, and every emitted response key must be contract-declared.
- **`projects.version` is the strong ETag.** Responses carry `ETag: "<version>"`; `updateProject` and `archiveProject` require `If-Match` equal to it, else `412 STALE_REVISION`. Missing/malformed `If-Match` or `Idempotency-Key` is `400 INVALID_REQUEST`.
- ICP versions are immutable; edits create a new `number`. Only a successful approval sets `projects.active_icp_version_id`, and only for a version belonging to that project.
- **Material change** means `offer` or `markets` changed: it supersedes the active ICP version and clears the pointer in the same transaction. `name`/`website`/`language_preferences` are not material.
- Archiving sets `status="archived"`; nothing is ever hard-deleted and no history is rewritten.
- Request bodies are strict (`extra="forbid"`): an unknown key, including `sender_identity`, is `422` rather than silently ignored.
- `Idempotency-Key` is required on every project mutation; the same key with a different body is `409 IDEMPOTENCY_CONFLICT`; the same key with the same body replays.
- The frontend never fabricates: unresolvable markets or languages raise, and live failures never fall back to demo data.
- Every task also runs `npx eslint` clean on changed files and the plan's type check:
  `npx tsc --noEmit --strict --module esnext --moduleResolution bundler --target ES2022 <changed .ts files>`.
- Every unexecuted check is **NOT RUN**.

**Existing interfaces this plan consumes (already implemented):**
- `buyeros_api.api.deps`: `get_engine`, `tenant_scoped`, `load_membership`, `permission_for_roles` (second argument is the **contract operation id**).
- `buyeros_api.api.errors`: `ApiError`, `envelope`; `buyeros_api.api.auth`: `Principal`, `get_principal`.
- `buyeros_api.db.icp`: `Project`, `IcpVersion`, `canonical_hash`.
- `buyeros_api.services.icp_service`: `StaleRevision`, `verify_approval_hash`.
- `buyeros_api.db.contact.IdempotencyRecord`: unique `(workspace_id, actor_id, operation_id, key)` with `request_hash`, `status`, `resource_id`.
- `buyeros_api.services.confirm_service`: `request_fingerprint(body)`, `IdempotencyConflict`.
- `services/live/{mode,mapping,client,session,read,storage}.ts` (P11): `createLiveClient(fetchImpl, baseUrl)`, `LiveError`, `LiveCancelled`, `SessionScope`, `loadLive`.
- `tests/conftest.py`: `pg_dsn`, `migrated`, `seeded`, `runtime_role_dsn`. `tests/auth_fixtures.py`: `ISSUER`, `AUDIENCE`, `jwks_document()`, `make_token()`. `tests/test_auth_routes_db.py`'s `auth_env` is the pattern for authenticated DB tests.

---

### Task 1: Migration and model columns

**Files:**
- Modify: `services/api/buyeros_api/db/icp.py`
- Modify: `services/api/tests/conftest.py`
- Create: `services/api/alembic/versions/0009_project_profile_columns.py`
- Create: `services/api/tests/test_api_projects_db.py`

**Interfaces:**
- Produces: `Project.company_name`, `Project.offer`, `Project.website`, `Project.markets`, `Project.language_preferences`, `Project.version`, `Project.active_icp_version_id`; `IcpVersion.superseded_at`.
- Consumes: `Base`, `TenantMixin`.
- Note: `tests/conftest.py`'s `seeded` fixture must supply the new NOT NULL columns, because the migration drops the backfill defaults; without it every `seeded` consumer errors. The test module also proves the migration's downgrade/backfill round-trip and that the server defaults are dropped.

- [ ] **Step 1: Write the failing test**

```python
# services/api/tests/test_api_projects_db.py
"""BO-007: the project/profile columns exist and the migration round-trips."""
import psycopg
import pytest

PROJECT_COLUMNS = {"company_name", "offer", "website", "markets", "language_preferences", "version", "active_icp_version_id"}


def test_project_profile_columns_exist(migrated):
    with psycopg.connect(migrated) as conn:
        rows = conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'projects'"
        ).fetchall()
    present = {r[0] for r in rows}
    assert PROJECT_COLUMNS <= present, PROJECT_COLUMNS - present


def test_icp_versions_has_superseded_at(migrated):
    with psycopg.connect(migrated) as conn:
        rows = conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'icp_versions'"
        ).fetchall()
    assert "superseded_at" in {r[0] for r in rows}


def test_new_project_columns_are_not_nullable(migrated):
    with psycopg.connect(migrated) as conn:
        rows = conn.execute(
            "SELECT column_name, is_nullable FROM information_schema.columns "
            "WHERE table_name = 'projects' AND column_name = ANY(%s)",
            (sorted(PROJECT_COLUMNS),),
        ).fetchall()
    nullable = {r[0] for r in rows if r[1] == "YES"}
    assert nullable == {"website", "active_icp_version_id"}, nullable
```

- [ ] **Step 2: Run to verify it fails**

Run (cwd `services/api`): `uv run pytest tests/test_api_projects_db.py -v`
Expected: FAIL — the columns do not exist (or the DB is skipped; see the note below).

**Note:** these tests are DB-backed and skip cleanly without Docker, exactly like the existing `*_db.py` tests. A skipped run is **NOT RUN**, not a pass — report the skip count.

- [ ] **Step 3: Write the migration and the model columns**

```python
# services/api/alembic/versions/0009_project_profile_columns.py
"""project profile columns and ICP supersession

Revision ID: 0009_project_profile_columns
Revises: 0008_grant_users_select
Create Date: 2026-09-18

The contract's `Project` requires company_name, offer, markets, language_preferences and a
monotonic `version` (the strong ETag used by If-Match on update/archive), and approval needs a
pointer to the active ICP version. `icp_versions.superseded_at` makes the contract's status
(saved | approved | superseded) derivable without rewriting history.

Existing rows are backfilled with empty defaults so the migration applies to a populated
database; the defaults are then dropped so new inserts must supply the values.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_project_profile_columns"
down_revision: str | None = "0008_grant_users_select"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ADDED = (
    ("company_name", sa.String(200), ""),
    ("offer", sa.Text(), ""),
    ("markets", postgresql.ARRAY(sa.String(2)), "{}"),
    ("language_preferences", postgresql.ARRAY(sa.String(16)), "{}"),
    ("version", sa.Integer(), "1"),
)


def upgrade() -> None:
    for name, type_, default in _ADDED:
        op.add_column("projects", sa.Column(name, type_, nullable=False, server_default=default))
    op.add_column("projects", sa.Column("website", sa.String(2000), nullable=True))
    op.add_column("projects", sa.Column("active_icp_version_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("icp_versions", sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True))
    for name, _, _ in _ADDED:
        op.alter_column("projects", name, server_default=None)


def downgrade() -> None:
    op.drop_column("icp_versions", "superseded_at")
    op.drop_column("projects", "active_icp_version_id")
    op.drop_column("projects", "website")
    for name, _, _ in reversed(_ADDED):
        op.drop_column("projects", name)
```

In `services/api/buyeros_api/db/icp.py`, extend the models (keep the existing `name` and `status`):

```python
from sqlalchemy import BigInteger, DateTime, ForeignKeyConstraint, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

class Project(Base, TenantMixin):
    __tablename__ = "projects"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_projects_workspace_id"),
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_projects_workspace"),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    company_name: Mapped[str] = mapped_column(String(200), nullable=False)
    offer: Mapped[str] = mapped_column(Text, nullable=False)
    website: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    markets: Mapped[list[str]] = mapped_column(ARRAY(String(2)), nullable=False, default=list)
    language_preferences: Mapped[list[str]] = mapped_column(ARRAY(String(16)), nullable=False, default=list)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    active_icp_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

class IcpVersion(Base, TenantMixin):
    ...  # unchanged fields, plus:
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_api_projects_db.py -v`
Expected: PASS (3 passed) with Docker available; otherwise report the skips as NOT RUN.

- [ ] **Step 5: Commit**

```bash
git add services/api/alembic/versions/0009_project_profile_columns.py services/api/buyeros_api/db/icp.py services/api/tests/conftest.py services/api/tests/test_api_projects_db.py
git commit -m "feat(api): add project profile columns and ICP supersession"
```

---

### Task 2: Strict request schemas, full createProject, response shape

**Files:**
- Create: `services/api/buyeros_api/api/schemas.py`
- Create: `services/api/buyeros_api/api/idempotency.py`
- Modify: `services/api/buyeros_api/api/routes/projects.py`
- Modify: `services/api/buyeros_api/db/contact.py`
- Create: `services/api/alembic/versions/0010_widen_idempotency_key.py`
- Modify: `services/api/tests/test_api_projects_db.py`
- Modify: `services/api/tests/test_api_routes_contract.py`

**Interfaces:**
- Produces: `ProjectCreate`, `ProjectUpdate`, `ArchiveRequest` (strict Pydantic v2 models); `_project_data(project) -> dict` returning the full contract subset; `begin_idempotency`/`complete_idempotency` in `api/idempotency.py`.
- Post-review fix (committed separately): the contract's `IdempotencyKey` allows 8..200 chars but `idempotency_records.key` was `VARCHAR(128)`, so a 129-200 char key would 500. Migration `0010_widen_idempotency_key` widens it to 200 and the model matches.
- Consumes: `Project` (Task 1), `envelope`/`ApiError`, `get_principal`, `tenant_scoped`/`load_membership`/`permission_for_roles`, `IdempotencyRecord`, `request_fingerprint`/`same_request`/`IdempotencyConflict`.

- [ ] **Step 1: Write the failing test** (the DB-backed authenticated pattern from `test_auth_routes_db.py`)

Append to `services/api/tests/test_api_projects_db.py` a module-level fixture and tests. Reuse the shape of `tests/test_auth_routes_db.py`'s `auth_env`, adding a reviewer. The teardown deletes in FK-safe order (`idempotency_records`, `icp_versions`, then `projects`), because `fk_icp_versions_project` has no `ON DELETE` and a reused `Idempotency-Key` across tests would otherwise replay:

```python
import asyncio
import uuid

from fastapi.testclient import TestClient

from buyeros_api.api import auth
from buyeros_api.api.app import create_app
from buyeros_api.api.jwks import JwksKeyCache
from buyeros_api.api.verifier import TokenVerifier
from tests import auth_fixtures as fx
from tests.conftest import runtime_role_dsn

WORKSPACE_A = "11111111-1111-4111-8111-111111111111"
OPERATOR = "auth0|operator-a"
REVIEWER = "auth0|reviewer-a"
CREATE = {
    "name": "Sensors Europe",
    "company_name": "HarbourSense Instruments",
    "offer": "Industrial sensing for process monitoring.",
    "markets": ["DE", "NL"],
    "language_preferences": ["en", "de"],
}


@pytest.fixture
def api(seeded, monkeypatch):
    """An authenticated client on the runtime role with operator and reviewer members."""
    monkeypatch.setenv("BUYEROS_DATABASE_URL", runtime_role_dsn(seeded))
    monkeypatch.setenv("BUYEROS_AUTH0_ISSUER", fx.ISSUER)
    monkeypatch.setenv("BUYEROS_AUTH0_AUDIENCE", fx.AUDIENCE)
    from buyeros_api.settings import get_settings

    get_settings.cache_clear()
    cache = JwksKeyCache(lambda: asyncio.sleep(0, result=fx.jwks_document()), cache_seconds=300)
    monkeypatch.setattr(auth, "_verifier_from_settings", lambda: TokenVerifier(cache, issuer=fx.ISSUER, audience=fx.AUDIENCE))

    owner = psycopg.connect(seeded, autocommit=True)
    for subject, roles in ((OPERATOR, ["operator"]), (REVIEWER, ["reviewer"])):
        user_id = uuid.uuid5(uuid.NAMESPACE_URL, subject)
        owner.execute("DELETE FROM memberships WHERE user_id = %s", (user_id,))
        owner.execute("DELETE FROM users WHERE id = %s", (user_id,))
        owner.execute("INSERT INTO users(id, issuer, subject) VALUES (%s, %s, %s)", (user_id, fx.ISSUER, subject))
        owner.execute(
            "INSERT INTO memberships(id, workspace_id, user_id, roles, active) VALUES (%s, %s, %s, %s, true)",
            (uuid.uuid4(), WORKSPACE_A, user_id, roles),
        )
    owner.close()
    try:
        yield TestClient(create_app(), raise_server_exceptions=False)
    finally:
        get_settings.cache_clear()
        owner = psycopg.connect(seeded, autocommit=True)
        for subject in (OPERATOR, REVIEWER):
            user_id = uuid.uuid5(uuid.NAMESPACE_URL, subject)
            owner.execute("DELETE FROM memberships WHERE user_id = %s", (user_id,))
            owner.execute("DELETE FROM users WHERE id = %s", (user_id,))
        owner.execute("DELETE FROM idempotency_records WHERE workspace_id = %s", (WORKSPACE_A,))
        owner.execute("DELETE FROM icp_versions WHERE workspace_id = %s", (WORKSPACE_A,))
        owner.execute("DELETE FROM projects WHERE workspace_id = %s", (WORKSPACE_A,))
        owner.close()


def _h(subject=OPERATOR, key="create-01", **extra):
    headers = {"Authorization": f"Bearer {fx.make_token(sub=subject)}", "Idempotency-Key": key}
    headers.update(extra)
    return headers


def test_create_project_persists_the_full_payload(api):
    response = api.post(f"/v1/workspaces/{WORKSPACE_A}/projects", json=CREATE, headers=_h())
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert data["company_name"] == CREATE["company_name"]
    assert data["markets"] == ["DE", "NL"]
    assert data["version"] == 1
    assert response.headers["ETag"] == '"1"'


def test_the_same_create_key_and_body_replays_instead_of_duplicating(api):
    first = api.post(f"/v1/workspaces/{WORKSPACE_A}/projects", json=CREATE, headers=_h(key="create-replay"))
    assert first.status_code == 201, first.text
    second = api.post(f"/v1/workspaces/{WORKSPACE_A}/projects", json=CREATE, headers=_h(key="create-replay"))
    assert second.status_code == 201, second.text
    assert second.json()["data"]["id"] == first.json()["data"]["id"]
    listed = api.get(f"/v1/workspaces/{WORKSPACE_A}/projects", headers=_h(key="list-0001")).json()["data"]["items"]
    assert len(listed) == 1


def test_the_same_create_key_with_a_different_body_conflicts(api):
    assert api.post(f"/v1/workspaces/{WORKSPACE_A}/projects", json=CREATE, headers=_h(key="create-conflict")).status_code == 201
    changed = {**CREATE, "name": "Sensors Europe revised"}
    response = api.post(f"/v1/workspaces/{WORKSPACE_A}/projects", json=changed, headers=_h(key="create-conflict"))
    assert response.status_code == 409
    assert response.json()["code"] == "IDEMPOTENCY_CONFLICT"


def test_a_malformed_idempotency_key_is_rejected(api):
    response = api.post(f"/v1/workspaces/{WORKSPACE_A}/projects", json=CREATE, headers=_h(key="short"))
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_REQUEST"


def test_unknown_keys_are_rejected(api):
    body = {**CREATE, "sender_identity": {"display_name": "x"}}
    response = api.post(f"/v1/workspaces/{WORKSPACE_A}/projects", json=body, headers=_h())
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_REQUEST"


def test_an_invalid_market_code_is_rejected(api):
    response = api.post(f"/v1/workspaces/{WORKSPACE_A}/projects", json={**CREATE, "markets": ["germany"]}, headers=_h())
    assert response.status_code == 422


def test_a_viewer_cannot_create(api):
    response = api.post(f"/v1/workspaces/{WORKSPACE_A}/projects", json=CREATE, headers=_h(subject=REVIEWER))
    # reviewer is deliberately not in createProject's x-permitted-roles (operator, workspace_admin)
    assert response.status_code == 403, response.text
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_api_projects_db.py -v -k create or unknown or invalid or viewer`
Expected: FAIL — `ProjectCreate` does not exist / create ignores the extra fields (the current route reads only `name`), so the schema assertions fail.

- [ ] **Step 3: Write `schemas.py` and rewrite the project routes**

```python
# services/api/buyeros_api/api/schemas.py
"""Strict request bodies (contract `additionalProperties: false` and x-validation)."""

from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _check_website(value: str | None) -> str | None:
    """The contract declares `format: uri`; an annotated value must still have a scheme."""
    if value is None:
        return value
    parsed = urlparse(value)
    if not parsed.scheme or (parsed.scheme in ("http", "https") and not parsed.netloc):
        raise ValueError(f"website must be an absolute URI: {value!r}")
    return value


class _ProjectFields(_Strict):
    name: str = Field(min_length=2, max_length=160)
    company_name: str = Field(min_length=2, max_length=200)
    offer: str = Field(max_length=20000)
    website: str | None = Field(default=None, max_length=2000)
    markets: list[str] = Field(min_length=1, max_length=20)
    language_preferences: list[str] = Field(min_length=1, max_length=10)

    @field_validator("markets")
    @classmethod
    def _iso_markets(cls, value: list[str]) -> list[str]:
        for code in value:
            if len(code) != 2 or not code.isalpha() or code != code.upper():
                raise ValueError(f"market code must be ISO-3166 alpha-2: {code!r}")
        return value

    @field_validator("website")
    @classmethod
    def _uri_website(cls, value: str | None) -> str | None:
        return _check_website(value)


class ProjectCreate(_ProjectFields):
    pass


class ProjectUpdate(_Strict):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    company_name: str | None = Field(default=None, min_length=2, max_length=200)
    offer: str | None = Field(default=None, max_length=20000)
    website: str | None = Field(default=None, max_length=2000)
    markets: list[str] | None = Field(default=None, min_length=1, max_length=20)
    language_preferences: list[str] | None = Field(default=None, min_length=1, max_length=10)

    @field_validator("markets")
    @classmethod
    def _iso_markets(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        for code in value:
            if len(code) != 2 or not code.isalpha() or code != code.upper():
                raise ValueError(f"market code must be ISO-3166 alpha-2: {code!r}")
        return value

    @field_validator("website")
    @classmethod
    def _uri_website(cls, value: str | None) -> str | None:
        return _check_website(value)


class ArchiveRequest(_Strict):
    """Contract `ArchiveRequest`: a required, auditable reason."""

    reason: str = Field(min_length=3, max_length=2000)
```

Rewrite `services/api/buyeros_api/api/routes/projects.py`'s `_project_data` and add the `Response` parameter so the ETag can be set. Introduce the shared idempotency helper here (Task 3 reuses it for PATCH/DELETE):

```python
# services/api/buyeros_api/api/idempotency.py
"""Project-mutation idempotency, reusing the P4 record and the P5 conflict rule."""

from dataclasses import dataclass

from sqlalchemy import select


@dataclass
class IdempotencyOutcome:
    """The record for this (workspace, actor, operation, key) and whether it is a replay."""

    record: object
    replay: bool


async def begin_idempotency(
    session, *, workspace_id, actor_id, operation_id: str, key: str, body: dict
) -> IdempotencyOutcome:
    """Return the completed record on a replay, or insert an in_progress one.

    The contract's `IdempotencyKey` is 8..200 opaque characters; anything else is 400. The same
    key with a different body is 409, matching `confirm_service.same_request`; a recorded record
    that is still `in_progress` is a conflict rather than a silent second mutation.
    """
    from ..db.contact import IdempotencyRecord
    from ..services.confirm_service import IdempotencyConflict, request_fingerprint, same_request
    from .errors import ApiError

    if not (8 <= len(key) <= 200):
        raise ApiError(400, "INVALID_REQUEST", "Idempotency-Key must be 8..200 characters")
    fingerprint = request_fingerprint(body)
    existing = (
        await session.execute(
            select(IdempotencyRecord).where(
                IdempotencyRecord.workspace_id == workspace_id,
                IdempotencyRecord.actor_id == actor_id,
                IdempotencyRecord.operation_id == operation_id,
                IdempotencyRecord.key == key,
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        record = IdempotencyRecord(
            workspace_id=workspace_id,
            actor_id=actor_id,
            operation_id=operation_id,
            key=key,
            request_hash=fingerprint,
            status="in_progress",
        )
        session.add(record)
        await session.flush()
        return IdempotencyOutcome(record, replay=False)
    try:
        same_request(existing.key, existing.request_hash, key, fingerprint, raise_on_conflict=True)
    except IdempotencyConflict as exc:
        raise ApiError(409, "IDEMPOTENCY_CONFLICT", str(exc)) from exc
    if existing.status != "completed":
        raise ApiError(409, "IDEMPOTENCY_CONFLICT", "request with this key is still in progress")
    return IdempotencyOutcome(existing, replay=True)


def complete_idempotency(outcome: IdempotencyOutcome, resource_id: str) -> None:
    """Mark this transaction's record complete, so a later replay can return its resource."""
    outcome.record.status = "completed"
    outcome.record.resource_id = resource_id


def if_match_version(if_match: str | None) -> int:
    """Parse the contract's strong ETag ('4'); missing or malformed is 400."""
    from .errors import ApiError

    if not if_match:
        raise ApiError(400, "INVALID_REQUEST", "If-Match header is required")
    if len(if_match) < 2 or not if_match.startswith('"') or not if_match.endswith('"'):
        raise ApiError(400, "INVALID_REQUEST", 'If-Match must be a strong ETag like "4"')
    try:
        version = int(if_match[1:-1])
    except ValueError as exc:
        raise ApiError(400, "INVALID_REQUEST", 'If-Match must be a strong ETag like "4"') from exc
    if version < 1:
        raise ApiError(400, "INVALID_REQUEST", 'If-Match must be a strong ETag like "4"')
    return version
```

Then in `projects.py`:

```python
def _project_data(project) -> dict:
    return {
        "id": str(project.id),
        "workspace_id": str(project.workspace_id),
        "version": project.version,
        "created_at": project.created_at.isoformat(),
        "updated_at": project.updated_at.isoformat(),
        "data_mode": "live",
        "name": project.name,
        "company_name": project.company_name,
        "offer": project.offer,
        "website": project.website,
        "markets": list(project.markets),
        "language_preferences": list(project.language_preferences),
        "status": project.status,
        "active_icp_version_id": str(project.active_icp_version_id) if project.active_icp_version_id else None,
    }


@router.post("", status_code=201)
async def create_project(
    workspace_id: uuid.UUID,
    request: Request,
    response: Response,
    payload: ProjectCreate,
    principal: Principal = Depends(get_principal),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    from sqlalchemy import select

    from ...db.icp import Project
    from ..deps import load_membership, permission_for_roles, tenant_scoped
    from ..idempotency import begin_idempotency, complete_idempotency

    if not idempotency_key:
        raise ApiError(400, "INVALID_REQUEST", "Idempotency-Key header is required")

    async with tenant_scoped(workspace_id) as session:
        membership = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(membership["roles"], "createProject"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        outcome = await begin_idempotency(
            session, workspace_id=workspace_id, actor_id=membership["user_id"],
            operation_id="createProject", key=idempotency_key, body=payload.model_dump(mode="json"),
        )
        if outcome.replay:
            project = (
                await session.execute(
                    select(Project).where(
                        Project.workspace_id == workspace_id, Project.id == uuid.UUID(str(outcome.record.resource_id))
                    )
                )
            ).scalar_one_or_none()
            if project is None:
                raise ApiError(404, "NOT_FOUND", "project not found")
            response.headers["ETag"] = f'"{project.version}"'
            return envelope(_project_data(project), request.state.request_id)
        project = Project(
            workspace_id=workspace_id,
            name=payload.name,
            company_name=payload.company_name,
            offer=payload.offer,
            website=payload.website,
            markets=payload.markets,
            language_preferences=payload.language_preferences,
        )
        session.add(project)
        await session.flush()
        complete_idempotency(outcome, str(project.id))
        data = _project_data(project)
        response.headers["ETag"] = f'"{project.version}"'
    return envelope(data, request.state.request_id)
```

Add the imports the file now needs: `from fastapi import APIRouter, Depends, Header, Response` and `from .schemas import ArchiveRequest, ProjectCreate, ProjectUpdate`. Also extend `test_api_routes_contract.py`'s `_Project` stub so it carries `version`, `created_at`, `updated_at`, `company_name`, `offer`, `website`, `markets`, `language_preferences` and `active_icp_version_id`; otherwise the response-subset test raises `AttributeError` against the widened `_project_data`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_api_projects_db.py -v`
Expected: PASS with Docker (report skips otherwise as NOT RUN). Also run `uv run pytest tests/test_api_routes_contract.py -q` — the response-subset test must still pass, since every new key is contract-declared.

- [ ] **Step 5: Commit**

```bash
git add services/api/buyeros_api/api/schemas.py services/api/buyeros_api/api/idempotency.py services/api/buyeros_api/api/routes/projects.py services/api/tests/test_api_projects_db.py services/api/tests/test_api_routes_contract.py
git commit -m "feat(api): strict project schemas, idempotent full create"
```

---

### Task 3: Versioned mutations — updateProject and archiveProject

**Files:**
- Modify: `services/api/buyeros_api/api/routes/projects.py`
- Modify: `services/api/buyeros_api/api/unimplemented.py`
- Modify: `services/api/tests/test_api_buyers.py`
- Modify: `services/api/tests/test_api_projects_db.py`

**Interfaces:**
- Produces: PATCH and DELETE routes, both applying `begin_idempotency`/`complete_idempotency`/`if_match_version` (Task 2) and the material-change supersession rule.
- Consumes: `ProjectUpdate`/`ArchiveRequest` (Task 2), `begin_idempotency`/`complete_idempotency`/`if_match_version`, `IcpVersion`, `_project_data`.

- [ ] **Step 1: Write the failing tests**

Append to `services/api/tests/test_api_projects_db.py`:

```python
def _create(api, key="create-1"):
    response = api.post(f"/v1/workspaces/{WORKSPACE_A}/projects", json=CREATE, headers=_h(key=key))
    assert response.status_code == 201, response.text
    return response.json()["data"]["id"]


def test_update_bumps_the_version_and_sets_the_etag(api):
    project_id = _create(api)
    response = api.patch(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{project_id}",
        json={"offer": "Revised offer for process monitoring."},
        headers=_h(key="update-01", **{"If-Match": '"1"'}),
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["offer"].startswith("Revised")
    assert data["version"] == 2
    assert response.headers["ETag"] == '"2"'
    assert data["name"] == CREATE["name"]  # untouched fields survive a partial update


def test_a_repeated_update_key_and_body_replays_the_version(api):
    project_id = _create(api)
    body = {"offer": "Revised offer for process monitoring."}
    first = api.patch(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{project_id}",
        json=body, headers=_h(key="update-replay", **{"If-Match": '"1"'}),
    )
    assert first.status_code == 200, first.text
    replay = api.patch(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{project_id}",
        json=body, headers=_h(key="update-replay", **{"If-Match": '"1"'}),
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["data"]["version"] == 2  # a replay, not a second bump
    assert replay.json()["data"]["id"] == first.json()["data"]["id"]


def test_a_stale_if_match_is_rejected(api):
    project_id = _create(api)
    api.patch(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{project_id}",
        json={"offer": "first"},
        headers=_h(key="update-10", **{"If-Match": '"1"'}),
    )
    response = api.patch(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{project_id}",
        json={"offer": "second"},
        headers=_h(key="update-11", **{"If-Match": '"1"'}),
    )
    assert response.status_code == 412
    assert response.json()["code"] == "STALE_REVISION"


def test_missing_if_match_is_rejected(api):
    project_id = _create(api)
    response = api.patch(f"/v1/workspaces/{WORKSPACE_A}/projects/{project_id}", json={"offer": "x"}, headers=_h(key="update-12"))
    assert response.status_code == 400


def test_archive_requires_workspace_admin(api):
    project_id = _create(api)
    response = api.delete(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{project_id}",
        json={"reason": "Pilot ended."},
        headers=_h(key="archive-01", **{"If-Match": '"1"'}),
    )
    assert response.status_code == 403  # operator is not permitted to archive


def test_archive_requires_the_contract_reason(api):
    project_id = _create(api)
    response = api.delete(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{project_id}",
        headers=_h(key="archive-02", **{"If-Match": '"1"'}),
    )
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_REQUEST"


def test_the_same_key_with_a_different_body_conflicts(api):
    project_id = _create(api)
    first = api.patch(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{project_id}",
        json={"offer": "one"},
        headers=_h(key="dup-0001", **{"If-Match": '"1"'}),
    )
    assert first.status_code == 200
    second = api.patch(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{project_id}",
        json={"offer": "two"},
        headers=_h(key="dup-0001", **{"If-Match": '"2"'}),
    )
    assert second.status_code == 409
    assert second.json()["code"] == "IDEMPOTENCY_CONFLICT"
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_api_projects_db.py -v -k update or stale or missing or archive or conflict`
Expected: FAIL — PATCH/DELETE currently answer `501` (they are in the registry).

- [ ] **Step 3: Implement the two routes**

In `projects.py`, add the material fields and the two routes. Both call `begin_idempotency` before loading the project, return the existing resource on a replay, and mark the record completed with `complete_idempotency` only once the mutation has succeeded (a raised 404/412 rolls the record back with the transaction):

```python
_MATERIAL_FIELDS = ("offer", "markets")


@router.patch("/{project_id}")
async def update_project(
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    payload: ProjectUpdate,
    request: Request,
    response: Response,
    principal: Principal = Depends(get_principal),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    if_match: str | None = Header(default=None, alias="If-Match"),
) -> dict:
    from sqlalchemy import func, select

    from ...db.icp import IcpVersion, Project
    from ..deps import load_membership, permission_for_roles, tenant_scoped
    from ..idempotency import begin_idempotency, complete_idempotency, if_match_version

    if not idempotency_key:
        raise ApiError(400, "INVALID_REQUEST", "Idempotency-Key header is required")
    expected_version = if_match_version(if_match)
    changes = payload.model_dump(exclude_unset=True, mode="json")
    if not changes:
        raise ApiError(422, "INVALID_REQUEST", "at least one field is required")

    async with tenant_scoped(workspace_id) as session:
        membership = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(membership["roles"], "updateProject"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        outcome = await begin_idempotency(
            session, workspace_id=workspace_id, actor_id=membership["user_id"],
            operation_id="updateProject", key=idempotency_key, body=changes,
        )
        project = (
            await session.execute(
                select(Project).where(Project.workspace_id == workspace_id, Project.id == project_id).with_for_update()
            )
        ).scalar_one_or_none()
        if project is None:
            raise ApiError(404, "NOT_FOUND", "project not found")
        if outcome.replay:
            response.headers["ETag"] = f'"{project.version}"'
            return envelope(_project_data(project), request.state.request_id)
        if project.version != expected_version:
            raise ApiError(412, "STALE_REVISION", "project changed; reload it")
        material = False
        for field, value in changes.items():
            if field in _MATERIAL_FIELDS and getattr(project, field) != value:
                material = True
            setattr(project, field, value)
        project.version += 1
        if material and project.active_icp_version_id is not None:
            # Contract: a material offer/market change supersedes the active profile.
            await session.execute(
                IcpVersion.__table__.update()
                .where(IcpVersion.workspace_id == workspace_id, IcpVersion.id == project.active_icp_version_id)
                .values(superseded_at=func.now())
            )
            project.active_icp_version_id = None
        await session.flush()
        complete_idempotency(outcome, str(project.id))
        data = _project_data(project)
        response.headers["ETag"] = f'"{project.version}"'
    return envelope(data, request.state.request_id)


@router.delete("/{project_id}")
async def archive_project(
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    payload: ArchiveRequest,
    request: Request,
    response: Response,
    principal: Principal = Depends(get_principal),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    if_match: str | None = Header(default=None, alias="If-Match"),
) -> dict:
    from sqlalchemy import select

    from ...db.icp import Project
    from ..deps import load_membership, permission_for_roles, tenant_scoped
    from ..idempotency import begin_idempotency, complete_idempotency, if_match_version

    if not idempotency_key:
        raise ApiError(400, "INVALID_REQUEST", "Idempotency-Key header is required")
    expected_version = if_match_version(if_match)
    body = payload.model_dump(mode="json")

    async with tenant_scoped(workspace_id) as session:
        membership = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(membership["roles"], "archiveProject"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        outcome = await begin_idempotency(
            session, workspace_id=workspace_id, actor_id=membership["user_id"],
            operation_id="archiveProject", key=idempotency_key, body=body,
        )
        project = (
            await session.execute(
                select(Project).where(Project.workspace_id == workspace_id, Project.id == project_id).with_for_update()
            )
        ).scalar_one_or_none()
        if project is None:
            raise ApiError(404, "NOT_FOUND", "project not found")
        if outcome.replay:
            response.headers["ETag"] = f'"{project.version}"'
            return envelope(_project_data(project), request.state.request_id)
        if project.version != expected_version:
            raise ApiError(412, "STALE_REVISION", "project changed; reload it")
        project.status = "archived"
        project.version += 1
        await session.flush()
        complete_idempotency(outcome, str(project.id))
        data = _project_data(project)
        response.headers["ETag"] = f'"{project.version}"'
    return envelope(data, request.state.request_id)
```

The contract's `ArchiveRequest.reason` is validated but not persisted (no column this phase; recorded in the spec's out-of-scope list). The reason is part of the idempotency fingerprint, so the same key with a different reason is a `409`.

Remove the two entries from `services/api/buyeros_api/api/unimplemented.py`:

```python
    "archiveProject": ("delete", "/v1/workspaces/{workspace_id}/projects/{project_id}"),
    "updateProject": ("patch", "/v1/workspaces/{workspace_id}/projects/{project_id}"),
```

and add `"updateProject"` and `"archiveProject"` to the `implemented` set in `tests/test_api_buyers.py::test_registry_covers_every_unimplemented_contract_operation`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_api_projects_db.py tests/test_api_buyers.py tests/test_api_routes_contract.py -v`
Expected: PASS with Docker. The registry test must still assert equality against every non-implemented contract operation.

- [ ] **Step 5: Commit**

```bash
git add services/api/buyeros_api/api/routes/projects.py services/api/buyeros_api/api/unimplemented.py services/api/tests/test_api_buyers.py services/api/tests/test_api_projects_db.py
git commit -m "feat(api): versioned project update and archive with idempotency"
```

---

### Task 4: Approval settles the active profile

**Files:**
- Modify: `services/api/buyeros_api/api/routes/icp.py`
- Modify: `services/api/tests/test_api_projects_db.py`
- Modify: `services/api/tests/test_api_routes_contract.py`

**Interfaces:**
- Consumes: `Project`/`IcpVersion.superseded_at` (Task 1), the existing approve route.
- Produces: approval sets `projects.active_icp_version_id`; a foreign/mismatched version cannot be approved; the superseded status is derivable.

- [ ] **Step 1: Write the failing test**

```python
def test_approval_sets_the_active_profile_and_requires_a_reviewer(api):
    project_id = _create(api)
    saved = api.post(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{project_id}/icp-versions",
        json={"requirements": [{"id": "r1", "text": "Distributes sensors", "category": "must", "hard_exclusion": False}],
              "markets": ["DE"], "buyer_types": ["Distributor"], "languages": ["en"], "offer_facts": []},
        headers=_h(key="i1"),
    )
    assert saved.status_code == 201, saved.text
    version = saved.json()["data"]
    body = {"content_hash": version["content_hash"], "confirmation": True}

    # operator cannot approve (approveICPVersion permits reviewer/workspace_admin)
    denied = api.post(
        f"/v1/workspaces/{WORKSPACE_A}/icp-versions/{version['id']}/approve",
        json=body, headers=_h(key="ap1", **{"If-Match": f'"{version["number"]}"'}),
    )
    assert denied.status_code == 403

    approved = api.post(
        f"/v1/workspaces/{WORKSPACE_A}/icp-versions/{version['id']}/approve",
        json=body, headers=_h(subject=REVIEWER, key="ap2", **{"If-Match": f'"{version["number"]}"'}),
    )
    assert approved.status_code == 200, approved.text

    project = api.get(f"/v1/workspaces/{WORKSPACE_A}/projects/{project_id}", headers=_h()).json()["data"]
    assert project["active_icp_version_id"] == version["id"]


def test_a_material_change_supersedes_and_reopens_the_profile(api):
    project_id = _create(api)
    saved = api.post(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{project_id}/icp-versions",
        json={"requirements": [{"id": "r1", "text": "x", "category": "must", "hard_exclusion": False}],
              "markets": ["DE"], "buyer_types": ["Distributor"], "languages": ["en"], "offer_facts": []},
        headers=_h(key="i1"),
    ).json()["data"]
    api.post(
        f"/v1/workspaces/{WORKSPACE_A}/icp-versions/{saved['id']}/approve",
        json={"content_hash": saved["content_hash"], "confirmation": True},
        headers=_h(subject=REVIEWER, key="ap1", **{"If-Match": f'"{saved["number"]}"'}),
    )
    api.patch(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{project_id}",
        json={"offer": "A materially different offer."},
        headers=_h(key="update-30", **{"If-Match": '"1"'}),
    )
    project = api.get(f"/v1/workspaces/{WORKSPACE_A}/projects/{project_id}", headers=_h()).json()["data"]
    assert project["active_icp_version_id"] is None
    versions = api.get(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{project_id}/icp-versions", headers=_h()
    ).json()["data"]["items"]
    assert [v["status"] for v in versions] == ["superseded"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_api_projects_db.py -v -k approval or material`
Expected: FAIL — approval does not set `active_icp_version_id`, and `superseded` is not derived.

- [ ] **Step 3: Implement**

In `services/api/buyeros_api/api/routes/icp.py`, `_icp_data` derives status from the two timestamps:

```python
        "status": "superseded" if row.superseded_at else ("approved" if row.approved_at else "saved"),
```

and the approve route, after setting `row.approved_at`/`row.approved_by`, settles the project pointer:

```python
        project = (
            await session.execute(
                select(Project).where(Project.workspace_id == workspace_id, Project.id == row.project_id).with_for_update()
            )
        ).scalar_one_or_none()
        if project is None:
            raise ApiError(404, "NOT_FOUND", "project not found")
        project.active_icp_version_id = row.id
```

Import `Project` alongside `IcpVersion`. The lookup by `row.project_id` is what makes a version belonging to a different project unreachable through that project's id, and the `workspace_id` predicate keeps it tenant-safe. Also add `superseded_at = None` to `test_api_routes_contract.py`'s `_Icp` stub, since `_icp_data` now reads it.

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_api_projects_db.py -v`
Expected: PASS with Docker; report skips as NOT RUN.

- [ ] **Step 5: Commit**

```bash
git add services/api/buyeros_api/api/routes/icp.py services/api/tests/test_api_projects_db.py
git commit -m "feat(api): approval settles the project's active profile"
```

---

### Task 5: Client write support

**Files:**
- Modify: `services/live/client.ts`
- Modify: `tests/live-adapter-checks.mjs`

**Interfaces:**
- Produces: `request({path, method, token, scope, signal, body?, idempotencyKey?, ifMatch?})`.
- Consumes: the P11 client.

- [ ] **Step 1: Write the failing checks**

Append to `tests/live-adapter-checks.mjs` (before the final summary line):

```js
await test('a write sends a JSON body and the mutation headers',async()=>{
  const seen=[];
  const client=live.createLiveClient(async(url,init)=>{seen.push(init);return {status:201,ok:true,json:async()=>({data:{id:'p-1'},request_id:'r',data_mode:'live'})};});
  await client.request({path:'/v1/workspaces/w/projects',method:'POST',scope:'s1',token:'t',body:{name:'x'},idempotencyKey:'k1'});
  assert.equal(seen[0].method,'POST');
  assert.equal(seen[0].headers['Content-Type'],'application/json');
  assert.equal(seen[0].headers['Idempotency-Key'],'k1');
  assert.equal(seen[0].headers['If-Match'],undefined);
  assert.deepEqual(JSON.parse(seen[0].body),{name:'x'});
});

await test('If-Match is sent only when supplied',async()=>{
  const seen=[];
  const client=live.createLiveClient(async(url,init)=>{seen.push(init);return {status:200,ok:true,json:async()=>({data:{},request_id:'r',data_mode:'live'})};});
  await client.request({path:'/v1/x',method:'PATCH',scope:'s1',body:{a:1},ifMatch:'"2"',idempotencyKey:'k'});
  assert.equal(seen[0].headers['If-Match'],'"2"');
});

await test('a stale write surfaces as a typed STALE_REVISION',async()=>{
  const client=live.createLiveClient(errorResponder(412,{code:'STALE_REVISION',message:'stale',request_id:'r',retryable:false}));
  await assert.rejects(()=>client.request({path:'/v1/x',method:'PATCH',scope:'s1',body:{},ifMatch:'"1"',idempotencyKey:'k'}),e=>{
    assert.ok(e instanceof live.LiveError);
    assert.equal(e.code,'STALE_REVISION');
    assert.equal(e.status,412);
    return true;
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `node tests/live-adapter-checks.mjs`
Expected: FAIL — the body is not sent and the mutation headers are absent.

- [ ] **Step 3: Implement**

In `services/live/client.ts`:

```ts
export interface LiveRequest {
  path: string;
  method?: string;
  token?: string;
  scope: string;
  signal?: AbortSignal;
  body?: unknown;
  idempotencyKey?: string;
  ifMatch?: string;
}
```

and inside `request`, before the fetch:

```ts
      const headers: Record<string, string> = {Accept: 'application/json'};
      if (token) headers.Authorization = `Bearer ${token}`;
      if (idempotencyKey) headers['Idempotency-Key'] = idempotencyKey;
      if (ifMatch) headers['If-Match'] = ifMatch;
      let payload: string | undefined;
      if (body !== undefined) {
        headers['Content-Type'] = 'application/json';
        payload = JSON.stringify(body);
      }
      ...
        response = await fetchImpl(`${root}${path}`, {method, headers, signal, body: payload});
```

The error mapping is unchanged, so `409`, `412`, `422` surface as `LiveError` codes.

- [ ] **Step 4: Run to verify it passes**

Run: `node tests/live-adapter-checks.mjs` → expect the previous count plus 3.
Run: `node tests/domain-checks.mjs` → `11 domain checks passed`.

- [ ] **Step 5: Commit**

```bash
git add services/live/client.ts tests/live-adapter-checks.mjs
git commit -m "feat(live): write support in the typed client"
```

---

### Task 6: The Offer mapper

**Files:**
- Create: `services/live/profile.ts`
- Modify: `tests/live-adapter-checks.mjs`

**Interfaces:**
- Produces: `resolveMarkets(text)`, `resolveLanguages(text)` returning `{codes, unknown}`; `toProjectCreate(offer)`; `toIcpSaveRequest(offer)`; `ProfileError`.
- Consumes: the wizard's `Offer` shape (structurally typed, no import needed from React).

- [ ] **Step 1: Write the failing checks**

```js
const profile=await loadModule('services/live/profile.ts');

await test('markets resolve from names and codes, case-insensitively',()=>{
  assert.deepEqual(profile.resolveMarkets('Germany, Netherlands/Belgium').codes,['DE','NL','BE']);
  assert.deepEqual(profile.resolveMarkets('de, NL').codes,['DE','NL']);
});

await test('an unknown market is returned, never dropped',()=>{
  const r=profile.resolveMarkets('Germany, Narnia');
  assert.deepEqual(r.codes,['DE']);
  assert.deepEqual(r.unknown,['Narnia']);
});

await test('languages resolve from names',()=>{
  assert.deepEqual(profile.resolveLanguages('English, German, Dutch, French').codes,['en','de','nl','fr']);
});

await test('an unresolvable value makes the mapper raise, naming it',()=>{
  const offer={company:'Acme',product:'Sensors',value:'Value',website:'',markets:'Narnia',language:'English',must:'x',nice:'',exclude:'',buyerTypes:['Distributor'],roles:''};
  assert.throws(()=>profile.toProjectCreate(offer),e=>e instanceof profile.ProfileError&&e.message.includes('Narnia'));
});

await test('toProjectCreate maps the contract fields without inventing values',()=>{
  const offer={company:'Acme GmbH',product:'Industrial sensors',value:'Sensing for automation.',website:'https://acme.example',markets:'Germany',language:'German',must:'Distributes sensors',nice:'',exclude:'',buyerTypes:['Distributor'],roles:'procurement manager'};
  const p=profile.toProjectCreate(offer);
  assert.equal(p.name,'Acme GmbH');
  assert.equal(p.company_name,'Acme GmbH');
  assert.deepEqual(p.markets,['DE']);
  assert.deepEqual(p.language_preferences,['de']);
  assert.ok(p.offer.includes('Sensing for automation.'));
});

await test('toIcpSaveRequest maps requirements with their categories',()=>{
  const offer={company:'Acme',product:'Sensors',value:'V',website:'',markets:'Germany',language:'English',must:'A;B',nice:'C',exclude:'D',buyerTypes:['Distributor'],roles:'buyer',offer_facts:[]};
  const r=profile.toIcpSaveRequest(offer);
  assert.deepEqual(r.requirements.map(x=>x.category),['must','must','nice','exclude']);
  assert.ok(r.requirements.every(x=>typeof x.id==='string'&&x.id.length>0));
  assert.deepEqual(r.buyer_types,['Distributor']);
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `node tests/live-adapter-checks.mjs`
Expected: FAIL — `Cannot find module services/live/profile.ts`.

- [ ] **Step 3: Implement**

```ts
// services/live/profile.ts
/** Turn the wizard's free-text Offer into contract payloads, or refuse. */

export class ProfileError extends Error {}

const MARKETS: Record<string, string> = {
  germany: 'DE', deutschland: 'DE', de: 'DE',
  netherlands: 'NL', holland: 'NL', nl: 'NL',
  belgium: 'BE', belgie: 'BE', belgi: 'BE', be: 'BE',
};
const LANGUAGES: Record<string, string> = {
  english: 'en', en: 'en',
  german: 'de', deutsch: 'de', de: 'de',
  dutch: 'nl', nederlands: 'nl', nl: 'nl',
  french: 'fr', francais: 'fr', fr: 'fr',
};

function split(text: string): string[] {
  return String(text || '').split(/[,/]/).map((part) => part.trim()).filter(Boolean);
}

function resolve(text: string, table: Record<string, string>): {codes: string[]; unknown: string[]} {
  const codes: string[] = [];
  const unknown: string[] = [];
  for (const part of split(text)) {
    const code = table[part.toLowerCase()];
    if (code) { if (!codes.includes(code)) codes.push(code); }
    else unknown.push(part);
  }
  return {codes, unknown};
}

export function resolveMarkets(text: string) { return resolve(text, MARKETS); }
export function resolveLanguages(text: string) { return resolve(text, LANGUAGES); }

export interface Offerish {
  company: string; product: string; value: string; website?: string; markets: string;
  language: string; must?: string; nice?: string; exclude?: string;
  buyerTypes?: string[]; roles?: string; advanced?: Record<string, string>;
}

function requireKnown(label: string, text: string, table: Record<string, string>): string[] {
  const {codes, unknown} = resolve(text, table);
  if (unknown.length) throw new ProfileError(`${label} not recognised: ${unknown.join(', ')}`);
  if (!codes.length) throw new ProfileError(`${label} is required`);
  return codes;
}

export function toProjectCreate(offer: Offerish) {
  const markets = requireKnown('market', offer.markets, MARKETS);
  const languages = requireKnown('language', offer.language, LANGUAGES);
  const advanced = Object.entries(offer.advanced ?? {}).filter(([, v]) => v)
    .map(([k, v]) => `${k}: ${v}`).join('\n');
  return {
    name: offer.company,
    company_name: offer.company,
    offer: [offer.product, offer.value, advanced].filter(Boolean).join('\n'),
    website: offer.website ? offer.website : undefined,
    markets,
    language_preferences: languages,
  };
}

function requirements(text: string, category: string) {
  return split(text).map((item, index) => ({
    id: `${category}-${index + 1}`,
    text: item,
    category,
    hard_exclusion: category === 'exclude',
  }));
}

export function toIcpSaveRequest(offer: Offerish) {
  const markets = requireKnown('market', offer.markets, MARKETS);
  const languages = requireKnown('language', offer.language, LANGUAGES);
  const requirementsList = [
    ...requirements(offer.must ?? '', 'must'),
    ...requirements(offer.nice ?? '', 'nice'),
    ...requirements(offer.exclude ?? '', 'exclude'),
  ];
  if (!requirementsList.length) throw new ProfileError('at least one buyer requirement is required');
  return {
    offer_facts: [],
    requirements: requirementsList,
    markets,
    buyer_types: offer.buyerTypes?.length ? offer.buyerTypes : ['Distributor'],
    languages,
    desired_roles: split(offer.roles ?? ''),
  };
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `node tests/live-adapter-checks.mjs` → previous count plus 6.

- [ ] **Step 5: Commit**

```bash
git add services/live/profile.ts tests/live-adapter-checks.mjs
git commit -m "feat(live): offer-to-payload mapper with explicit rejection"
```

---

### Task 7: Write orchestration

**Files:**
- Create: `services/live/writes.ts`
- Modify: `tests/live-adapter-checks.mjs`

**Interfaces:**
- Produces: `saveProfile({client, session, offer, projectId?, idempotencyKey})` → `{project, icpVersion}`; `approveProfile({client, session, project, icpVersion, idempotencyKey})`.
- Consumes: `client.ts` (Task 5), `profile.ts` (Task 6), `session.ts`.

- [ ] **Step 1: Write the failing checks**

```js
const writes=await loadModule('services/live/writes.ts');

function liveSession(project=null){return {current:()=>({mode:'live',actor:'a',workspace:'w',project}),token:()=>'tok',identity:()=>'live:a:w:'+(project||'-')};}

await test('saveProfile creates the project then saves a version, in order',async()=>{
  const calls=[];
  const client={request:async({path,method,idempotencyKey,ifMatch,token})=>{
    calls.push({path,method,idempotencyKey,ifMatch,token});
    if(method==='POST'&&path.endsWith('/projects'))return {id:'p1',version:1,active_icp_version_id:null};
    return {id:'i1',number:1,content_hash:'sha256:x'};
  }};
  const offer={company:'Acme',product:'S',value:'V',website:'',markets:'Germany',language:'English',must:'m',nice:'',exclude:'',buyerTypes:['Distributor'],roles:''};
  const out=await writes.saveProfile({client,session:liveSession(),offer,idempotencyKey:'k0000001'});
  assert.deepEqual(calls.map(c=>c.method),['POST','POST']);
  assert.ok(calls[1].path.endsWith('/projects/p1/icp-versions'));
  assert.equal(calls[0].token,'tok');// the session token reaches the client
  assert.equal(out.project.id,'p1');
  assert.equal(out.icpVersion.id,'i1');
});

await test('saveProfile selects an already-selected project instead of creating one',async()=>{
  const calls=[];
  const client={request:async({path,method})=>{calls.push({path,method});return {id:'i2',number:2,content_hash:'sha256:y'};}};
  await writes.saveProfile({client,session:liveSession('p9'),offer:{company:'Acme',product:'S',value:'V',markets:'Germany',language:'English',must:'m',buyerTypes:['Distributor']},idempotencyKey:'k0000002'});
  assert.deepEqual(calls.map(c=>c.method),['POST']);
  assert.ok(calls[0].path.endsWith('/projects/p9/icp-versions'));
});

await test('approveProfile sends the version number as If-Match and the hash',async()=>{
  let seen;
  const client={request:async(args)=>{seen=args;return {id:'i1',status:'approved'};}};
  await writes.approveProfile({client,session:liveSession('p'),project:{id:'p'},icpVersion:{id:'i1',number:3,content_hash:'sha256:z'},idempotencyKey:'k0000003'});
  assert.equal(seen.path,'/v1/workspaces/w/icp-versions/i1/approve');
  assert.equal(seen.ifMatch,'"3"');
  assert.deepEqual(seen.body,{content_hash:'sha256:z',confirmation:true});
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `node tests/live-adapter-checks.mjs`
Expected: FAIL — `Cannot find module services/live/writes.ts`.

- [ ] **Step 3: Implement**

```ts
// services/live/writes.ts
/** Sequence the project/profile write calls. No UI, no storage, no demo data. */
import {toIcpSaveRequest, toProjectCreate, type Offerish} from './profile';
import type {LiveClient} from './client';
import type {SessionScope} from './session';

interface Deps {
  client: Pick<LiveClient, 'request'>;
  session: Pick<SessionScope, 'current' | 'token' | 'identity'>;
  idempotencyKey: string;
}

export async function saveProfile(input: Deps & {offer: Offerish; projectId?: string}) {
  const {client, session, offer, idempotencyKey} = input;
  const current = session.current();
  const workspace = current.workspace;
  const token = session.token();
  // "Create or select": the caller may name a project, else the session's selected project is used,
  // and only when neither exists is a project created.
  let projectId = input.projectId ?? current.project ?? undefined;
  let project: {id: string} | undefined = projectId ? {id: projectId} : undefined;
  if (!projectId) {
    project = await client.request({
      path: `/v1/workspaces/${workspace}/projects`, method: 'POST', scope: session.identity(),
      token, body: toProjectCreate(offer), idempotencyKey,
    });
    projectId = (project as {id: string}).id;
  }
  const icpVersion = await client.request({
    path: `/v1/workspaces/${workspace}/projects/${projectId}/icp-versions`, method: 'POST', scope: session.identity(),
    token, body: toIcpSaveRequest(offer), idempotencyKey,
  });
  return {project, icpVersion};
}

export async function approveProfile(input: Deps & {project: {id: string}; icpVersion: {id: string; number: number; content_hash: string}}) {
  const {client, session, icpVersion, idempotencyKey} = input;
  const workspace = session.current().workspace;
  return client.request({
    path: `/v1/workspaces/${workspace}/icp-versions/${icpVersion.id}/approve`, method: 'POST', scope: session.identity(),
    token: session.token(), idempotencyKey, ifMatch: `"${icpVersion.number}"`,
    body: {content_hash: icpVersion.content_hash, confirmation: true},
  });
}
```

The token is read from the session (`session.token()`), not baked into the client at construction: the client stays a transport, and a signed-out session sends no `Authorization` header rather than a stale one.

- [ ] **Step 4: Run to verify it passes**

Run: `node tests/live-adapter-checks.mjs` → previous count plus 3.

- [ ] **Step 5: Commit**

```bash
git add services/live/writes.ts tests/live-adapter-checks.mjs
git commit -m "feat(live): project and profile write orchestration"
```

---

### Task 8: Live UI wiring

**Files:**
- Create: `features/live/offer-wizard.tsx`
- Create: `features/live/profile.tsx`
- Modify: `features/workspace.tsx`

**Interfaces:**
- Consumes: `saveProfile`/`approveProfile` (Task 7), `useWorkspaceSession` (P11), the existing `Wizard`.
- Produces: the wizard and a profile panel render in live mode.

This task is UI-only, so it is verified by `tsc`, `eslint` and `pnpm build` rather than by the node harness (a `.tsx` cannot be loaded there — recorded in P11).

- [ ] **Step 1: Implement the two live components**

```tsx
// features/live/offer-wizard.tsx
'use client';
import {useState} from 'react';
import {Wizard, type Offer} from '@/features/discovery/wizard';
import {useWorkspaceSession} from '@/features/providers/workspace-session';
import {saveProfile} from '@/services/live/writes';

export function LiveOfferWizard({offer, setOffer, onSaved, t}: {
  offer: Offer; setOffer: (o: Offer) => void; onSaved: (info: {projectId: string; icpVersionId: string}) => void;
  t: (s: string) => string;
}) {
  const {session, client} = useWorkspaceSession();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function save() {
    setBusy(true);
    setError('');
    try {
      // A fresh key per user action, >= 8 chars per the contract.
      const key = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
      const out = await saveProfile({client, session, offer, idempotencyKey: key});
      onSaved({projectId: out.project.id, icpVersionId: out.icpVersion.id});
    } catch (err) {
      // A ProfileError names the offending value; a LiveError carries the API code. Neither is
      // swallowed and neither falls back to demo data.
      const failure = err as {message?: string; code?: string};
      setError(failure.message || failure.code || 'Save failed');
    } finally {
      setBusy(false);
    }
  }
  return (
    <div>
      {error ? <p role="alert">{error}</p> : null}
      {busy ? <p role="status">Saving profile...</p> : null}
      <Wizard offer={offer} setOffer={setOffer} run={() => {}} save={save} t={t} />
    </div>
  );
}
```

The wrapper owns its error and busy state because the existing `Wizard` exposes neither; the wizard's own field validation is unchanged, and the API failure is rendered beside it rather than thrown past the component.

```tsx
// features/live/profile.tsx
'use client';
export function LiveProfile({project, icpVersion, onApprove, busy, error}: {
  project: {name: string; version: number; active_icp_version_id: string | null} | null;
  icpVersion: {id: string; number: number; status: string} | null;
  onApprove: () => void; busy: boolean; error?: string;
}) {
  if (!project) return <section className="panel" role="status"><p>No project yet. Save a profile to create one.</p></section>;
  return (
    <section className="panel" role="status">
      <h3>{project.name}</h3>
      <p>Project version {project.version}</p>
      {icpVersion ? <p>Profile v{icpVersion.number} - {icpVersion.status}</p> : <p>No saved profile yet.</p>}
      <button onClick={onApprove} disabled={busy || !icpVersion || icpVersion.status === 'approved'}>Approve profile</button>
      {error ? <p role="alert">{error}</p> : null}
    </section>
  );
}
```

- [ ] **Step 2: Wire the live branch in `features/workspace.tsx`**

The live branch currently renders `LiveOverview` for the overview route and `LiveUnavailable` elsewhere. Extend it, keeping the demo branch byte-identical:

- import `LiveOfferWizard` and `LiveProfilePanel` (the panel is a self-contained container that re-reads the session).
- when `mode === 'live'` and `isWizard`, render `LiveOfferWizard` with the existing `offer`/`OfferSet` and `t`; its `save` selects the saved project with `session.next({project})` and routes to `/app` so the profile panel can load it.
- when `mode === 'live'` and `isOverview`, render `LiveProfilePanel` above `LiveOverview`; the panel fetches `GET /v1/workspaces/{workspace}/projects/{project}` and its `/icp-versions` in a `useEffect` (with the same abort/staleness discipline as `LiveOverview`), and approve calls `approveProfile` then re-fetches.
- **Recorded deviation from this plan's literal text:** P11's `availabilityFor(mode, 'discovery')` is `unavailable` in live mode, so gating the wizard on `availabilityFor(mode, 'discovery')` would make `LiveOfferWizard` dead code — contradicting this task's own goal. The implementer made the gate route-aware (`availabilityFor(mode, isOverview || isWizard ? 'overview' : 'discovery')`), so the wizard and overview are `available` while lists/outreach/results/settings stay `LiveUnavailable`. `services/live/mode.ts` and its P11 checks are unchanged.

- [ ] **Step 3: Copy**

The live components use literal English copy, matching `LiveOverview`/`LiveUnavailable` (P11) — the shell's `t` is not threaded into them. `locales/index.ts` is not modified this phase.

- [ ] **Step 4: Verify**

Run: `node tests/live-adapter-checks.mjs` → unchanged count (this task adds no checks).
Run: `node tests/domain-checks.mjs` → `11 domain checks passed`.
Run: `npx tsc -p tsconfig.json` → clean.
Run: `npx eslint features/live/offer-wizard.tsx features/live/profile.tsx features/workspace.tsx` → no NEW findings (the pre-existing `workspace.tsx` errors are known and must not grow).
Run: `pnpm build` → clean.

- [ ] **Step 5: Commit**

```bash
git add features/live/offer-wizard.tsx features/live/profile.tsx features/workspace.tsx
git commit -m "feat(live): render the offer wizard and profile panel in live mode"
```

---

## Self-Review

- **Spec coverage:** §A boundaries (Tasks 1-8 create exactly the named units); §B data model/versioning/immutability (Tasks 1, 3, 4); §C validation/errors/response/contract bookkeeping (Tasks 2, 3); §D client + mapper + orchestration (Tasks 5, 6, 7); §E testing and acceptance mapping (Tasks 1-7 backend tests and checks; Task 8 is UI, build-verified); §F out of scope (no task, by design). Every section maps to a task.
- **Acceptance mapping:** TEST-BO-007-01 → the cross-tenant/foreign `404` tests plus the fact that the profile is fetched (Task 2/4 tests); TEST-BO-007-02 → `test_a_material_change_supersedes_and_reopens_the_profile` (Task 4); TEST-BO-007-03 → `test_a_stale_if_match_is_rejected` (Task 3); TEST-BO-007-04 → the role/foreign-version tests (Tasks 3, 4). The deferred halves are recorded in the spec, not asserted here.
- **Placeholder scan:** no `TBD`/`TODO`; every code step contains complete code. Task 8's UI is described rather than fully specified line-by-line because `workspace.tsx` is 47 KB and the edit must be surgical; the implementer's brief names the exact anchors, and the task is build/lint-verified rather than check-verified.
- **Type consistency:** `ProjectCreate`/`ProjectUpdate`/`ArchiveRequest` (Task 2) are the route payload types used in Tasks 2 and 3. `_project_data` is the single response shaper. `begin_idempotency`/`complete_idempotency`/`if_match_version` (Task 2's `idempotency.py`) are consumed by all three mutations (create in Task 2, update/archive in Task 3). `resolveMarkets`/`resolveLanguages`/`toProjectCreate`/`toIcpSaveRequest`/`ProfileError` (Task 6) are consumed by Task 7. `saveProfile`/`approveProfile` (Task 7) are consumed by Task 8.
- **Contract alignment (corrections applied at review):** `createProject` is idempotent and replays (contract `x-idempotency: Required`); `Idempotency-Key` is length-checked 8..200; `archiveProject` takes the contract's required `ArchiveRequest.reason`; `website` is validated as a URI; `offer` carries the contract's `maxLength: 20000` with no invented minimum. Test-fixed: the `_project_data` stub in `test_api_routes_contract.py` and `_Icp.superseded_at` are widened with the response shapes, and the DB fixture tears down `idempotency_records`/`icp_versions` in FK order.
- **Known limitation carried forward:** the `ICPSaveRequest` body is still read as an ad-hoc dict in `icp.py`; tightening it is a follow-up, and Task 4 does not change that.
- **Final whole-branch review fixes (applied, commits 48dc810/bca502d):** `archiveProject` added to the `OPERATION_ROLES`/`CONTRACT_ROLES` maps (behavior unchanged); `begin_idempotency` inserts under a savepoint and converts a concurrent unique-key `IntegrityError` into a replay or `409` instead of a `500`; approving a new version now supersedes the previously active one; the wizard reuses one `Idempotency-Key` per save action. Acceptance tests were added for a foreign-workspace approve `404`, material-change approval retention plus a later `saved` version, and foreign project PATCH/DELETE `404`.

## Global Notes

- No remote commits/pushes, deploys, cloud resources, real-data migrations, provider calls, or sends.
- Record exact command output in `PROGRESS.md`; every unexecuted check is **NOT RUN**. A DB test that skips is NOT RUN, not a pass.
- Execution requires a recorded dependency waiver and may use `superpowers:subagent-driven-development` or `superpowers:executing-plans`.
