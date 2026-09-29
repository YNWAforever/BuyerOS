# P13 Durable Buyer Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **Build is NOT authorized by this document**; execution requires explicit approval under a dependency waiver.

**Goal:** Freeze a bounded filtered buyer selection into a server-owned snapshot, read it back paged, and persist human review and notes/owner against the exact frozen versions.

**Architecture:** Seven contract operations land on the existing P2 tables. `createBuyerSnapshot` materialises ordered `(buyer_id, version)` rows; `listBuyers`/`getBuyer` read them with a wider contract subset; `updateBuyer` is idempotent with a strong `If-Match`; `reviewBuyers` appends immutable `human_reviews` with per-item version conflicts; two evidence reads round it out. One migration adds `project_buyers.version` and an idempotency response store; the live client gains buyer/evidence mappers plus live buyer table/drawer components.

**Tech Stack:** Python 3.12+ (installed 3.14.6), FastAPI, Pydantic v2, SQLAlchemy 2 + psycopg, Alembic, pytest + httpx TestClient, uv; TypeScript/React 19 + Next 16, Node 24 for the checks. **No new dependency.**

## Global Constraints

- Spec: `docs/buyeros/specs/2026-09-19-p13-buyer-review-design.md`. Contract: `docs/buyeros/contracts/openapi.proposed.yaml` (authoritative). Task: `docs/buyeros/tasks/BO-008-...md`.
- Branch `p13-buyer-review` from `p12-project-profile-writes` @ `91ba848` (it extends the P12 write surface; it does not build off `main`).
- Plan-only artifact: no remote commits/pushes, deploys, cloud resources, real-data migrations, paid calls, mailboxes, or sends.
- Fail closed: unconfigured auth returns `401`. Roles come from Postgres membership only.
- Contract-first: every implemented route matches the contract's `operationId`, method, path and schema names, and every emitted response key must be contract-declared.
- Request bodies are strict Pydantic v2 models (`extra="forbid"`). `BuyerUpdate` rejects an explicit `null` note but accepts an explicit `null` owner (clearing it); an empty body is `422`.
- `Idempotency-Key` is required on `createBuyerSnapshot`, `updateBuyer` and `reviewBuyers`; it is 8..200 characters; the same key with a different body is `409 IDEMPOTENCY_CONFLICT`; the same key with the same body replays (returning the recorded snapshot, the current buyer, or the stored `BulkResult`).
- `project_buyers.version` is the strong ETag for `updateBuyer`; `If-Match` must equal it, else `412 STALE_REVISION`; missing/malformed `If-Match` is `400 INVALID_REQUEST`. `reviewBuyers` compares each item's expected version (`Selection` or `BuyerSnapshotItem.buyer_version`) and reports a per-item `conflict` without modifying that buyer.
- ICP versions and `human_reviews` are append-only. A review never edits or deletes a prior row.
- Snapshots are immutable: order and membership never expand after creation; `expires_at = now + 15 minutes`; a missing or expired snapshot is `404`.
- A non-empty deferred filter (`markets`, `buyer_types`, `contact`, `suppressed`, `run_id`, `list_id`) is `422 INVALID_REQUEST` naming the field; a filter is never silently dropped.
- Cross-tenant and absent project/buyer/snapshot/evidence all return a non-enumerating `404 NOT_FOUND`.
- The frontend never fabricates or falls back to demo data; live failures surface as `LiveError`/`MapError`.
- Every task also runs the plan's type check and lint on changed files:
  `npx tsc --noEmit --strict --module esnext --moduleResolution bundler --target ES2022 <changed .ts/.tsx files>` and `npx eslint <changed files>`.
- Every unexecuted check is **NOT RUN**. A DB test that skips is NOT RUN, not a pass.

**Existing interfaces this plan consumes (already implemented):**
- `buyeros_api.api.deps`: `get_engine`, `tenant_scoped`, `load_membership`, `permission_for_roles` (second argument is the contract operation id).
- `buyeros_api.api.errors`: `ApiError`, `envelope`; `buyeros_api.api.auth`: `Principal`, `get_principal`.
- `buyeros_api.api.idempotency`: `begin_idempotency`, `complete_idempotency`, `if_match_version`.
- `buyeros_api.db.icp.canonical_hash`.
- `buyeros_api.db.buyers`: `Company`, `ProjectBuyer`, `SourceDocument`, `Evidence`, `FitAssessment`, `HumanReview`, `BuyerSnapshot`, `BuyerSnapshotItem`.
- `tests/conftest.py`: `pg_dsn`, `migrated`, `seeded`, `runtime_role_dsn`; `tests/auth_fixtures.py`: `ISSUER`, `AUDIENCE`, `jwks_document()`, `make_token()`.
- `tests/conftest.py`'s `seeded` fixture creates workspace A (`11111111-1111-4111-8111-111111111111`) with `ProjectA` (`a0000000-0000-4000-8000-000000000001`) and workspace B (`22222222-2222-4222-8222-222222222222`) with `ProjectB` (`b0000000-0000-4000-8000-000000000002`).

---

### Task 1: Migration, buyer version and idempotency response store

**Files:**
- Create: `services/api/alembic/versions/0011_project_buyer_version.py`
- Modify: `services/api/buyeros_api/db/buyers.py`
- Modify: `services/api/buyeros_api/db/contact.py`
- Modify: `services/api/buyeros_api/api/idempotency.py`
- Create: `services/api/tests/test_buyer_review_db.py`

**Interfaces:**
- Produces: `ProjectBuyer.version`; `IdempotencyRecord.response`; `IdempotencyOutcome(record, replay, response)`; `complete_idempotency(outcome, resource_id, response=None)`.
- Consumes: `Base`, `TenantMixin`, `JSONB`.

- [ ] **Step 1: Write the failing tests**

```python
# services/api/tests/test_buyer_review_db.py
"""BO-008 slice 1: buyer version, snapshots, reviews and evidence."""
import asyncio
import uuid

import psycopg
import pytest
from fastapi.testclient import TestClient

from buyeros_api.api import auth
from buyeros_api.api.app import create_app
from buyeros_api.api.jwks import JwksKeyCache
from buyeros_api.api.verifier import TokenVerifier
from tests import auth_fixtures as fx
from tests.conftest import runtime_role_dsn

WORKSPACE_A = "11111111-1111-4111-8111-111111111111"
WORKSPACE_B = "22222222-2222-4222-8222-222222222222"
PROJECT_A = "a0000000-0000-4000-8000-000000000001"
PROJECT_B = "b0000000-0000-4000-8000-000000000002"
OPERATOR = "auth0|operator-a"
REVIEWER = "auth0|reviewer-a"
ADMIN = "auth0|admin-a"


def test_buyer_version_and_idempotency_response_columns_exist(migrated):
    with psycopg.connect(migrated) as conn:
        columns = {
            (r[0], r[1], r[2])
            for r in conn.execute(
                "SELECT table_name, column_name, is_nullable FROM information_schema.columns "
                "WHERE (table_name = 'project_buyers' AND column_name = 'version') "
                "OR (table_name = 'idempotency_records' AND column_name = 'response')"
            ).fetchall()
        }
    assert columns == {("project_buyers", "version", "NO"), ("idempotency_records", "response", "YES")}


def test_a_raw_project_buyer_insert_defaults_to_version_one(seeded):
    company_id = str(uuid.uuid4())
    buyer_id = str(uuid.uuid4())
    with psycopg.connect(seeded, autocommit=True) as conn:
        conn.execute(
            "INSERT INTO companies(id, workspace_id, legal_name, display_name) VALUES (%s, %s, 'C', 'C Co')",
            (company_id, WORKSPACE_A),
        )
        conn.execute(
            "INSERT INTO project_buyers(id, workspace_id, project_id, company_id) VALUES (%s, %s, %s, %s)",
            (buyer_id, WORKSPACE_A, PROJECT_A, company_id),
        )
        version = conn.execute("SELECT version FROM project_buyers WHERE id = %s", (buyer_id,)).fetchone()[0]
        conn.execute("DELETE FROM project_buyers WHERE id = %s", (buyer_id,))
        conn.execute("DELETE FROM companies WHERE id = %s", (company_id,))
    assert version == 1
```

- [ ] **Step 2: Run to verify they fail**

Run (cwd `services/api`): `uv run pytest tests/test_buyer_review_db.py -v`
Expected: FAIL - the `version` and `response` columns do not exist (or the DB is skipped; see the note below).

**Note:** these tests are DB-backed and skip cleanly without Docker, exactly like the existing `*_db.py` tests. A skipped run is **NOT RUN**, not a pass - report the skip count.

- [ ] **Step 3: Write the migration and the model columns**

```python
# services/api/alembic/versions/0011_project_buyer_version.py
"""buyer version and idempotency response storage

Revision ID: 0011_project_buyer_version
Revises: 0010_widen_idempotency_key
Create Date: 2026-09-19

`project_buyers.version` is the buyer's optimistic-concurrency token (If-Match on updateBuyer and each
Selection item). It keeps a server default so a raw insert still starts at 1.

`idempotency_records.response` stores a committed bulk result so a same-key/same-body replay returns the
original response, which a single `resource_id` cannot express for a bulk operation.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011_project_buyer_version"
down_revision: str | None = "0010_widen_idempotency_key"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("project_buyers", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("idempotency_records", sa.Column("response", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("idempotency_records", "response")
    op.drop_column("project_buyers", "version")
```

In `services/api/buyeros_api/db/buyers.py`, add to `ProjectBuyer` (the file already imports `Integer`):

```python
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
```

In `services/api/buyeros_api/db/contact.py`, add to `IdempotencyRecord` (the file already imports `JSONB`):

```python
    response: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
```

In `services/api/buyeros_api/api/idempotency.py`, carry the stored response through the outcome:

```python
@dataclass
class IdempotencyOutcome:
    """The record for this (workspace, actor, operation, key) and whether it is a replay."""

    record: object
    replay: bool
    response: dict | None = None
```

In `begin_idempotency`, return the stored response on a replay (replace the final replay return):

```python
    return IdempotencyOutcome(existing, replay=True, response=existing.response)
```

Change `complete_idempotency` to optionally store a response:

```python
def complete_idempotency(outcome: IdempotencyOutcome, resource_id: str, response: dict | None = None) -> None:
    """Mark this transaction's record complete, so a later replay can return its resource/response."""
    outcome.record.status = "completed"
    outcome.record.resource_id = resource_id
    if response is not None:
        outcome.record.response = response
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_buyer_review_db.py -v`
Expected: PASS (2 passed) with Docker available; otherwise report the skips as NOT RUN.
Also run `uv run pytest tests/ -q` - no regression (P12's callers pass no response and keep re-reading).

- [ ] **Step 5: Commit**

```bash
git add services/api/alembic/versions/0011_project_buyer_version.py services/api/buyeros_api/db/buyers.py services/api/buyeros_api/db/contact.py services/api/buyeros_api/api/idempotency.py services/api/tests/test_buyer_review_db.py
git commit -m "feat(api): add buyer version and idempotency response storage"
```

---

### Task 2: Strict request schemas and the buyer/evidence response shapers

**Files:**
- Modify: `services/api/buyeros_api/api/schemas.py`
- Create: `services/api/buyeros_api/services/buyer_view.py`
- Modify: `services/api/tests/test_api_routes_contract.py`
- Modify: `services/api/tests/test_buyer_review_db.py`

**Interfaces:**
- Produces: `SnapshotCreate`, `BuyerFilters`, `VersionedId`, `ExplicitSelection`, `SnapshotSelection`, `Selection`, `ReviewRequest`, `BuyerUpdate`; `buyer_view.buyer_data`, `fit_data`, `review_data`, `snapshot_data`, `evidence_data`.
- Consumes: `_Strict`, `ProjectBuyer`, `Company`, `FitAssessment`, `HumanReview`, `Evidence`, `SourceDocument`.

- [ ] **Step 1: Write the failing tests**

Append to `services/api/tests/test_buyer_review_db.py`:

```python
def test_buyer_update_rejects_an_empty_body_and_a_null_note():
    from pydantic import ValidationError

    from buyeros_api.api.schemas import BuyerUpdate

    with pytest.raises(ValidationError):
        BuyerUpdate.model_validate({})
    with pytest.raises(ValidationError):
        BuyerUpdate.model_validate({"note": None})
    # an explicit null owner is allowed (it clears the owner)
    assert BuyerUpdate.model_validate({"owner_membership_id": None}).owner_membership_id is None


def test_snapshot_create_rejects_unknown_keys_and_bounds():
    from pydantic import ValidationError

    from buyeros_api.api.schemas import SnapshotCreate

    base = {"filters": {}, "sort": "best_fit", "requested_limit": 10}
    assert SnapshotCreate.model_validate(base).requested_limit == 10
    for bad in (
        {**base, "extra": 1},
        {**base, "sort": "newest"},
        {**base, "requested_limit": 0},
        {**base, "requested_limit": 1001},
    ):
        with pytest.raises(ValidationError):
            SnapshotCreate.model_validate(bad)


def test_review_request_discriminates_the_selection_kind():
    from pydantic import ValidationError

    from buyeros_api.api.schemas import ReviewRequest

    explicit = {
        "selection": {"kind": "explicit", "buyers": [{"id": str(uuid.uuid4()), "version": 2}]},
        "status": "accepted",
        "reason": "reviewed",
    }
    assert ReviewRequest.model_validate(explicit).status == "accepted"
    for bad in (
        {**explicit, "status": "approved"},
        {**explicit, "reason": "no"},
        {"selection": {"kind": "other"}, "status": "accepted", "reason": "reviewed"},
    ):
        with pytest.raises(ValidationError):
            ReviewRequest.model_validate(bad)
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_buyer_review_db.py -v -k "rejects_an_empty or snapshot_create or discriminates"`
Expected: FAIL - `ImportError: cannot import name 'BuyerUpdate'`.

- [ ] **Step 3: Write the schemas and shapers**

Add to the imports at the top of `services/api/buyeros_api/api/schemas.py`:

```python
from typing import Annotated, Literal, Union

from pydantic import model_validator
```

Append to `services/api/buyeros_api/api/schemas.py` (reuse `_Strict` and `Field`):

```python
class BuyerFilters(_Strict):
    """Contract `BuyerFilters`. All optional; the route rejects a deferred non-empty filter."""

    q: str | None = Field(default=None, max_length=200)
    markets: list[str] | None = None
    buyer_types: list[str] | None = None
    fit: list[str] | None = None
    review: list[str] | None = None
    contact: list[str] | None = None
    suppressed: bool | None = None
    source_types: list[str] | None = None
    evidence_retrieved_after: str | None = None
    run_id: str | None = None
    list_id: str | None = None
    owner_membership_id: str | None = None


class SnapshotCreate(_Strict):
    filters: BuyerFilters = Field(default_factory=BuyerFilters)
    sort: Literal["best_fit", "name_asc"]
    requested_limit: int = Field(ge=1, le=1000)


class VersionedId(_Strict):
    id: str
    version: int = Field(ge=1)


class ExplicitSelection(_Strict):
    kind: Literal["explicit"]
    buyers: list[VersionedId] = Field(min_length=1, max_length=1000)


class SnapshotSelection(_Strict):
    kind: Literal["snapshot"]
    snapshot_id: str
    excluded_ids: list[str] = Field(default_factory=list, max_length=1000)


Selection = Annotated[Union[ExplicitSelection, SnapshotSelection], Field(discriminator="kind")]


class ReviewRequest(_Strict):
    selection: Selection
    status: Literal["accepted", "rejected", "needs_information"]
    reason: str = Field(min_length=3, max_length=2000)


class BuyerUpdate(_Strict):
    note: str | None = Field(default=None, max_length=4000)
    owner_membership_id: str | None = None

    @model_validator(mode="after")
    def _required_patch(self) -> "BuyerUpdate":
        if not self.model_fields_set:
            raise ValueError("at least one field is required")
        if "note" in self.model_fields_set and self.note is None:
            raise ValueError("note must not be null")
        return self
```

Create `services/api/buyeros_api/services/buyer_view.py`:

```python
"""Contract-shaped Buyer, FitAssessment, HumanReview, Evidence and snapshot subsets (BO-008)."""


def fit_data(fit) -> dict:
    return {
        "id": str(fit.id),
        "icp_version_id": str(fit.icp_version_id),
        "assessment_version": 1,
        "verdict": fit.verdict,
        "rationale": fit.rationale,
        "supported_requirement_ids": [],
        "contradictory_evidence_ids": [],
        "evidence_refs": [],
        "unknowns": [],
        "next_action": "human_review",
        "freshness": "current",
        "evidence_set_hash": fit.evidence_set_hash,
        "prompt_version": "unversioned",
        "model_route_version": "unversioned",
    }


def review_data(review, icp_version_id) -> dict:
    data = {
        "id": str(review.id),
        "status": review.state,
        "reason": review.reason or "",
        "actor_id": str(review.actor_user_id),
        "at": review.created_at.isoformat(),
    }
    if review.fit_assessment_id is not None:
        data["assessment_id"] = str(review.fit_assessment_id)
    if icp_version_id is not None:
        data["icp_version_id"] = str(icp_version_id)
    return data


def evidence_data(evidence, source) -> dict:
    data = {
        "id": str(evidence.id),
        "workspace_id": str(evidence.workspace_id),
        "project_id": str(evidence.project_id),
        "company_id": str(evidence.company_id),
        "source_document_id": str(evidence.source_document_id) if evidence.source_document_id else None,
        "version": 1,
        "excerpt": evidence.excerpt,
        "kind": "inference" if evidence.is_inference else "observation",
        "relationship": evidence.stance,
        "status": "available",
        "data_mode": "live",
    }
    if source is not None:
        data["source_url"] = source.canonical_url
        data["retrieved_at"] = source.retrieved_at.isoformat() if source.retrieved_at else None
        if source.language:
            data["original_language"] = source.language
    if evidence.requirement_id:
        data["requirement_id"] = evidence.requirement_id
    if evidence.translation:
        data["translated_excerpt"] = evidence.translation
    return data


def snapshot_data(snapshot, *, sort: str, total: int, result_limit_reached: bool) -> dict:
    return {
        "id": str(snapshot.id),
        "workspace_id": str(snapshot.workspace_id),
        "project_id": str(snapshot.project_id),
        "actor_id": str(snapshot.actor_user_id),
        "filters_hash": snapshot.filter_hash,
        "sort": sort,
        "total": total,
        "created_at": snapshot.created_at.isoformat(),
        "expires_at": snapshot.expires_at.isoformat() if snapshot.expires_at else None,
        "snapshot_version": 1,
        "result_limit_reached": result_limit_reached,
    }


def buyer_data(buyer, company, *, fit=None, review=None, owner_membership_id=None, evidence_count=0) -> dict:
    data = {
        "id": str(buyer.id),
        "workspace_id": str(buyer.workspace_id),
        "version": buyer.version,
        "created_at": buyer.created_at.isoformat(),
        "updated_at": buyer.updated_at.isoformat(),
        "data_mode": "live",
        "project_id": str(buyer.project_id),
        "company_id": str(buyer.company_id),
        "name": company.display_name,
        "contact_research_status": "not_researched",
        "suppressed": False,
        "owner_membership_id": str(owner_membership_id) if owner_membership_id else None,
        "note": buyer.note,
        "evidence_count": evidence_count,
    }
    if company.domain:
        data["normalized_domain"] = company.domain
    if fit is not None:
        data["fit"] = fit_data(fit)
    if review is not None:
        icp_version_id = fit.icp_version_id if fit is not None else None
        data["review"] = review_data(review, icp_version_id)
    return data
```

In `services/api/tests/test_api_routes_contract.py`: change the import to
`from buyeros_api.services.buyer_view import buyer_data`, extend the `_Buyer` stub with
`version = 1`, `created_at = updated_at = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)`
and `owner_user_id = None`, give `_Company` a `domain = None`, then assert
`set(buyer_data(_Buyer(), _Company())) <= buyer_keys`. (The file already imports `datetime` and defines `_Company`.)

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_buyer_review_db.py tests/test_api_routes_contract.py -v`
Expected: PASS with Docker; report skips as NOT RUN.

- [ ] **Step 5: Commit**

```bash
git add services/api/buyeros_api/api/schemas.py services/api/buyeros_api/services/buyer_view.py services/api/tests/test_api_routes_contract.py services/api/tests/test_buyer_review_db.py
git commit -m "feat(api): strict buyer schemas and contract response shapers"
```

---

### Task 3: Snapshot materialization and createBuyerSnapshot

**Files:**
- Create: `services/api/buyeros_api/services/buyer_selection.py`
- Modify: `services/api/buyeros_api/api/routes/buyers.py`
- Modify: `services/api/buyeros_api/api/unimplemented.py`
- Modify: `services/api/tests/test_api_buyers.py`
- Modify: `services/api/tests/test_buyer_review_db.py`

**Interfaces:**
- Produces: `reject_unsupported_filters(filters: dict) -> None`; `filters_hash(filters: dict, sort: str) -> str`; `async def materialize(session, *, workspace_id, project_id, filters, sort, limit) -> tuple[list[tuple[uuid.UUID, int]], int, bool]`; `create_buyer_snapshot` route.
- Consumes: `SnapshotCreate`, `snapshot_data`, `begin_idempotency`/`complete_idempotency`, `canonical_hash`, `Company`, `ProjectBuyer`, `FitAssessment`, `HumanReview`, `Evidence`, `SourceDocument`, `BuyerSnapshot`, `BuyerSnapshotItem`.

- [ ] **Step 1: Write the failing test**

Append to `services/api/tests/test_buyer_review_db.py`. The `api` fixture seeds the operator, reviewer and
admin members and tears the buyer tables down in FK-safe order (`human_reviews`, `fit_assessments`,
`buyer_snapshot_items`, `buyer_snapshots`, `project_buyers`, `evidence`, `source_documents`, `companies`):

```python
@pytest.fixture
def api(seeded, monkeypatch):
    """An authenticated client on the runtime role with operator, reviewer and admin members."""
    monkeypatch.setenv("BUYEROS_DATABASE_URL", runtime_role_dsn(seeded))
    monkeypatch.setenv("BUYEROS_AUTH0_ISSUER", fx.ISSUER)
    monkeypatch.setenv("BUYEROS_AUTH0_AUDIENCE", fx.AUDIENCE)
    from buyeros_api.settings import get_settings

    get_settings.cache_clear()
    cache = JwksKeyCache(lambda: asyncio.sleep(0, result=fx.jwks_document()), cache_seconds=300)
    monkeypatch.setattr(auth, "_verifier_from_settings", lambda: TokenVerifier(cache, issuer=fx.ISSUER, audience=fx.AUDIENCE))

    owner = psycopg.connect(seeded, autocommit=True)
    for subject, roles in ((OPERATOR, ["operator"]), (REVIEWER, ["reviewer"]), (ADMIN, ["workspace_admin"])):
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
        for subject in (OPERATOR, REVIEWER, ADMIN):
            user_id = uuid.uuid5(uuid.NAMESPACE_URL, subject)
            owner.execute("DELETE FROM memberships WHERE user_id = %s", (user_id,))
            owner.execute("DELETE FROM users WHERE id = %s", (user_id,))
        for statement in (
            "DELETE FROM buyer_snapshot_items WHERE workspace_id = %s",
            "DELETE FROM buyer_snapshots WHERE workspace_id = %s",
            "DELETE FROM human_reviews WHERE workspace_id = %s",
            "DELETE FROM fit_assessments WHERE workspace_id = %s",
            "DELETE FROM list_memberships WHERE workspace_id = %s",
            "DELETE FROM project_buyers WHERE workspace_id = %s",
            "DELETE FROM evidence WHERE workspace_id = %s",
            "DELETE FROM source_documents WHERE workspace_id = %s",
            "DELETE FROM companies WHERE workspace_id = %s",
            "DELETE FROM idempotency_records WHERE workspace_id = %s",
        ):
            owner.execute(statement, (WORKSPACE_A,))
        owner.close()


def _seed_buyer(seeded, *, name, fit=None, review=None, owner_user_id=None, domain=None):
    company_id = str(uuid.uuid4())
    buyer_id = str(uuid.uuid4())
    with psycopg.connect(seeded, autocommit=True) as conn:
        conn.execute(
            "INSERT INTO companies(id, workspace_id, legal_name, display_name, domain) VALUES (%s, %s, %s, %s, %s)",
            (company_id, WORKSPACE_A, name, name, domain),
        )
        conn.execute(
            "INSERT INTO project_buyers(id, workspace_id, project_id, company_id, owner_user_id) "
            "VALUES (%s, %s, %s, %s, %s)",
            (buyer_id, WORKSPACE_A, PROJECT_A, company_id, owner_user_id),
        )
        if fit is not None:
            conn.execute(
                "INSERT INTO fit_assessments(id, workspace_id, project_buyer_id, icp_version_id, evidence_set_hash, "
                "verdict, rationale) VALUES (%s, %s, %s, %s, 'sha256:x', %s, 'because')",
                (str(uuid.uuid4()), WORKSPACE_A, buyer_id, str(uuid.uuid4()), fit),
            )
        if review is not None:
            conn.execute(
                "INSERT INTO human_reviews(id, workspace_id, project_buyer_id, state, actor_user_id) "
                "VALUES (%s, %s, %s, %s, %s)",
                (str(uuid.uuid4()), WORKSPACE_A, buyer_id, review, str(uuid.uuid4())),
            )
    return buyer_id


def _h(subject=OPERATOR, key="snapshot-01", **extra):
    headers = {"Authorization": f"Bearer {fx.make_token(sub=subject)}", "Idempotency-Key": key}
    headers.update(extra)
    return headers


def test_create_snapshot_orders_filters_and_bounds(api, seeded):
    with psycopg.connect(seeded, autocommit=True) as conn:
        conn.execute("DELETE FROM project_buyers WHERE workspace_id = %s", (WORKSPACE_A,))
    _seed_buyer(seeded, name="Zeta Sensors", fit="match")
    _seed_buyer(seeded, name="Alpha Sensors", fit="needs_review")
    _seed_buyer(seeded, name="Mid Sensors", fit="match")
    response = api.post(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/buyer-snapshots",
        json={"filters": {"fit": ["match"]}, "sort": "name_asc", "requested_limit": 1},
        headers=_h(),
    )
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert data["total"] == 1
    assert data["result_limit_reached"] is True
    assert data["sort"] == "name_asc"
    assert data["snapshot_version"] == 1
    assert response.headers.get("ETag") is None


def test_a_deferred_filter_is_rejected_loudly(api):
    response = api.post(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/buyer-snapshots",
        json={"filters": {"markets": ["DE"]}, "sort": "best_fit", "requested_limit": 10},
        headers=_h(key="snapshot-f"),
    )
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_REQUEST"
    assert "markets" in response.json()["message"]


def test_a_snapshot_replays_for_the_same_key_and_body(api):
    body = {"filters": {}, "sort": "best_fit", "requested_limit": 10}
    first = api.post(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/buyer-snapshots",
        json=body, headers=_h(key="snapshot-replay"),
    )
    second = api.post(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/buyer-snapshots",
        json=body, headers=_h(key="snapshot-replay"),
    )
    assert first.status_code == second.status_code == 201
    assert first.json()["data"]["id"] == second.json()["data"]["id"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_buyer_review_db.py -v -k snapshot`
Expected: FAIL - `501 NOT_IMPLEMENTED` (createBuyerSnapshot is in the registry).

- [ ] **Step 3: Implement the selection service and the route**

Create `services/api/buyeros_api/services/buyer_selection.py`:

```python
"""Filter a project's buyers into an ordered, bounded snapshot selection (BO-008)."""

import uuid
from datetime import datetime

from sqlalchemy import select

from ..api.errors import ApiError
from ..db.buyers import Company, Evidence, FitAssessment, HumanReview, ProjectBuyer, SourceDocument

# Filters this phase can source. `source_types` is deferred: neither evidence nor source_documents
# carries a source-type column yet (that lands with P3/BO-014 ingestion).
_SUPPORTED = frozenset({"q", "fit", "review", "owner_membership_id", "evidence_retrieved_after"})
_DEFERRED = ("markets", "buyer_types", "contact", "suppressed", "source_types", "run_id", "list_id")
_FIT_RANK = {"match": 0, "needs_review": 1, "not_a_match": 2}


def reject_unsupported_filters(filters: dict) -> None:
    for name in _DEFERRED:
        value = filters.get(name)
        if value not in (None, [], "", False):
            raise ApiError(422, "INVALID_REQUEST", f"filter not supported in this phase: {name}")


def filters_hash(filters: dict, sort: str) -> str:
    from ..db.icp import canonical_hash

    normalized = {key: value for key, value in sorted(filters.items()) if value not in (None, [], "")}
    return canonical_hash({"filters": normalized, "sort": sort})


async def _latest(session, model, workspace_id, buyer_ids):
    if not buyer_ids:
        return {}
    rows = (
        await session.execute(
            select(model)
            .where(model.workspace_id == workspace_id, model.project_buyer_id.in_(buyer_ids))
            .order_by(model.project_buyer_id, model.created_at.desc(), model.id)
        )
    ).scalars().all()
    latest: dict = {}
    for row in rows:
        latest.setdefault(row.project_buyer_id, row)
    return latest


async def _buyers_with_evidence_after(session, workspace_id, project_id, buyer_ids, retrieved_after):
    if not buyer_ids:
        return set()
    try:
        cutoff = datetime.fromisoformat(retrieved_after)
    except ValueError as exc:
        raise ApiError(422, "INVALID_REQUEST", "evidence_retrieved_after must be an ISO-8601 timestamp") from exc
    rows = (
        await session.execute(
            select(ProjectBuyer.id)
            .join(
                Evidence,
                (Evidence.workspace_id == ProjectBuyer.workspace_id) & (Evidence.company_id == ProjectBuyer.company_id),
            )
            .join(
                SourceDocument,
                (SourceDocument.workspace_id == Evidence.workspace_id)
                & (SourceDocument.id == Evidence.source_document_id),
            )
            .where(
                ProjectBuyer.workspace_id == workspace_id,
                ProjectBuyer.project_id == project_id,
                ProjectBuyer.id.in_(buyer_ids),
                SourceDocument.retrieved_at.is_not(None),
                SourceDocument.retrieved_at >= cutoff,
            )
        )
    ).scalars().all()
    return set(rows)


async def materialize(session, *, workspace_id, project_id, filters: dict, sort: str, limit: int):
    """Return ordered (buyer_id, version) pairs, the matched total, and whether the limit clipped it."""
    reject_unsupported_filters(filters)
    query = (
        select(ProjectBuyer, Company)
        .join(Company, (Company.workspace_id == ProjectBuyer.workspace_id) & (Company.id == ProjectBuyer.company_id))
        .where(ProjectBuyer.workspace_id == workspace_id, ProjectBuyer.project_id == project_id)
    )
    q = filters.get("q")
    if q:
        query = query.where(Company.display_name.ilike(f"%{q}%"))
    owner_membership_id = filters.get("owner_membership_id")
    if owner_membership_id:
        from ..db.models import Membership

        owner_user_id = (
            await session.execute(
                select(Membership.user_id).where(
                    Membership.workspace_id == workspace_id,
                    Membership.id == uuid.UUID(owner_membership_id),
                    Membership.active.is_(True),
                )
            )
        ).scalar_one_or_none()
        if owner_user_id is None:
            raise ApiError(422, "INVALID_REQUEST", "owner_membership_id is not an active member")
        query = query.where(ProjectBuyer.owner_user_id == owner_user_id)

    rows = (await session.execute(query)).all()
    buyer_ids = [buyer.id for buyer, _ in rows]
    fits = await _latest(session, FitAssessment, workspace_id, buyer_ids)
    reviews = await _latest(session, HumanReview, workspace_id, buyer_ids)
    wanted_fit = set(filters.get("fit") or [])
    wanted_review = set(filters.get("review") or [])
    retrieved_after = filters.get("evidence_retrieved_after")
    evidence_ok = (
        await _buyers_with_evidence_after(session, workspace_id, project_id, buyer_ids, retrieved_after)
        if retrieved_after
        else set(buyer_ids)
    )

    selected = []
    for buyer, company in rows:
        fit = fits.get(buyer.id)
        review = reviews.get(buyer.id)
        if wanted_fit and (fit.verdict if fit else None) not in wanted_fit:
            continue
        if wanted_review and (review.state if review else None) not in wanted_review:
            continue
        if buyer.id not in evidence_ok:
            continue
        selected.append((buyer, company, fit))

    if sort == "name_asc":
        selected.sort(key=lambda item: (item[1].display_name, str(item[0].id)))
    else:
        selected.sort(key=lambda item: (_FIT_RANK.get(item[2].verdict if item[2] else None, 3), item[1].display_name, str(item[0].id)))
    matched = len(selected)
    return [(buyer.id, buyer.version) for buyer, _, _ in selected[:limit]], matched, matched > limit
```

In `services/api/buyeros_api/api/routes/buyers.py`, add the route (imports are function-local by convention):

```python
@router.post("/projects/{project_id}/buyer-snapshots", status_code=201)
async def create_buyer_snapshot(
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    payload: SnapshotCreate,
    request: Request,
    response: Response,
    principal: Principal = Depends(get_principal),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import select

    from ...db.buyers import BuyerSnapshot, BuyerSnapshotItem
    from ...db.icp import Project
    from ...services.buyer_selection import filters_hash, materialize
    from ...services.buyer_view import snapshot_data
    from ..deps import load_membership, permission_for_roles, tenant_scoped
    from ..idempotency import begin_idempotency, complete_idempotency

    if not idempotency_key:
        raise ApiError(400, "INVALID_REQUEST", "Idempotency-Key header is required")
    body = payload.model_dump(mode="json")

    async with tenant_scoped(workspace_id) as session:
        membership = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(membership["roles"], "createBuyerSnapshot"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        project = (
            await session.execute(
                select(Project).where(Project.workspace_id == workspace_id, Project.id == project_id)
            )
        ).scalar_one_or_none()
        if project is None:
            raise ApiError(404, "NOT_FOUND", "project not found")
        outcome = await begin_idempotency(
            session, workspace_id=workspace_id, actor_id=membership["user_id"],
            operation_id="createBuyerSnapshot", key=idempotency_key, body=body,
        )
        if outcome.replay and outcome.response is not None:
            return envelope(outcome.response, request.state.request_id)
        ordered, matched, clipped = await materialize(
            session, workspace_id=workspace_id, project_id=project_id,
            filters=body["filters"], sort=body["sort"], limit=body["requested_limit"],
        )
        snapshot = BuyerSnapshot(
            workspace_id=workspace_id, project_id=project_id,
            filter_hash=filters_hash(body["filters"], body["sort"]),
            actor_user_id=membership["user_id"],
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
        )
        session.add(snapshot)
        await session.flush()
        for ordinal, (buyer_id, buyer_version) in enumerate(ordered):
            session.add(
                BuyerSnapshotItem(
                    workspace_id=workspace_id, snapshot_id=snapshot.id,
                    ordinal=ordinal, buyer_id=buyer_id, buyer_version=buyer_version,
                )
            )
        await session.flush()
        data = snapshot_data(snapshot, sort=body["sort"], total=len(ordered), result_limit_reached=clipped)
        complete_idempotency(outcome, str(snapshot.id), response=data)
    return envelope(data, request.state.request_id)
```

Add `from fastapi import APIRouter, Depends, Header, Request, Response` (add `Response` and `Header` if absent)
and `from ..schemas import SnapshotCreate` to `buyers.py`. Also remove
`"createBuyerSnapshot": ("post", "/v1/workspaces/{workspace_id}/projects/{project_id}/buyer-snapshots")` from
`services/api/buyeros_api/api/unimplemented.py` and add `"createBuyerSnapshot"` to the `implemented` set in
`services/api/tests/test_api_buyers.py`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_buyer_review_db.py tests/test_api_buyers.py -v`
Expected: PASS with Docker. The registry test must still assert equality against every non-implemented operation.

- [ ] **Step 5: Commit**

```bash
git add services/api/buyeros_api/services/buyer_selection.py services/api/buyeros_api/api/routes/buyers.py services/api/buyeros_api/api/unimplemented.py services/api/tests/test_api_buyers.py services/api/tests/test_buyer_review_db.py
git commit -m "feat(api): materialize bounded buyer snapshots"
```

---

### Task 4: Wider buyer reads (listBuyers and getBuyer)

**Files:**
- Create: `services/api/buyeros_api/services/buyer_read.py`
- Modify: `services/api/buyeros_api/api/routes/buyers.py`
- Modify: `services/api/tests/test_buyer_review_db.py`

**Interfaces:**
- Produces: `async def view(session, *, workspace_id, buyer, company) -> dict`.
- Consumes: `buyer_data`, `FitAssessment`, `HumanReview`, `Evidence`, `Membership`.

- [ ] **Step 1: Write the failing tests**

Append to `services/api/tests/test_buyer_review_db.py`:

```python
def _snapshot(api, *, limit=10, key="list-01"):
    response = api.post(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/buyer-snapshots",
        json={"filters": {}, "sort": "name_asc", "requested_limit": limit},
        headers=_h(key=key),
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["id"]


def test_list_buyers_pages_the_frozen_snapshot(api, seeded):
    with psycopg.connect(seeded, autocommit=True) as conn:
        conn.execute("DELETE FROM project_buyers WHERE workspace_id = %s", (WORKSPACE_A,))
    first = _seed_buyer(seeded, name="Alpha Sensors", fit="match", review="accepted")
    _seed_buyer(seeded, name="Beta Sensors", fit="needs_review", review="awaiting_review")
    snapshot_id = _snapshot(api)

    response = api.get(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/buyers",
        params={"snapshot_id": snapshot_id, "offset": 0, "limit": 1},
        headers=_h(key="list-read"),
    )
    assert response.status_code == 200, response.text
    page = response.json()["data"]
    assert page["total"] == 2 and page["offset"] == 0 and page["limit"] == 1
    assert len(page["items"]) == 1
    item = page["items"][0]
    assert item["id"] == first
    assert item["version"] == 1
    assert item["fit"]["verdict"] == "match"
    assert item["review"]["status"] == "accepted"
    assert item["evidence_count"] == 0
    assert item["suppressed"] is False

    # a buyer created after the snapshot is not in it
    _seed_buyer(seeded, name="Gamma Sensors", fit="match")
    after = api.get(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/buyers",
        params={"snapshot_id": snapshot_id, "offset": 0, "limit": 10},
        headers=_h(key="list-read-2"),
    )
    assert after.json()["data"]["total"] == 2


def test_a_foreign_or_unknown_snapshot_is_a_404(api):
    response = api.get(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/buyers",
        params={"snapshot_id": str(uuid.uuid4()), "offset": 0, "limit": 10},
        headers=_h(key="list-404"),
    )
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


def test_get_buyer_returns_the_contract_subset_and_404s_foreign(api, seeded):
    buyer_id = _seed_buyer(seeded, name="Alpha Sensors", fit="match")
    own = api.get(f"/v1/workspaces/{WORKSPACE_A}/buyers/{buyer_id}", headers=_h(key="get-01"))
    assert own.status_code == 200, own.text
    assert own.json()["data"]["id"] == buyer_id
    foreign = api.get(f"/v1/workspaces/{WORKSPACE_B}/buyers/{buyer_id}", headers=_h(key="get-02"))
    assert foreign.status_code == 404
    assert "Alpha" not in foreign.text
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_buyer_review_db.py -v -k "pages_the_frozen or foreign_or_unknown or returns_the_contract"`
Expected: FAIL - the page items lack `version`/`fit`/`review` (the P9 shaper emits identity + note only).

- [ ] **Step 3: Implement the read view and widen the routes**

Create `services/api/buyeros_api/services/buyer_read.py`:

```python
"""Load the contract Buyer view for a project buyer (BO-008)."""

from sqlalchemy import func, select

from ..db.buyers import Evidence, FitAssessment, HumanReview
from ..db.models import Membership
from .buyer_view import buyer_data


async def _latest(session, model, workspace_id, buyer_id):
    return (
        await session.execute(
            select(model)
            .where(model.workspace_id == workspace_id, model.project_buyer_id == buyer_id)
            .order_by(model.created_at.desc(), model.id)
        )
    ).scalars().first()


async def view(session, *, workspace_id, buyer, company) -> dict:
    fit = await _latest(session, FitAssessment, workspace_id, buyer.id)
    review = await _latest(session, HumanReview, workspace_id, buyer.id)
    owner_membership_id = None
    if buyer.owner_user_id is not None:
        owner_membership_id = (
            await session.execute(
                select(Membership.id).where(
                    Membership.workspace_id == workspace_id,
                    Membership.user_id == buyer.owner_user_id,
                    Membership.active.is_(True),
                )
            )
        ).scalar_one_or_none()
    evidence_count = (
        await session.execute(
            select(func.count())
            .select_from(Evidence)
            .where(
                Evidence.workspace_id == workspace_id,
                Evidence.project_id == buyer.project_id,
                Evidence.company_id == buyer.company_id,
            )
        )
    ).scalar_one()
    return buyer_data(
        buyer, company, fit=fit, review=review,
        owner_membership_id=owner_membership_id, evidence_count=evidence_count,
    )
```

Rewrite `list_buyers` in `services/api/buyeros_api/api/routes/buyers.py` to page the frozen snapshot and
shape each row with `buyer_read.view`; add `offset: int = 0` and `limit: int = 50` query parameters
(`limit` clamped to `1..100`), reject an expired snapshot with `404`, and replace `_buyer_data(...)` with
`await view(session, workspace_id=workspace_id, buyer=buyer, company=company)`. Then rewrite `get_buyer`
to load its `(ProjectBuyer, Company)` row and return `await view(...)`. Remove the old `_buyer_data`
helper. The `total` is the snapshot item count; `items` is that ordered page sliced by
`offset`/`limit`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_buyer_review_db.py tests/test_api_routes_contract.py tests/test_api_tenant_isolation.py -v`
Expected: PASS with Docker; report skips as NOT RUN.

- [ ] **Step 5: Commit**

```bash
git add services/api/buyeros_api/services/buyer_read.py services/api/buyeros_api/api/routes/buyers.py services/api/tests/test_buyer_review_db.py
git commit -m "feat(api): widen buyer reads to the contract subset"
```

---

### Task 5: updateBuyer - notes and owner under If-Match

**Files:**
- Modify: `services/api/buyeros_api/api/routes/buyers.py`
- Modify: `services/api/buyeros_api/api/unimplemented.py`
- Modify: `services/api/tests/test_api_buyers.py`
- Modify: `services/api/tests/test_buyer_review_db.py`

**Interfaces:**
- Produces: `update_buyer` route.
- Consumes: `BuyerUpdate`, `if_match_version`, `begin_idempotency`/`complete_idempotency`, `buyer_read.view`, `Membership`.

- [ ] **Step 1: Write the failing tests**

Append to `services/api/tests/test_buyer_review_db.py`:

```python
def _admin_membership(seeded, subject=ADMIN):
    user_id = uuid.uuid5(uuid.NAMESPACE_URL, subject)
    with psycopg.connect(seeded, autocommit=True) as conn:
        return str(conn.execute(
            "SELECT id FROM memberships WHERE workspace_id = %s AND user_id = %s",
            (WORKSPACE_A, user_id),
        ).fetchone()[0])


def test_update_buyer_bumps_the_version_and_sets_the_etag(api, seeded):
    buyer_id = _seed_buyer(seeded, name="Alpha Sensors", fit="match")
    response = api.patch(
        f"/v1/workspaces/{WORKSPACE_A}/buyers/{buyer_id}",
        json={"note": "Reviewed scope."},
        headers=_h(key="update-01", **{"If-Match": '"1"'}),
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["note"] == "Reviewed scope."
    assert data["version"] == 2
    assert response.headers["ETag"] == '"2"'


def test_update_buyer_rejects_stale_and_missing_if_match(api, seeded):
    buyer_id = _seed_buyer(seeded, name="Alpha Sensors")
    stale = api.patch(
        f"/v1/workspaces/{WORKSPACE_A}/buyers/{buyer_id}",
        json={"note": "x"},
        headers=_h(key="update-10", **{"If-Match": '"9"'}),
    )
    assert stale.status_code == 412 and stale.json()["code"] == "STALE_REVISION"
    missing = api.patch(
        f"/v1/workspaces/{WORKSPACE_A}/buyers/{buyer_id}",
        json={"note": "x"}, headers=_h(key="update-11"),
    )
    assert missing.status_code == 400


def test_update_buyer_replays_and_validates_the_owner(api, seeded):
    buyer_id = _seed_buyer(seeded, name="Alpha Sensors")
    body = {"owner_membership_id": _admin_membership(seeded)}
    first = api.patch(
        f"/v1/workspaces/{WORKSPACE_A}/buyers/{buyer_id}",
        json=body, headers=_h(key="update-replay", **{"If-Match": '"1"'}),
    )
    assert first.status_code == 200, first.text
    assert first.json()["data"]["owner_membership_id"] == body["owner_membership_id"]
    replay = api.patch(
        f"/v1/workspaces/{WORKSPACE_A}/buyers/{buyer_id}",
        json=body, headers=_h(key="update-replay", **{"If-Match": '"1"'}),
    )
    assert replay.json()["data"]["version"] == 2  # a replay, not a second bump
    bad = api.patch(
        f"/v1/workspaces/{WORKSPACE_A}/buyers/{buyer_id}",
        json={"owner_membership_id": str(uuid.uuid4())},
        headers=_h(key="update-bad-owner", **{"If-Match": '"2"'}),
    )
    assert bad.status_code == 422


def test_update_buyer_404s_a_foreign_buyer_and_conflicts_on_reuse(api, seeded):
    buyer_id = _seed_buyer(seeded, name="Alpha Sensors")
    foreign = api.patch(
        f"/v1/workspaces/{WORKSPACE_B}/buyers/{buyer_id}",
        json={"note": "x"}, headers=_h(key="update-f", **{"If-Match": '"1"'}),
    )
    assert foreign.status_code == 404
    assert api.patch(
        f"/v1/workspaces/{WORKSPACE_A}/buyers/{buyer_id}",
        json={"note": "one"}, headers=_h(key="update-conflict", **{"If-Match": '"1"'}),
    ).status_code == 200
    conflict = api.patch(
        f"/v1/workspaces/{WORKSPACE_A}/buyers/{buyer_id}",
        json={"note": "two"}, headers=_h(key="update-conflict", **{"If-Match": '"2"'}),
    )
    assert conflict.status_code == 409 and conflict.json()["code"] == "IDEMPOTENCY_CONFLICT"
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_buyer_review_db.py -v -k update_buyer`
Expected: FAIL - PATCH answers `501` (it is in the registry).

- [ ] **Step 3: Implement the route**

Add to `services/api/buyeros_api/api/routes/buyers.py`:

```python
@router.patch("/buyers/{buyer_id}")
async def update_buyer(
    workspace_id: uuid.UUID,
    buyer_id: uuid.UUID,
    payload: BuyerUpdate,
    request: Request,
    response: Response,
    principal: Principal = Depends(get_principal),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    if_match: str | None = Header(default=None, alias="If-Match"),
) -> dict:
    from sqlalchemy import select

    from ...db.buyers import Company, ProjectBuyer
    from ...db.models import Membership
    from ...services.buyer_read import view
    from ..deps import load_membership, permission_for_roles, tenant_scoped
    from ..idempotency import begin_idempotency, complete_idempotency, if_match_version

    if not idempotency_key:
        raise ApiError(400, "INVALID_REQUEST", "Idempotency-Key header is required")
    expected_version = if_match_version(if_match)
    body = payload.model_dump(mode="json")

    async with tenant_scoped(workspace_id) as session:
        membership = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(membership["roles"], "updateBuyer"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        outcome = await begin_idempotency(
            session, workspace_id=workspace_id, actor_id=membership["user_id"],
            operation_id="updateBuyer", key=idempotency_key, body=body,
        )
        buyer = (
            await session.execute(
                select(ProjectBuyer)
                .where(ProjectBuyer.workspace_id == workspace_id, ProjectBuyer.id == buyer_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if buyer is None:
            raise ApiError(404, "NOT_FOUND", "buyer not found")
        company = (
            await session.execute(
                select(Company).where(Company.workspace_id == workspace_id, Company.id == buyer.company_id)
            )
        ).scalar_one()
        if outcome.replay:
            response.headers["ETag"] = f'"{buyer.version}"'
            return envelope(await view(session, workspace_id=workspace_id, buyer=buyer, company=company), request.state.request_id)
        if buyer.version != expected_version:
            raise ApiError(412, "STALE_REVISION", "buyer changed; reload it")
        if "owner_membership_id" in payload.model_fields_set:
            if payload.owner_membership_id is None:
                buyer.owner_user_id = None
            else:
                owner = (
                    await session.execute(
                        select(Membership).where(
                            Membership.workspace_id == workspace_id,
                            Membership.id == uuid.UUID(payload.owner_membership_id),
                            Membership.active.is_(True),
                        )
                    )
                ).scalar_one_or_none()
                if owner is None:
                    raise ApiError(422, "INVALID_REQUEST", "owner_membership_id is not an active member")
                buyer.owner_user_id = owner.user_id
        if "note" in payload.model_fields_set:
            buyer.note = payload.note
        buyer.version += 1
        await session.flush()
        await session.refresh(buyer)
        complete_idempotency(outcome, str(buyer.id))
        data = await view(session, workspace_id=workspace_id, buyer=buyer, company=company)
        response.headers["ETag"] = f'"{buyer.version}"'
    return envelope(data, request.state.request_id)
```

Add `BuyerUpdate` to the `..schemas` import. Remove `"updateBuyer"` from
`services/api/buyeros_api/api/unimplemented.py` and add `"updateBuyer"` to the `implemented` set in
`services/api/tests/test_api_buyers.py`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_buyer_review_db.py tests/test_api_buyers.py -v`
Expected: PASS with Docker.

- [ ] **Step 5: Commit**

```bash
git add services/api/buyeros_api/api/routes/buyers.py services/api/buyeros_api/api/unimplemented.py services/api/tests/test_api_buyers.py services/api/tests/test_buyer_review_db.py
git commit -m "feat(api): versioned buyer note and owner updates"
```

---

### Task 6: reviewBuyers - append-only review with per-item conflicts

**Files:**
- Create: `services/api/buyeros_api/services/buyer_review.py`
- Create: `services/api/buyeros_api/api/routes/reviews.py`
- Modify: `services/api/buyeros_api/api/app.py`
- Modify: `services/api/buyeros_api/api/unimplemented.py`
- Modify: `services/api/tests/test_api_buyers.py`
- Modify: `services/api/tests/test_buyer_review_db.py`

**Interfaces:**
- Produces: `async def apply(session, *, workspace_id, project_id, actor_user_id, selection, status, reason) -> dict`; `review_buyers` route (registered on the app).
- Consumes: `ReviewRequest`, `begin_idempotency`/`complete_idempotency`, `BuyerSnapshot`, `BuyerSnapshotItem`, `FitAssessment`, `HumanReview`, `ProjectBuyer`.

- [ ] **Step 1: Write the failing tests**

Append to `services/api/tests/test_buyer_review_db.py`:

```python
def test_review_updates_only_the_explicit_selection(api, seeded):
    first = _seed_buyer(seeded, name="Alpha Sensors", fit="match")
    second = _seed_buyer(seeded, name="Beta Sensors", fit="match")
    response = api.post(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/buyer-reviews",
        json={"selection": {"kind": "explicit", "buyers": [{"id": first, "version": 1}]},
              "status": "accepted", "reason": "reviewed evidence"},
        headers=_h(subject=REVIEWER, key="review-01"),
    )
    assert response.status_code == 200, response.text
    result = response.json()["data"]
    assert (result["requested"], result["updated"], result["blocked"], result["conflicts"]) == (1, 1, 0, 0)
    assert result["results"][0]["version"] == 2
    assert api.get(f"/v1/workspaces/{WORKSPACE_A}/buyers/{first}", headers=_h(key="r-get-1")).json()["data"]["version"] == 2
    assert api.get(f"/v1/workspaces/{WORKSPACE_A}/buyers/{second}", headers=_h(key="r-get-2")).json()["data"]["version"] == 1


def test_a_stale_review_version_conflicts_and_preserves_the_prior_record(api, seeded):
    buyer_id = _seed_buyer(seeded, name="Alpha Sensors", fit="match", review="accepted")
    response = api.post(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/buyer-reviews",
        json={"selection": {"kind": "explicit", "buyers": [{"id": buyer_id, "version": 9}]},
              "status": "rejected", "reason": "changed mind"},
        headers=_h(subject=REVIEWER, key="review-conflict"),
    )
    result = response.json()["data"]
    assert result["conflicts"] == 1 and result["updated"] == 0
    assert result["results"][0] == {"id": buyer_id, "status": "conflict", "reason_code": "version_conflict", "version": 1}
    assert api.get(f"/v1/workspaces/{WORKSPACE_A}/buyers/{buyer_id}", headers=_h(key="r-get-3")).json()["data"]["review"]["status"] == "accepted"


def test_a_snapshot_review_expands_excluding_removed_ids(api, seeded):
    first = _seed_buyer(seeded, name="Alpha Sensors", fit="match")
    second = _seed_buyer(seeded, name="Beta Sensors", fit="match")
    snapshot_id = _snapshot(api, key="review-snap")
    response = api.post(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/buyer-reviews",
        json={"selection": {"kind": "snapshot", "snapshot_id": snapshot_id, "excluded_ids": [second]},
              "status": "accepted", "reason": "batch reviewed"},
        headers=_h(subject=REVIEWER, key="review-snap-key"),
    )
    result = response.json()["data"]
    assert result["requested"] == 1 and result["updated"] == 1
    assert {row["id"] for row in result["results"]} == {first}


def test_review_requires_a_reviewer_and_replays(api, seeded):
    buyer_id = _seed_buyer(seeded, name="Alpha Sensors", fit="match")
    body = {"selection": {"kind": "explicit", "buyers": [{"id": buyer_id, "version": 1}]},
            "status": "needs_information", "reason": "ask for detail"}
    denied = api.post(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/buyer-reviews",
        json=body, headers=_h(subject=OPERATOR, key="review-denied"),
    )
    assert denied.status_code == 403
    first = api.post(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/buyer-reviews",
        json=body, headers=_h(subject=REVIEWER, key="review-replay"),
    )
    assert first.status_code == 200 and first.json()["data"]["updated"] == 1
    replay = api.post(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/buyer-reviews",
        json=body, headers=_h(subject=REVIEWER, key="review-replay"),
    )
    assert replay.json()["data"] == first.json()["data"]  # the stored result, not a re-apply
    assert api.get(f"/v1/workspaces/{WORKSPACE_A}/buyers/{buyer_id}", headers=_h(key="r-get-4")).json()["data"]["version"] == 2
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_buyer_review_db.py -v -k review`
Expected: FAIL - `501 NOT_IMPLEMENTED` (reviewBuyers is in the registry).

- [ ] **Step 3: Implement the service, the route and the app registration**

Create `services/api/buyeros_api/services/buyer_review.py`:

```python
"""Apply a bulk human review against explicit or snapshot buyer versions (BO-008)."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from ..api.errors import ApiError
from ..db.buyers import BuyerSnapshot, BuyerSnapshotItem, FitAssessment, HumanReview, ProjectBuyer


async def _resolve_items(session, *, workspace_id, project_id, selection: dict):
    """Return deterministic (buyer_id, expected_version) pairs for the request's selection."""
    if selection["kind"] == "explicit":
        return [(uuid.UUID(item["id"]), item["version"]) for item in selection["buyers"]]
    snapshot_id = uuid.UUID(selection["snapshot_id"])
    snapshot = (
        await session.execute(
            select(BuyerSnapshot).where(
                BuyerSnapshot.workspace_id == workspace_id,
                BuyerSnapshot.project_id == project_id,
                BuyerSnapshot.id == snapshot_id,
            )
        )
    ).scalar_one_or_none()
    if snapshot is None:
        raise ApiError(404, "NOT_FOUND", "buyer snapshot not found")
    if snapshot.expires_at is not None and snapshot.expires_at <= datetime.now(timezone.utc):
        raise ApiError(404, "NOT_FOUND", "buyer snapshot expired")
    excluded = {uuid.UUID(value) for value in selection["excluded_ids"]}
    rows = (
        await session.execute(
            select(BuyerSnapshotItem)
            .where(BuyerSnapshotItem.workspace_id == workspace_id, BuyerSnapshotItem.snapshot_id == snapshot_id)
            .order_by(BuyerSnapshotItem.ordinal)
        )
    ).scalars().all()
    return [(row.buyer_id, row.buyer_version) for row in rows if row.buyer_id not in excluded]


async def _latest(session, model, workspace_id, buyer_id):
    return (
        await session.execute(
            select(model)
            .where(model.workspace_id == workspace_id, model.project_buyer_id == buyer_id)
            .order_by(model.created_at.desc(), model.id)
        )
    ).scalars().first()


async def apply(session, *, workspace_id, project_id, actor_user_id, selection: dict, status: str, reason: str) -> dict:
    items = await _resolve_items(session, workspace_id=workspace_id, project_id=project_id, selection=selection)
    results: list[dict] = []
    updated = blocked = conflicts = 0
    for buyer_id, expected_version in items:
        buyer = (
            await session.execute(
                select(ProjectBuyer)
                .where(
                    ProjectBuyer.workspace_id == workspace_id,
                    ProjectBuyer.project_id == project_id,
                    ProjectBuyer.id == buyer_id,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if buyer is None:
            blocked += 1
            results.append({"id": str(buyer_id), "status": "blocked", "reason_code": "not_found"})
            continue
        if buyer.version != expected_version:
            conflicts += 1
            results.append({"id": str(buyer_id), "status": "conflict", "reason_code": "version_conflict", "version": buyer.version})
            continue
        latest = await _latest(session, HumanReview, workspace_id, buyer_id)
        if latest is not None and latest.state == status:
            results.append({"id": str(buyer_id), "status": "unchanged", "version": buyer.version})
            continue
        fit = await _latest(session, FitAssessment, workspace_id, buyer_id)
        session.add(
            HumanReview(
                workspace_id=workspace_id, project_buyer_id=buyer_id, state=status, reason=reason,
                actor_user_id=actor_user_id, fit_assessment_id=fit.id if fit else None,
            )
        )
        buyer.version += 1
        await session.flush()
        updated += 1
        results.append({"id": str(buyer_id), "status": "updated", "reason_code": status, "version": buyer.version})
    return {
        "requested": len(items), "updated": updated, "blocked": blocked, "conflicts": conflicts, "results": results,
    }
```

Create `services/api/buyeros_api/api/routes/reviews.py`:

```python
import uuid

from fastapi import APIRouter, Depends, Header, Request

from ..auth import Principal, get_principal
from ..errors import ApiError, envelope
from ..schemas import ReviewRequest

router = APIRouter(prefix="/v1/workspaces/{workspace_id}", tags=["buyer-reviews"])


@router.post("/projects/{project_id}/buyer-reviews")
async def review_buyers(
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    payload: ReviewRequest,
    request: Request,
    principal: Principal = Depends(get_principal),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    from sqlalchemy import select

    from ...db.icp import Project
    from ...services.buyer_review import apply
    from ..deps import load_membership, permission_for_roles, tenant_scoped
    from ..idempotency import begin_idempotency, complete_idempotency

    if not idempotency_key:
        raise ApiError(400, "INVALID_REQUEST", "Idempotency-Key header is required")
    body = payload.model_dump(mode="json")

    async with tenant_scoped(workspace_id) as session:
        membership = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(membership["roles"], "reviewBuyers"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        project = (
            await session.execute(select(Project).where(Project.workspace_id == workspace_id, Project.id == project_id))
        ).scalar_one_or_none()
        if project is None:
            raise ApiError(404, "NOT_FOUND", "project not found")
        outcome = await begin_idempotency(
            session, workspace_id=workspace_id, actor_id=membership["user_id"],
            operation_id="reviewBuyers", key=idempotency_key, body=body,
        )
        if outcome.replay and outcome.response is not None:
            return envelope(outcome.response, request.state.request_id)
        data = await apply(
            session, workspace_id=workspace_id, project_id=project_id,
            actor_user_id=membership["user_id"], selection=body["selection"],
            status=body["status"], reason=body["reason"],
        )
        complete_idempotency(outcome, str(project_id), response=data)
    return envelope(data, request.state.request_id)
```

In `services/api/buyeros_api/api/app.py`, add
`from .routes.reviews import router as reviews_router` and `app.include_router(reviews_router)` (after
`buyers_router`). Remove `"reviewBuyers"` from `services/api/buyeros_api/api/unimplemented.py` and add
`"reviewBuyers"` to the `implemented` set in `services/api/tests/test_api_buyers.py`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_buyer_review_db.py tests/test_api_buyers.py tests/test_api_routes_contract.py -v`
Expected: PASS with Docker.

- [ ] **Step 5: Commit**

```bash
git add services/api/buyeros_api/services/buyer_review.py services/api/buyeros_api/api/routes/reviews.py services/api/buyeros_api/api/app.py services/api/buyeros_api/api/unimplemented.py services/api/tests/test_api_buyers.py services/api/tests/test_buyer_review_db.py
git commit -m "feat(api): append-only bulk buyer review with per-item conflicts"
```

---

### Task 7: Evidence reads (listBuyerEvidence and getEvidence)

**Files:**
- Modify: `services/api/buyeros_api/api/routes/buyers.py`
- Modify: `services/api/buyeros_api/api/unimplemented.py`
- Modify: `services/api/tests/test_api_buyers.py`
- Modify: `services/api/tests/test_buyer_review_db.py`

**Interfaces:**
- Produces: `list_buyer_evidence` and `get_evidence` routes.
- Consumes: `evidence_data`, `Evidence`, `SourceDocument`, `ProjectBuyer`.

- [ ] **Step 1: Write the failing tests**

Append to `services/api/tests/test_buyer_review_db.py`:

```python
def _seed_evidence(seeded, buyer_id, company_id):
    source_id = str(uuid.uuid4())
    evidence_id = str(uuid.uuid4())
    with psycopg.connect(seeded, autocommit=True) as conn:
        conn.execute(
            "INSERT INTO source_documents(id, workspace_id, canonical_url, digest, retrieved_at, language) "
            "VALUES (%s, %s, 'https://example.test/a', 'sha256:x', now(), 'en')",
            (source_id, WORKSPACE_A),
        )
        conn.execute(
            "INSERT INTO evidence(id, workspace_id, project_id, company_id, source_document_id, stance, excerpt) "
            "VALUES (%s, %s, %s, %s, %s, 'supports', 'supports the requirement')",
            (evidence_id, WORKSPACE_A, PROJECT_A, company_id, source_id),
        )
    return evidence_id


def test_buyer_evidence_is_scoped_and_404s_foreign(api, seeded):
    buyer_id = _seed_buyer(seeded, name="Alpha Sensors", fit="match")
    with psycopg.connect(seeded) as conn:
        company_id = conn.execute("SELECT company_id FROM project_buyers WHERE id = %s", (buyer_id,)).fetchone()[0]
    evidence_id = _seed_evidence(seeded, buyer_id, company_id)

    page = api.get(f"/v1/workspaces/{WORKSPACE_A}/buyers/{buyer_id}/evidence", headers=_h(key="ev-01"))
    assert page.status_code == 200, page.text
    body = page.json()["data"]
    assert body["total"] == 1 and body["items"][0]["id"] == evidence_id
    assert body["items"][0]["relationship"] == "supports"
    assert body["items"][0]["source_url"] == "https://example.test/a"

    one = api.get(f"/v1/workspaces/{WORKSPACE_A}/evidence/{evidence_id}", headers=_h(key="ev-02"))
    assert one.status_code == 200 and one.json()["data"]["id"] == evidence_id

    foreign = api.get(f"/v1/workspaces/{WORKSPACE_B}/evidence/{evidence_id}", headers=_h(key="ev-03"))
    assert foreign.status_code == 404
    assert evidence_id not in foreign.text
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_buyer_review_db.py -v -k evidence`
Expected: FAIL - `501 NOT_IMPLEMENTED` (both operations are in the registry).

- [ ] **Step 3: Implement the routes**

Add to `services/api/buyeros_api/api/routes/buyers.py`:

```python
@router.get("/buyers/{buyer_id}/evidence")
async def list_buyer_evidence(
    workspace_id: uuid.UUID,
    buyer_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(get_principal),
    offset: int = 0,
    limit: int = 50,
) -> dict:
    from sqlalchemy import func, select

    from ...db.buyers import Evidence, ProjectBuyer, SourceDocument
    from ...services.buyer_view import evidence_data
    from ..deps import load_membership, permission_for_roles, tenant_scoped

    limit = max(1, min(limit, 100))
    async with tenant_scoped(workspace_id) as session:
        membership = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(membership["roles"], "listBuyerEvidence"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        buyer = (
            await session.execute(
                select(ProjectBuyer).where(ProjectBuyer.workspace_id == workspace_id, ProjectBuyer.id == buyer_id)
            )
        ).scalar_one_or_none()
        if buyer is None:
            raise ApiError(404, "NOT_FOUND", "buyer not found")
        total = (
            await session.execute(
                select(func.count())
                .select_from(Evidence)
                .where(
                    Evidence.workspace_id == workspace_id,
                    Evidence.project_id == buyer.project_id,
                    Evidence.company_id == buyer.company_id,
                )
            )
        ).scalar_one()
        rows = (
            await session.execute(
                select(Evidence, SourceDocument)
                .outerjoin(
                    SourceDocument,
                    (SourceDocument.workspace_id == Evidence.workspace_id)
                    & (SourceDocument.id == Evidence.source_document_id),
                )
                .where(
                    Evidence.workspace_id == workspace_id,
                    Evidence.project_id == buyer.project_id,
                    Evidence.company_id == buyer.company_id,
                )
                .order_by(Evidence.created_at, Evidence.id)
                .offset(offset)
                .limit(limit)
            )
        ).all()
        items = [evidence_data(evidence, source) for evidence, source in rows]
    return envelope({"items": items, "offset": offset, "limit": limit, "total": total}, request.state.request_id)


@router.get("/evidence/{evidence_id}")
async def get_evidence(
    workspace_id: uuid.UUID,
    evidence_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(get_principal),
) -> dict:
    from sqlalchemy import select

    from ...db.buyers import Evidence, SourceDocument
    from ...services.buyer_view import evidence_data
    from ..deps import load_membership, permission_for_roles, tenant_scoped

    async with tenant_scoped(workspace_id) as session:
        membership = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(membership["roles"], "getEvidence"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        row = (
            await session.execute(
                select(Evidence, SourceDocument)
                .outerjoin(
                    SourceDocument,
                    (SourceDocument.workspace_id == Evidence.workspace_id)
                    & (SourceDocument.id == Evidence.source_document_id),
                )
                .where(Evidence.workspace_id == workspace_id, Evidence.id == evidence_id)
            )
        ).one_or_none()
        if row is None:
            raise ApiError(404, "NOT_FOUND", "evidence not found")
        evidence, source = row
        data = evidence_data(evidence, source)
    return envelope(data, request.state.request_id)
```

Remove `"listBuyerEvidence"` and `"getEvidence"` from `services/api/buyeros_api/api/unimplemented.py` and
add both to the `implemented` set in `services/api/tests/test_api_buyers.py`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_buyer_review_db.py tests/test_api_buyers.py tests/test_api_routes_contract.py -v`
Expected: PASS with Docker.

- [ ] **Step 5: Commit**

```bash
git add services/api/buyeros_api/api/routes/buyers.py services/api/buyeros_api/api/unimplemented.py services/api/tests/test_api_buyers.py services/api/tests/test_buyer_review_db.py
git commit -m "feat(api): scoped buyer evidence reads"
```

---

### Task 8: Live buyer/evidence mappers and the selection helper

**Files:**
- Modify: `services/live/mapping.ts`
- Create: `services/live/buyer-selection.ts`
- Modify: `tests/live-adapter-checks.mjs`

**Interfaces:**
- Produces: `LiveBuyer`, `LiveBuyerPage`, `LiveEvidence`, `toBuyers(data)`, `toBuyerPage(data)`, `toEvidence(data)`, `toEvidencePage(data)`; `explicitSelection`, `snapshotSelection`, `ReviewSelection`.
- Consumes: `page`, `str`, `strList`, `MapError` (module-local).

- [ ] **Step 1: Write the failing checks**

In `tests/live-adapter-checks.mjs`, replace the existing `toBuyers` check (the `'buyers map to the narrow
model and keep a null note as null'` block and its line in `'every mapper enforces its required fields'`)
with the fuller shape, then append the new checks before the final summary:

```js
await test('buyers map to the versioned review model',()=>{
  const payload={items:[{id:'b-1',name:'Example GmbH',version:3,note:null,evidence_count:2,
    fit:{verdict:'match'},review:{status:'accepted'},owner_membership_id:null}],offset:0,limit:1,total:1};
  assert.deepEqual(map.toBuyers(payload),[{id:'b-1',name:'Example GmbH',version:3,fitVerdict:'match',
    reviewStatus:'accepted',ownerMembershipId:null,note:null,evidenceCount:2}]);
});

await test('a buyer without a fit or review maps those to null, not an error',()=>{
  const payload={items:[{id:'b-1',name:'Example GmbH',version:1,note:'n',evidence_count:0}]};
  const [row]=map.toBuyers(payload);
  assert.equal(row.fitVerdict,null);
  assert.equal(row.reviewStatus,null);
});

await test('a buyer page keeps the snapshot id and paging',()=>{
  const page=map.toBuyerPage({items:[{id:'b-1',name:'A',version:1,note:null,evidence_count:0}],
    snapshot_id:'s-1',offset:0,limit:50,total:1,expires_at:'2026-09-19T00:00:00Z'});
  assert.equal(page.snapshotId,'s-1');
  assert.equal(page.total,1);
  assert.equal(page.items[0].id,'b-1');
});

await test('evidence maps the contract subset',()=>{
  const payload={items:[{id:'e-1',relationship:'supports',excerpt:'x',kind:'observation',status:'available',
    source_url:'https://example.test/a'}],offset:0,limit:1,total:1};
  assert.deepEqual(map.toEvidencePage(payload).items,[{id:'e-1',relationship:'supports',excerpt:'x',
    kind:'observation',status:'available',sourceUrl:'https://example.test/a'}]);
});

const selection=await loadModule('services/live/buyer-selection.ts');

await test('an explicit selection carries the frozen versions',()=>{
  assert.deepEqual(selection.explicitSelection([{id:'b-1',version:2}]),{kind:'explicit',buyers:[{id:'b-1',version:2}]});
});

await test('a snapshot selection excludes the removed ids',()=>{
  assert.deepEqual(selection.snapshotSelection('s-1',['b-9']),{kind:'snapshot',snapshot_id:'s-1',excluded_ids:['b-9']});
});
```

- [ ] **Step 2: Run to verify it fails**

Run (repo root): `node tests/live-adapter-checks.mjs`
Expected: FAIL - the buyer mapper returns the narrow shape and `services/live/buyer-selection.ts` does not exist.

- [ ] **Step 3: Implement the mappers and the helper**

In `services/live/mapping.ts`, replace `LiveBuyer` and `toBuyers` and add the page/evidence mappers:

```ts
export interface LiveBuyer {
  id: string; name: string; version: number; fitVerdict: string | null;
  reviewStatus: string | null; ownerMembershipId: string | null; note: string | null; evidenceCount: number;
}
export interface LiveBuyerPage { items: LiveBuyer[]; snapshotId: string; offset: number; limit: number; total: number; expiresAt: string | null; }
export interface LiveEvidence { id: string; relationship: string; excerpt: string; kind: string; status: string; sourceUrl: string | null; }

function num(row: Record<string, unknown>, key: string): number {
  const v = row[key];
  if (typeof v === 'number') return v;
  throw new MapError(`missing required field: ${key}`);
}

function optionalString(row: Record<string, unknown>, key: string): string | null {
  const v = row[key];
  return typeof v === 'string' ? v : null;
}

export function toBuyers(data: unknown): LiveBuyer[] {
  return rows(data).map((r) => ({
    id: str(r, 'id'),
    name: str(r, 'name'),
    version: num(r, 'version'),
    fitVerdict: typeof r.fit === 'object' && r.fit !== null ? optionalString(r.fit as Record<string, unknown>, 'verdict') : null,
    reviewStatus: typeof r.review === 'object' && r.review !== null ? optionalString(r.review as Record<string, unknown>, 'status') : null,
    ownerMembershipId: optionalString(r, 'owner_membership_id'),
    note: optionalString(r, 'note'),
    evidenceCount: num(r, 'evidence_count'),
  }));
}

export function toBuyerPage(data: unknown): LiveBuyerPage {
  if (typeof data !== 'object' || data === null) throw new MapError('expected a buyer page object');
  const page = data as Record<string, unknown>;
  return {
    items: toBuyers(data),
    snapshotId: str(page, 'snapshot_id'),
    offset: num(page, 'offset'),
    limit: num(page, 'limit'),
    total: num(page, 'total'),
    expiresAt: optionalString(page, 'expires_at'),
  };
}

export function toEvidence(data: unknown): LiveEvidence[] {
  return rows(data).map((r) => ({
    id: str(r, 'id'),
    relationship: str(r, 'relationship'),
    excerpt: str(r, 'excerpt'),
    kind: str(r, 'kind'),
    status: str(r, 'status'),
    sourceUrl: optionalString(r, 'source_url'),
  }));
}

export function toEvidencePage(data: unknown): { items: LiveEvidence[]; total: number } {
  if (typeof data !== 'object' || data === null) throw new MapError('expected an evidence page object');
  return { items: toEvidence(data), total: num(data as Record<string, unknown>, 'total') };
}
```

Create `services/live/buyer-selection.ts`:

```ts
/** Build the contract `Selection` for a review action. No UI, no storage, no demo data. */

export interface VersionedBuyer { id: string; version: number; }
export type ReviewSelection =
  | { kind: 'explicit'; buyers: VersionedBuyer[] }
  | { kind: 'snapshot'; snapshot_id: string; excluded_ids: string[] };

export function explicitSelection(buyers: VersionedBuyer[]): ReviewSelection {
  return { kind: 'explicit', buyers };
}

export function snapshotSelection(snapshotId: string, excludedIds: string[]): ReviewSelection {
  return { kind: 'snapshot', snapshot_id: snapshotId, excluded_ids: excludedIds };
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `node tests/live-adapter-checks.mjs` -> the previous count plus 6.
Run: `node tests/domain-checks.mjs` -> `11 domain checks passed`.
Run: `npx tsc --noEmit --strict --module esnext --moduleResolution bundler --target ES2022 services/live/mapping.ts services/live/buyer-selection.ts` -> clean.
Run: `npx eslint services/live/mapping.ts services/live/buyer-selection.ts tests/live-adapter-checks.mjs` -> clean.

- [ ] **Step 5: Commit**

```bash
git add services/live/mapping.ts services/live/buyer-selection.ts tests/live-adapter-checks.mjs
git commit -m "feat(live): buyer, evidence and selection mappers"
```

---

### Task 9: Live buyer table and detail drawer

**Files:**
- Create: `features/live/buyers.tsx`
- Create: `features/live/buyer-detail.tsx`
- Modify: `features/workspace.tsx`

**Interfaces:**
- Consumes: `useWorkspaceSession`, `client.request`, `toBuyerPage`/`toEvidencePage`, `explicitSelection`/`snapshotSelection`, `LiveCancelled`.
- Produces: `LiveBuyers`, `LiveBuyerDetail`, rendered in live mode.

This task is UI-only; it is verified by `tsc`, `eslint` and `pnpm build` rather than the node harness (recorded in P11).

- [ ] **Step 1: Create the detail panel**

```tsx
// features/live/buyer-detail.tsx
'use client';
import {useEffect,useState} from 'react';
import {useWorkspaceSession} from '@/features/providers/workspace-session';
import {LiveCancelled} from '@/services/live/client';
import {toEvidencePage,type LiveEvidence} from '@/services/live/mapping';

export function LiveBuyerDetail({buyerId,onClose}:{buyerId:string; onClose:()=>void}) {
  const {session,client}=useWorkspaceSession();
  const [evidence,setEvidence]=useState<LiveEvidence[]>([]);
  const [error,setError]=useState('');
  useEffect(()=>{
    let active=true; const own=new AbortController();
    const scope=session.current();
    if(!scope.workspace||!scope.project)return ()=>{active=false;own.abort();};
    const identity=session.identity();
    const signal=AbortSignal.any([session.controller().signal,own.signal]);
    const path=`/v1/workspaces/${scope.workspace}/buyers/${buyerId}/evidence`;
    void (async()=>{
      try{
        const page=toEvidencePage(await client.request<unknown>({path,token:session.token(),scope:identity,signal}));
        if(!active||!session.isCurrent(identity))return;
        setEvidence(page.items);
      }catch(err){
        if(!active||err instanceof LiveCancelled)return;
        const failure=err as {code?:string;message?:string};
        setError(failure.code||failure.message||'Failed to load evidence');
      }
    })();
    return ()=>{active=false;own.abort();};
  },[client,session,buyerId]);
  return (
    <section className="panel" role="status">
      <div className="inline spread"><h3>Buyer evidence</h3><button onClick={onClose}>Close</button></div>
      {error?<p role="alert">{error}</p>:null}
      {evidence.length?evidence.map((row)=>(
        <div className="activity" key={row.id}>
          <div><b>{row.relationship}</b><p>{row.excerpt}</p></div>
        </div>
      )):<p className="muted">No evidence recorded.</p>}
    </section>
  );
}
```

- [ ] **Step 2: Create the live buyer table**

```tsx
// features/live/buyers.tsx
'use client';
import {useCallback,useEffect,useState} from 'react';
import {useWorkspaceSession} from '@/features/providers/workspace-session';
import {LiveCancelled} from '@/services/live/client';
import {toBuyerPage,type LiveBuyer,type LiveBuyerPage} from '@/services/live/mapping';
import {explicitSelection,snapshotSelection,type ReviewSelection} from '@/services/live/buyer-selection';
import {LiveBuyerDetail} from './buyer-detail';

const REVIEW_STATUSES=['accepted','rejected','needs_information'] as const;

export function LiveBuyers() {
  const {session,client}=useWorkspaceSession();
  const [page,setPage]=useState<LiveBuyerPage|null>(null);
  const [selected,setSelected]=useState<Record<string,number>>({});
  const [detail,setDetail]=useState<string|null>(null);
  const [status,setStatus]=useState<(typeof REVIEW_STATUSES)[number]>('accepted');
  const [reason,setReason]=useState('');
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const [reload,setReload]=useState(0);
  const scope=session.current();
  const workspace=scope.workspace;
  const project=scope.project;

  useEffect(()=>{
    let active=true; const own=new AbortController();
    const current=session.current();
    if(!current.workspace||!current.project){ setPage(null); return ()=>{active=false;own.abort();}; }
    const identity=session.identity();
    const signal=AbortSignal.any([session.controller().signal,own.signal]);
    void (async()=>{
      setError('');
      try{
        const snapshot=await client.request<{id:string}>({
          path:`/v1/workspaces/${current.workspace}/projects/${current.project}/buyer-snapshots`,
          method:'POST',scope:identity,token:session.token(),signal,
          body:{filters:{},sort:'name_asc',requested_limit:100},
          idempotencyKey:`snapshot-${Date.now()}-${Math.random().toString(36).slice(2)}`,
        });
        const loaded=toBuyerPage(await client.request<unknown>({
          path:`/v1/workspaces/${current.workspace}/projects/${current.project}/buyers?snapshot_id=${snapshot.id}&offset=0&limit=50`,
          token:session.token(),scope:identity,signal,
        }));
        if(!active||!session.isCurrent(identity))return;
        setPage(loaded); setSelected({});
      }catch(err){
        if(!active||err instanceof LiveCancelled)return;
        const failure=err as {code?:string;message?:string};
        setError(failure.code||failure.message||'Failed to load buyers');
      }
    })();
    return ()=>{active=false;own.abort();};
  },[client,session,reload]);

  const toggle=useCallback((buyer:LiveBuyer)=>{
    setSelected((prev)=>{
      const next={...prev};
      if(next[buyer.id]!==undefined)delete next[buyer.id]; else next[buyer.id]=buyer.version;
      return next;
    });
  },[]);

  function selection():ReviewSelection|null{
    if(!page)return null;
    const ids=Object.keys(selected);
    if(!ids.length)return null;
    const allPage=page.items.every((buyer)=>selected[buyer.id]!==undefined)&&ids.length===page.items.length;
    if(allPage&&page.total>page.items.length){
      return snapshotSelection(page.snapshotId,[]);
    }
    return explicitSelection(ids.map((id)=>({id,version:selected[id]})));
  }

  async function submitReview(){
    const payload=selection();
    if(!payload||reason.trim().length<3){ setError('Select at least one buyer and give a reason.'); return; }
    setBusy(true); setError('');
    try{
      await client.request({
        path:`/v1/workspaces/${workspace}/projects/${project}/buyer-reviews`,method:'POST',
        scope:session.identity(),token:session.token(),
        idempotencyKey:`review-${Date.now()}-${Math.random().toString(36).slice(2)}`,
        body:{selection:payload,status,reason},
      });
      setSelected({}); setReason(''); setReload((value)=>value+1);
    }catch(err){
      if(!(err instanceof LiveCancelled)){
        const failure=err as {code?:string;message?:string};
        setError(failure.code||failure.message||'Review failed');
      }
    }finally{ setBusy(false); }
  }

  if(!workspace||!project)return <section className="panel" role="status"><p>No project selected. Save a profile to create one.</p></section>;
  if(error&&!page)return <section className="panel" role="alert"><p>{error}</p></section>;
  if(!page)return <section className="panel" role="status"><p>Loading buyers...</p></section>;
  return (
    <section className="panel">
      <div className="inline spread"><h2>Buyers</h2><span>{page.total} in this selection</span></div>
      {error?<p role="alert">{error}</p>:null}
      {page.items.length?page.items.map((buyer)=>(
        <div className="activity" key={buyer.id}>
          <input type="checkbox" aria-label={`Select ${buyer.name}`} checked={selected[buyer.id]!==undefined} onChange={()=>toggle(buyer)}/>
          <div><b>{buyer.name}</b><p>{buyer.fitVerdict||'no fit'} - {buyer.reviewStatus||'awaiting_review'} - {buyer.note||'no note'}</p></div>
          <button onClick={()=>setDetail(buyer.id)}>Details</button>
        </div>
      )):<p className="muted">No buyers in this snapshot.</p>}
      <div className="inline">
        <select aria-label="Review status" value={status} onChange={(event)=>setStatus(event.target.value as typeof status)}>
          {REVIEW_STATUSES.map((value)=><option key={value} value={value}>{value}</option>)}
        </select>
        <input aria-label="Review reason" value={reason} onChange={(event)=>setReason(event.target.value)} placeholder="Reason (required)"/>
        <button onClick={submitReview} disabled={busy}>{busy?'Reviewing...':'Apply review'}</button>
      </div>
      {detail?<LiveBuyerDetail buyerId={detail} onClose={()=>setDetail(null)}/>:null}
    </section>
  );
}
```

- [ ] **Step 3: Wire the live branch in `features/workspace.tsx`**

Add `import {LiveBuyers} from './live/buyers';`, add `isBuyers=path==='/app/discover'` beside the other
route booleans, change the gate to
`const liveAvailability=availabilityFor(mode,isOverview||isWizard||isBuyers?'overview':'discovery');`,
and add the buyers branch to the live expression (after the wizard branch):

```tsx
isBuyers?(liveAvailability==='available'?<LiveBuyers/>:<LiveUnavailable state={liveAvailability}/>):
```

Keep the demo branch byte-identical.

- [ ] **Step 4: Verify**

Run: `node tests/live-adapter-checks.mjs` -> unchanged count (this task adds no checks).
Run: `node tests/domain-checks.mjs` -> `11 domain checks passed`.
Run: `npx tsc -p tsconfig.json` -> clean.
Run: `npx eslint features/live/buyers.tsx features/live/buyer-detail.tsx features/workspace.tsx` -> no NEW findings (the pre-existing `workspace.tsx` errors must not grow).
Run: `pnpm build` -> clean.

- [ ] **Step 5: Commit**

```bash
git add features/live/buyers.tsx features/live/buyer-detail.tsx features/workspace.tsx
git commit -m "feat(live): render the buyer table and detail drawer in live mode"
```

---

## Self-Review

- **Spec coverage:** §A boundaries (Tasks 1-9 create exactly the named units); §B data model/versioning/immutability (Tasks 1, 5, 6); §C API/errors/idempotency/bookkeeping (Tasks 3-7); §D snapshot materialization and review semantics (Tasks 3, 5, 6); §E client and UI (Tasks 8, 9); §F testing and acceptance mapping (the DB tests in Tasks 1-7 and the checks in Task 8; Task 9 is UI, build-verified); §G out of scope (no task, by design). Every section maps to a task.
- **Correction applied at review (spec amendment needed):** the spec lists `source_types` among the supported filters, but neither `evidence` nor `source_documents` carries a source-type column (that arrives with P3/BO-014 ingestion), so it cannot be honored. `buyer_selection.py` therefore treats `source_types` as deferred and rejects a non-empty value with `422`, exactly like `markets`. The committed spec's §D filter list must be amended to move `source_types` from supported to deferred before execution.
- **Placeholder scan:** no `TBD`/`TODO`; every code step contains complete code.
- **Type consistency:** `buyer_view.buyer_data`/`snapshot_data`/`evidence_data` flow into Tasks 3-7; `buyer_read.view` is consumed by Tasks 4-6; `buyer_review.apply` by Task 6; `IdempotencyOutcome.response` by Tasks 3 and 6; `toBuyerPage`/`toEvidencePage`/`explicitSelection`/`snapshotSelection` (Task 8) by Task 9. `createBuyerSnapshot`/`updateBuyer`/`reviewBuyers` idempotency operation ids match the contract.
- **Known limitation carried forward:** `listBuyers`/`getBuyer` load the fit, review, owner and evidence count with one query per row; for a page of at most 100 this is acceptable in a pilot and is recorded rather than batched.
- **Acceptance mapping:** TEST-BO-008-01 -> the frozen-snapshot paging test plus every cross-tenant `404`; TEST-BO-008-03 -> the review update/conflict/replay tests; TEST-BO-008-02 is deferred with the lists slice (Slice 2), recorded in the spec.

## Global Notes

- No remote commits/pushes, deploys, cloud resources, real-data migrations, provider calls, or sends.
- Record exact command output in `.superpowers/sdd/p13/progress.md`; every unexecuted check is **NOT RUN**. A DB test that skips is NOT RUN, not a pass.
- Execution requires a recorded dependency waiver and may use `superpowers:subagent-driven-development` or `superpowers:executing-plans`.
- One migration owner: `0011_project_buyer_version` is the only schema change this phase.
