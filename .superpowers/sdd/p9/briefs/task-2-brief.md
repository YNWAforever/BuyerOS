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
