# P10 Bearer Identity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **Build is NOT authorized by this document**; execution requires explicit approval under a dependency waiver.

**Goal:** Replace P9's fail-closed authentication stub with real RS256/JWKS verification and make the authenticated request path executable end-to-end.

**Architecture:** A `JwksKeyCache` owns the one stateful, network-touching concern (TTL cache, single refetch on unknown `kid`, fail-closed outage). A `TokenVerifier` composes it with the pure claim rules P9 already tested, turning a token into a `Principal(issuer, subject)`. `get_principal` stays a thin async FastAPI dependency that maps `AuthError` to `ApiError(401, "UNAUTHENTICATED")`. Roles and workspaces continue to come only from Postgres via the unchanged `load_membership`. A new Alembic revision grants the runtime role `SELECT` on `users`, which is what currently makes every authenticated route fail.

**Tech Stack:** Python 3.12+ (installed 3.14.6), FastAPI, SQLAlchemy 2 + psycopg, Alembic, `PyJWT[crypto]` (new), pytest + httpx TestClient, uv; disposable PostgreSQL for tests.

## Global Constraints

- Branch: `p10-bearer-identity` from `p9-api-surface` at `b11cf5c`.
- Spec: `docs/buyeros/specs/2026-09-16-p10-bearer-identity-design.md`. Contract: `docs/buyeros/contracts/openapi.proposed.yaml` (authoritative).
- Plan-only artifact: no remote commits/pushes, deploys, cloud resources, real-data migrations, paid calls, mailboxes, or sends.
- Fail closed: with no `auth0_issuer`/`auth0_audience` configured, every route except liveness returns `401 UNAUTHENTICATED`. Roles come from Postgres membership, never token claims.
- RS256 only. `alg: none`, `HS256` and every other algorithm are rejected before signature work. The algorithm allow-list is passed explicitly and never derived from the token header alone.
- A JWKS outage must never become an API outage *or* a signature bypass: serve a still-valid cache, otherwise reject. Never return an empty key set or skip verification.
- `Principal` carries only `(issuer, subject)`. No claim is ever used for authorization.
- Unknown actor (valid token, no `users` row) → non-enumerating `404 NOT_FOUND`. No auto-provisioning.
- `401` bodies are a fixed generic message: never state which check failed, never echo a claim, token or header value.
- The `users` grant is **SELECT only**. The API never writes `users`.
- Every unexecuted check is **NOT RUN**.

**Existing interfaces this plan consumes (already implemented):**
- `buyeros_api.settings.get_settings()` → `Settings` with `auth0_issuer`, `auth0_audience`, `jwks_cache_seconds` (default 300), `database_url`.
- `buyeros_api.api.auth.{AuthError, Principal, jwks_uri_for, claims_to_principal, get_principal}`.
- `buyeros_api.api.deps.{get_engine, tenant_scoped, load_membership, permission_for_roles}`.
- `buyeros_api.api.errors.{ApiError, envelope}`.
- `tests/conftest.py`: `pg_dsn`, `migrated`, `seeded` fixtures and `runtime_role_dsn(dsn)`.

---

### Task 1: Add the crypto dependency

**Files:**
- Modify: `services/api/pyproject.toml`
- Modify: `services/api/uv.lock` (regenerated)

**Interfaces:**
- Produces: an importable `jwt` module (PyJWT) with RSA support available to every later task.

- [ ] **Step 1: Add the dependency**

In `services/api/pyproject.toml`, add to `[project].dependencies`:

```toml
  "pyjwt[crypto]>=2.9,<3",
```

Then remove the now-stale trailing note (the one beginning `# NOTE (BO-005 spike): ... pyjwt[crypto] are intentionally omitted`), since the omission it documents is exactly what this task resolves. Leave `asyncpg` out of scope (still unused).

- [ ] **Step 2: Sync and verify the import**

Run (cwd `services/api`):

```bash
uv sync
uv run python -c "import jwt; from jwt import PyJWKClient; print(jwt.__version__)"
```

Expected: prints a `2.x` version with no error. Record the exact resolved version.

- [ ] **Step 3: Verify the full suite still passes**

Run: `uv run pytest -q`
Expected: PASS (175 passed, 1 skipped) — a dependency addition must not change behavior.

- [ ] **Step 4: Commit**

```bash
git add services/api/pyproject.toml services/api/uv.lock
git commit -m "chore(api): add pinned pyjwt[crypto] for bearer verification"
```

---

### Task 2: The JWKS key cache

**Files:**
- Create: `services/api/buyeros_api/api/jwks.py`
- Create: `services/api/tests/test_jwks_cache.py`

**Interfaces:**
- Produces: `class JwksKeyCache(fetch_jwks, *, cache_seconds=300, now=time.monotonic)`; `async def get_key(kid: str) -> object` raising `JwksError`; `def invalidate() -> None`. `JwksError` is defined in this module.
- Consumes: nothing from earlier tasks except the new `jwt` dependency.

**Design note:** `fetch_jwks` is an injected zero-argument async callable returning a parsed JWKS document (`{"keys": [{...}, ...]}`). This is what makes the whole state machine testable with no network. `now` is an injected clock (defaulting to `time.monotonic`) for deterministic TTL tests. `get_key` is async because its only I/O is the fetch; the caller awaits it.

- [ ] **Step 1: Write the failing test**

```python
# services/api/tests/test_jwks_cache.py
import asyncio

import pytest

from buyeros_api.api.jwks import JwksError, JwksKeyCache


def _doc(*kids):
    return {"keys": [{"kty": "RSA", "use": "sig", "kid": kid, "n": "AQAB", "e": "AQAB"} for kid in kids]}


class Fetcher:
    """Counts calls and can be told to fail, so refetch bounds are observable."""

    def __init__(self, *docs):
        self.docs = list(docs)
        self.calls = 0
        self.error = None

    async def __call__(self):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.docs[min(self.calls - 1, len(self.docs) - 1)]


def test_returns_cached_key_without_refetching():
    fetcher = Fetcher(_doc("k1"))
    cache = JwksKeyCache(fetcher, cache_seconds=300, now=lambda: 1000.0)
    assert asyncio.run(cache.get_key("k1")) is not None
    assert asyncio.run(cache.get_key("k1")) is not None
    assert fetcher.calls == 1


def test_unknown_kid_refetches_once_for_rotation():
    fetcher = Fetcher(_doc("k1"), _doc("k1", "k2"))
    cache = JwksKeyCache(fetcher, cache_seconds=300, now=lambda: 1000.0)
    assert asyncio.run(cache.get_key("k1")) is not None
    assert asyncio.run(cache.get_key("k2")) is not None
    assert fetcher.calls == 2


def test_unknown_kid_that_never_appears_raises_without_hammering():
    fetcher = Fetcher(_doc("k1"))
    cache = JwksKeyCache(fetcher, cache_seconds=300, now=lambda: 1000.0)
    with pytest.raises(JwksError):
        asyncio.run(cache.get_key("nope"))
    # one initial fetch + exactly one rotation refetch, never more
    assert fetcher.calls == 2


def test_stale_entry_refetches_and_picks_up_new_keys():
    clock = {"t": 1000.0}
    fetcher = Fetcher(_doc("k1"), _doc("k1", "k2"))
    cache = JwksKeyCache(fetcher, cache_seconds=300, now=lambda: clock["t"])
    asyncio.run(cache.get_key("k1"))
    clock["t"] = 1000.0 + 301
    assert asyncio.run(cache.get_key("k2")) is not None
    assert fetcher.calls == 2


def test_outage_serves_a_still_valid_cache():
    fetcher = Fetcher(_doc("k1"))
    cache = JwksKeyCache(fetcher, cache_seconds=300, now=lambda: 1000.0)
    asyncio.run(cache.get_key("k1"))
    fetcher.error = RuntimeError("network down")
    assert asyncio.run(cache.get_key("k1")) is not None


def test_outage_with_no_valid_cache_raises_rather_than_bypassing():
    fetcher = Fetcher(_doc("k1"))
    fetcher.error = RuntimeError("network down")
    cache = JwksKeyCache(fetcher, cache_seconds=300, now=lambda: 1000.0)
    with pytest.raises(JwksError):
        asyncio.run(cache.get_key("k1"))


def test_malformed_entries_are_skipped_not_coerced():
    doc = {"keys": [{"kty": "EC", "kid": "ec"}, {"kty": "RSA", "kid": "no-material"}]}
    fetcher = Fetcher(doc)
    cache = JwksKeyCache(fetcher, cache_seconds=300, now=lambda: 1000.0)
    with pytest.raises(JwksError):
        asyncio.run(cache.get_key("ec"))
    with pytest.raises(JwksError):
        asyncio.run(cache.get_key("no-material"))
```

- [ ] **Step 2: Run test to verify it fails**

Run (cwd `services/api`): `uv run pytest tests/test_jwks_cache.py -v`
Expected: FAIL — `ModuleNotFoundError: buyeros_api.api.jwks`.

- [ ] **Step 3: Write minimal implementation**

```python
# services/api/buyeros_api/api/jwks.py
"""JWKS fetch/cache/rotation for RS256 verification (P10).

The only stateful, network-touching unit in the auth path. Given a `kid` it
returns a usable public key or raises — it never returns an empty set and never
skips verification, so a JWKS outage can never become a signature bypass.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable

import jwt


class JwksError(Exception):
    pass


def _public_key(entry: dict):
    """Build an RSA public key from one JWK entry, or None if it is not usable."""
    if entry.get("kty") != "RSA":
        return None
    if entry.get("use") not in (None, "sig"):
        return None
    try:
        return jwt.algorithms.RSAAlgorithm.from_jwk(entry)
    except (ValueError, TypeError, KeyError):
        return None


class JwksKeyCache:
    """Per-process key cache: TTL hit, one refetch on unknown kid, fail closed."""

    def __init__(
        self,
        fetch_jwks: Callable[[], Awaitable[dict]],
        *,
        cache_seconds: int = 300,
        now: Callable[[], float] = time.monotonic,
    ) -> None:
        self._fetch_jwks = fetch_jwks
        self._cache_seconds = cache_seconds
        self._now = now
        self._keys: dict[str, object] = {}
        self._fetched_at: float | None = None
        self._lock = asyncio.Lock()

    def _fresh(self) -> bool:
        return self._fetched_at is not None and (self._now() - self._fetched_at) < self._cache_seconds

    def invalidate(self) -> None:
        self._fetched_at = None

    async def _refetch(self) -> None:
        async with self._lock:
            # Another request may have refreshed while we waited for the lock.
            if self._fresh() and self._keys:
                return
            document = await self._fetch_jwks()
            keys: dict[str, object] = {}
            for entry in document.get("keys", []):
                kid = entry.get("kid")
                if not kid:
                    continue
                key = _public_key(entry)
                if key is not None:
                    keys[kid] = key
            self._keys = keys
            self._fetched_at = self._now()

    async def get_key(self, kid: str):
        if kid in self._keys and self._fresh():
            return self._keys[kid]
        try:
            await self._refetch()
        except Exception as exc:  # noqa: BLE001 - any fetch failure is an auth failure
            if kid in self._keys and self._fresh():
                return self._keys[kid]  # outage: serve a still-valid cache
            raise JwksError("key set unavailable") from exc
        if kid not in self._keys:
            raise JwksError("unknown key id")
        return self._keys[kid]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_jwks_cache.py -v`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add services/api/buyeros_api/api/jwks.py services/api/tests/test_jwks_cache.py
git commit -m "feat(api): add JWKS cache with rotation and fail-closed outage handling"
```

---

### Task 3: The token verifier

**Files:**
- Create: `services/api/buyeros_api/api/verifier.py`
- Create: `services/api/tests/auth_fixtures.py`
- Create: `services/api/tests/test_auth_tenant.py`

**Interfaces:**
- Produces: `class TokenVerifier(jwks_cache, *, issuer, audience)` with `async def verify(token: str) -> Principal`; `async def fetch_jwks_document(jwks_uri) -> dict`; `def default_verifier(settings) -> TokenVerifier`.
- Consumes: `JwksError`, `JwksKeyCache` (Task 2); `Principal`, `AuthError`, `jwks_uri_for`, `claims_to_principal` (P9).

**`verify` is async, and this matters.** Every P9 route is `async def`, so verification runs inside a live event loop; a synchronous `verify` cannot bridge to the async JWKS cache with `asyncio.run` (verified: that raises `RuntimeError: asyncio.run() cannot be called from a running event loop`). `verify` is therefore `async`, awaits the cache directly, and does only CPU-bound crypto in between. It never calls `asyncio.run`.

- [ ] **Step 1: Write the shared auth fixtures**

```python
# services/api/tests/auth_fixtures.py
"""Local RSA keypair + JWKS document so the real RS256 path is exercised offline."""

import json

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

ISSUER = "https://issuer.test/"
AUDIENCE = "buyeros-api"
KID = "test-key-1"

_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_public_jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(_private_key.public_key()))
_public_jwk.update({"kid": KID, "use": "sig", "alg": "RS256"})


def jwks_document() -> dict:
    return {"keys": [dict(_public_jwk)]}


def make_token(*, sub="auth0|member", iss=ISSUER, aud=AUDIENCE, exp=9999999999, nbf=None, kid=KID, alg="RS256", key=None):
    claims = {"iss": iss, "aud": aud, "exp": exp, "sub": sub}
    if nbf is not None:
        claims["nbf"] = nbf
    headers = {"kid": kid} if kid is not None else {}
    return jwt.encode(claims, key or _private_key, algorithm=alg, headers=headers)
```

- [ ] **Step 2: Write the failing test**

```python
# services/api/tests/test_auth_tenant.py
import asyncio

import pytest

from buyeros_api.api.auth import AuthError, Principal
from buyeros_api.api.jwks import JwksKeyCache
from buyeros_api.api.verifier import TokenVerifier
from tests import auth_fixtures as fx


def _verifier():
    cache = JwksKeyCache(lambda: asyncio.sleep(0, result=fx.jwks_document()), cache_seconds=300)
    return TokenVerifier(cache, issuer=fx.ISSUER, audience=fx.AUDIENCE)


def _verify(token):
    """Drive the async verifier from a sync test without a running loop."""
    return asyncio.run(_verifier().verify(token))


def test_valid_token_yields_principal():
    principal = _verify(fx.make_token(sub="auth0|member"))
    assert principal == Principal(issuer=fx.ISSUER, subject="auth0|member")


def test_wrong_issuer_rejected():
    with pytest.raises(AuthError):
        _verify(fx.make_token(iss="https://other.test/"))


def test_wrong_audience_rejected():
    with pytest.raises(AuthError):
        _verify(fx.make_token(aud="other-api"))


def test_expired_token_rejected():
    with pytest.raises(AuthError):
        _verify(fx.make_token(exp=100))


def test_future_nbf_rejected():
    with pytest.raises(AuthError):
        _verify(fx.make_token(nbf=9999999999))


def test_unknown_kid_rejected():
    with pytest.raises(AuthError):
        _verify(fx.make_token(kid="not-in-jwks"))


def test_missing_kid_rejected():
    with pytest.raises(AuthError):
        _verify(fx.make_token(kid=None))


def test_forged_signature_rejected():
    from cryptography.hazmat.primitives.asymmetric import rsa

    attacker = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with pytest.raises(AuthError):
        _verify(fx.make_token(key=attacker))


def test_alg_none_rejected():
    unsigned = "eyJhbGciOiJub25lIiwia2lkIjoidGVzdC1rZXktMSJ9.eyJpc3MiOiJodHRwczovL2lzc3Vlci50ZXN0LyJ9."
    with pytest.raises(AuthError):
        _verify(unsigned)


def test_hs256_rejected():
    # A >=32-byte secret keeps PyJWT from emitting an InsecureKeyLengthWarning.
    with pytest.raises(AuthError):
        _verify(fx.make_token(alg="HS256", key="x" * 32))


def test_jwks_outage_with_no_cache_is_auth_error_not_a_bypass():
    async def failing():
        raise RuntimeError("network down")

    cache = JwksKeyCache(failing, cache_seconds=300)
    verifier = TokenVerifier(cache, issuer=fx.ISSUER, audience=fx.AUDIENCE)
    with pytest.raises(AuthError):
        asyncio.run(verifier.verify(fx.make_token()))
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_auth_tenant.py -v`
Expected: FAIL — `ModuleNotFoundError: buyeros_api.api.verifier`.

- [ ] **Step 4: Write minimal implementation**

```python
# services/api/buyeros_api/api/verifier.py
"""RS256 token verification over a JWKS cache (P10).

Enforces the algorithm allow-list and key selection, then defers claim rules to
the pure `claims_to_principal` so claim logic stays in one tested place.
"""

import httpx
import jwt

from .auth import AuthError, Principal, claims_to_principal, jwks_uri_for
from .jwks import JwksError, JwksKeyCache

ALLOWED_ALGORITHMS = ("RS256",)


async def fetch_jwks_document(jwks_uri: str) -> dict:
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(jwks_uri)
        response.raise_for_status()
        return response.json()


class TokenVerifier:
    def __init__(self, jwks_cache: JwksKeyCache, *, issuer: str, audience: str) -> None:
        self._jwks = jwks_cache
        self._issuer = issuer
        self._audience = audience

    async def verify(self, token: str) -> Principal:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise AuthError("malformed token") from exc
        if header.get("alg") not in ALLOWED_ALGORITHMS:
            raise AuthError("unsupported algorithm")
        kid = header.get("kid")
        if not kid:
            raise AuthError("missing key id")
        try:
            key = await self._jwks.get_key(kid)
        except JwksError as exc:
            raise AuthError("key set unavailable") from exc
        try:
            claims = jwt.decode(
                token,
                key,
                algorithms=list(ALLOWED_ALGORITHMS),
                options={"verify_aud": False, "verify_iss": False},
            )
        except jwt.PyJWTError as exc:
            raise AuthError("signature verification failed") from exc
        return claims_to_principal(claims, issuer=self._issuer, audience=self._audience)


def default_verifier(settings) -> TokenVerifier:
    uri = jwks_uri_for(settings.auth0_issuer)
    return TokenVerifier(
        JwksKeyCache(lambda: fetch_jwks_document(uri), cache_seconds=settings.jwks_cache_seconds),
        issuer=settings.auth0_issuer,
        audience=settings.auth0_audience,
    )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_auth_tenant.py -v`
Expected: PASS (11 passed).

- [ ] **Step 6: Commit**

```bash
git add services/api/buyeros_api/api/verifier.py services/api/tests/auth_fixtures.py services/api/tests/test_auth_tenant.py
git commit -m "feat(api): verify RS256 bearer tokens against a JWKS cache"
```

---

### Task 4: Wire verification into the request path

**Files:**
- Modify: `services/api/buyeros_api/api/auth.py`
- Modify: `services/api/tests/test_api_auth.py`

**Interfaces:**
- Consumes: `TokenVerifier`, `default_verifier` (Task 3).
- Produces: `get_principal` that verifies real tokens; the unconfigured case still returns `401` before any verification. `claims_to_principal` and `principal_from_token` keep their P9 signatures (the latter still fails closed).

**Note on the async path:** `get_principal` is already `async`, and `TokenVerifier.verify` is async (Task 3), so the handler simply awaits it. There is no thread offload and no `asyncio.run` anywhere in the request path — verification is CPU-bound crypto plus a cache lookup that is async only because of the JWKS fetch. Keep the existing `principal_from_token` name and signature as the test seam P9 established.

- [ ] **Step 1: Write the failing test**

Append to `services/api/tests/test_api_auth.py`:

```python
def test_get_principal_verifies_a_real_token(monkeypatch):
    import asyncio

    from fastapi import Depends
    from fastapi.testclient import TestClient

    from buyeros_api.api import auth
    from buyeros_api.api.app import create_app
    from buyeros_api.api.jwks import JwksKeyCache
    from buyeros_api.api.verifier import TokenVerifier
    from tests import auth_fixtures as fx

    monkeypatch.setenv("BUYEROS_AUTH0_ISSUER", fx.ISSUER)
    monkeypatch.setenv("BUYEROS_AUTH0_AUDIENCE", fx.AUDIENCE)
    from buyeros_api.settings import get_settings

    get_settings.cache_clear()

    cache = JwksKeyCache(lambda: asyncio.sleep(0, result=fx.jwks_document()), cache_seconds=300)
    monkeypatch.setattr(auth, "_verifier_from_settings", lambda: TokenVerifier(cache, issuer=fx.ISSUER, audience=fx.AUDIENCE))

    app = create_app()

    @app.get("/whoami")
    async def whoami(principal: auth.Principal = Depends(auth.get_principal)):
        return {"data": {"subject": principal.subject}, "request_id": "x", "data_mode": "live"}

    try:
        good = TestClient(app).get("/whoami", headers={"Authorization": f"Bearer {fx.make_token()}"})
        assert good.status_code == 200
        assert good.json()["data"]["subject"] == "auth0|member"

        bad = TestClient(app, raise_server_exceptions=False).get(
            "/whoami", headers={"Authorization": f"Bearer {fx.make_token(iss='https://other.test/')}"}
        )
        assert bad.status_code == 401
        assert bad.json()["code"] == "UNAUTHENTICATED"
        assert "other.test" not in bad.text
    finally:
        get_settings.cache_clear()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_api_auth.py::test_get_principal_verifies_a_real_token -v`
Expected: FAIL — `AttributeError: module 'buyeros_api.api.auth' has no attribute '_verifier_from_settings'`.

- [ ] **Step 3: Modify the implementation**

In `services/api/buyeros_api/api/auth.py`, keep `AuthError`, `Principal`, `jwks_uri_for`, `claims_to_principal` and `principal_from_token` exactly as they are. Add a verifier accessor and change `get_principal` to use it:

```python
def _verifier_from_settings():
    from ..settings import get_settings
    from .verifier import default_verifier

    return default_verifier(get_settings())


async def get_principal(request: Request) -> Principal:
    from .errors import ApiError

    settings = get_settings()
    if not settings.auth0_issuer or not settings.auth0_audience:
        raise ApiError(401, "UNAUTHENTICATED", "authentication is not configured")
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise ApiError(401, "UNAUTHENTICATED", "missing bearer token")
    try:
        return await _verifier_from_settings().verify(token.strip())
    except AuthError as exc:
        raise ApiError(401, "UNAUTHENTICATED", "token rejected") from exc
```

Note the final `except` maps to the fixed generic message `"token rejected"` — it must not interpolate `str(exc)`, because `exc` may name the failed check.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_api_auth.py -v`
Expected: PASS. All P9 auth tests must still pass unchanged; if any P9 test asserted the old literal message, update only the message expectation, not the behavior.

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest -q`
Expected: PASS (all prior tests plus the new ones).

- [ ] **Step 6: Commit**

```bash
git add services/api/buyeros_api/api/auth.py services/api/tests/test_api_auth.py
git commit -m "feat(api): verify bearer tokens in the request path"
```

---

### Task 5: Grant the runtime role SELECT on users

**Files:**
- Create: `services/api/alembic/versions/0008_grant_users_select.py`
- Modify: `services/api/tests/test_api_tenant_isolation.py`

**Interfaces:**
- Produces: migration `0008_grant_users_select` (down_revision `0007_outbox_terminal_state`) granting `SELECT ON users` to `buyeros_api` and `buyeros_worker`.
- Consumes: nothing.

- [ ] **Step 1: Write the migration**

```python
"""grant SELECT on users to the runtime roles

Revision ID: 0008_grant_users_select
Revises: 0007_outbox_terminal_state
Create Date: 2026-09-16

The API resolves an actor by reading `users` (never writing it), but no earlier
migration granted the NOBYPASSRLS runtime roles access to that table, so every
authenticated route failed with `permission denied for table users`. This is a
privilege grant only: no table, column, index or row is touched, and `users`
stays non-RLS to match `workspaces`.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0008_grant_users_select"
down_revision: str | None = "0007_outbox_terminal_state"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("GRANT SELECT ON users TO buyeros_api, buyeros_worker;")


def downgrade() -> None:
    op.execute("REVOKE SELECT ON users FROM buyeros_api, buyeros_worker;")
```

- [ ] **Step 2: Verify the migration applies and reverses**

Run (cwd `services/api`): `uv run pytest tests/test_tenant_isolation_db.py -q`
Expected: PASS — the `migrated` fixture applies all migrations through `0008`.

Then verify the runtime role can now read `users` (uses the disposable database from the fixture; run once, record output):

```bash
uv run python -c "
import psycopg, uuid, subprocess
name = 'buyeros-grant-check-' + uuid.uuid4().hex[:6]
subprocess.run(['docker','run','-d','--name',name,'-e','POSTGRES_PASSWORD=buyeros','-e','POSTGRES_USER=buyeros','-e','POSTGRES_DB=buyeros','-p','127.0.0.1::5432','postgres:16'],capture_output=True)
"
```

If Docker is unavailable, record the check as **NOT RUN** with that reason rather than skipping silently.

- [ ] **Step 3: Unskip the route-level isolation test**

In `services/api/tests/test_api_tenant_isolation.py`, remove the `@pytest.mark.skip(reason=...)` decorator from `test_route_tenant_scope_comes_from_the_membership_checked_path`. The test body is already correct; leave it otherwise unchanged.

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_api_tenant_isolation.py -v`
Expected: PASS (4 passed, 0 skipped) — the previously skipped route-level test now runs against real PostgreSQL under the runtime role.

- [ ] **Step 5: Commit**

```bash
git add services/api/alembic/versions/0008_grant_users_select.py services/api/tests/test_api_tenant_isolation.py
git commit -m "fix(api): grant runtime roles SELECT on users and unskip route isolation test"
```

---

### Task 6: Authenticated route acceptance tests

**Files:**
- Modify: `services/api/tests/test_api_tenant_isolation.py`
- Create: `services/api/tests/test_auth_routes_db.py`

**Interfaces:**
- Consumes: `auth_fixtures` (Task 3), `TokenVerifier` (Task 3), `0008` grant (Task 5), `seeded`/`runtime_role_dsn` fixtures.
- Produces: the three BO-004 acceptance tests against real PostgreSQL.

- [ ] **Step 1: Write the failing acceptance tests**

```python
# services/api/tests/test_auth_routes_db.py
"""BO-004 acceptance tests: a verified actor reaches real data only through membership."""

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
PROJECT_B = "b0000000-0000-4000-8000-000000000002"
MEMBER = "auth0|member-a"
VIEWER = "auth0|viewer-a"


@pytest.fixture
def auth_env(seeded, monkeypatch):
    """Point the app at a local verifier and the runtime-role database."""
    monkeypatch.setenv("BUYEROS_DATABASE_URL", runtime_role_dsn(seeded))
    monkeypatch.setenv("BUYEROS_AUTH0_ISSUER", fx.ISSUER)
    monkeypatch.setenv("BUYEROS_AUTH0_AUDIENCE", fx.AUDIENCE)
    from buyeros_api.settings import get_settings

    get_settings.cache_clear()

    cache = JwksKeyCache(lambda: asyncio.sleep(0, result=fx.jwks_document()), cache_seconds=300)
    monkeypatch.setattr(
        auth, "_verifier_from_settings", lambda: TokenVerifier(cache, issuer=fx.ISSUER, audience=fx.AUDIENCE)
    )

    owner = psycopg.connect(seeded, autocommit=True)
    for subject, roles in ((MEMBER, ["operator"]), (VIEWER, ["viewer"])):
        user_id = uuid.uuid5(uuid.NAMESPACE_URL, subject)
        owner.execute("DELETE FROM memberships WHERE user_id = %s", (user_id,))
        owner.execute("DELETE FROM users WHERE id = %s", (user_id,))
        owner.execute("INSERT INTO users(id, issuer, subject) VALUES (%s, %s, %s)", (user_id, fx.ISSUER, subject))
        owner.execute(
            "INSERT INTO memberships(id, workspace_id, user_id, roles, active) VALUES (%s, %s, %s, %s, true)",
            (uuid.uuid4(), WORKSPACE_A, user_id, roles),
        )
    owner.close()
    yield
    get_settings.cache_clear()
    owner = psycopg.connect(seeded, autocommit=True)
    for subject in (MEMBER, VIEWER):
        user_id = uuid.uuid5(uuid.NAMESPACE_URL, subject)
        owner.execute("DELETE FROM memberships WHERE user_id = %s", (user_id,))
        owner.execute("DELETE FROM users WHERE id = %s", (user_id,))
    owner.close()


def _client():
    return TestClient(create_app(), raise_server_exceptions=False)


def _headers(subject=MEMBER, **kwargs):
    return {"Authorization": f"Bearer {fx.make_token(sub=subject, **kwargs)}"}


def test_valid_member_reaches_only_its_own_workspace(auth_env):
    client = _client()
    ok = client.get(f"/v1/workspaces/{WORKSPACE_A}/projects", headers=_headers())
    assert ok.status_code == 200, ok.text
    assert {item["name"] for item in ok.json()["data"]["items"]} == {"ProjectA"}

    foreign = client.get(f"/v1/workspaces/{WORKSPACE_B}/projects", headers=_headers())
    assert foreign.status_code == 404
    assert "ProjectB" not in foreign.text


def test_forged_expired_and_wrong_audience_are_denied(auth_env):
    client = _client()
    path = f"/v1/workspaces/{WORKSPACE_A}/projects"
    for headers in (
        _headers(iss="https://other.test/"),
        _headers(aud="other-api"),
        _headers(exp=100),
        {"Authorization": "Bearer not-a-jwt"},
    ):
        response = client.get(path, headers=headers)
        assert response.status_code == 401, headers
        assert response.json()["code"] == "UNAUTHENTICATED"
        assert "oauth" not in response.text.lower()


def test_unknown_actor_is_a_non_enumerating_404(auth_env):
    client = _client()
    response = client.get(f"/v1/workspaces/{WORKSPACE_A}/projects", headers=_headers(sub="auth0|nobody"))
    assert response.status_code == 404
    assert "ProjectA" not in response.text


def test_viewer_cannot_mutate(auth_env):
    client = _client()
    response = client.post(
        f"/v1/workspaces/{WORKSPACE_A}/projects",
        headers={**_headers(VIEWER), "Idempotency-Key": "k-1"},
        json={"name": "Nope"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "PERMISSION_DENIED"


def test_foreign_project_id_is_hidden(auth_env):
    client = _client()
    response = client.get(f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_B}", headers=_headers())
    assert response.status_code == 404
    assert "ProjectB" not in response.text


def test_capabilities_and_errors_disclose_no_secrets(auth_env):
    client = _client()
    caps = client.get(f"/v1/workspaces/{WORKSPACE_A}/capabilities", headers=_headers())
    assert caps.status_code == 200
    body = caps.text.lower()
    for secret in ("password", "postgresql://", "bearer ", "auth0|"):
        assert secret not in body, secret

    denied = client.get(f"/v1/workspaces/{WORKSPACE_A}/projects", headers={"Authorization": "Bearer bogus"})
    assert denied.json()["message"] == "token rejected"
```

- [ ] **Step 2: Run tests to verify they fail**

Run (cwd `services/api`): `uv run pytest tests/test_auth_routes_db.py -v`
Expected: FAIL — the routes have no working verifier yet / grant not applied, so authentication does not succeed.

- [ ] **Step 3: Make them pass**

No new production code should be required: Tasks 3–5 already provide the verifier and the grant. If a test fails, the failure is a real defect in an earlier task — fix that task, not the test. If `test_capabilities_and_errors_disclose_no_secrets` fails on `"auth0|"`, the cause is an echo of the subject; investigate rather than relaxing the assertion.

- [ ] **Step 4: Run the full suite**

Run: `uv run pytest -q`
Expected: PASS (0 skipped unless Docker was unavailable for the DB tests, in which case report the skip count honestly).

- [ ] **Step 5: Commit**

```bash
git add services/api/tests/test_auth_routes_db.py
git commit -m "test(api): BO-004 authenticated route acceptance tests"
```

---

## Self-Review

- **Spec coverage:** A (Tasks 2, 3 — unit boundaries), B (Task 3 — algorithm allow-list, key selection, claims via `claims_to_principal`; Task 4 — unconfigured fail-closed preserved, generic message), C (Task 2 — TTL, rotation, single-refetch bound, outage, strict parsing; dependency note → Task 1), D (Task 5 — `0008_` SELECT-only grant, unskip), E (Task 6 — unknown actor 404), F (Tasks 2, 3, 5, 6 — all four test layers), G (recorded out of scope; no task, by design). Every spec section maps to a task.
- **Placeholder scan:** no `TBD`/`TODO`; every code step contains complete code. The Docker availability branch in Task 5 Step 2 is an explicit, named condition, not a placeholder.
- **Type consistency:** `JwksError`, `JwksKeyCache(fetch_jwks, *, cache_seconds, now)`, `async get_key(kid)`, `invalidate()`; `TokenVerifier(jwks_cache, *, issuer, audience)`, `async verify(token) -> Principal`, `default_verifier(settings)`; `auth._verifier_from_settings()` is the monkeypatch seam used by Tasks 4 and 6. `Principal(issuer, subject)` and `claims_to_principal(claims, *, issuer, audience, now)` are unchanged from P9 and used consistently.
- **Async path verified:** `JwksKeyCache.get_key` and `TokenVerifier.verify` are both async and `get_principal` awaits them, so recommended verification runs inside the route's existing event loop with no nested-loop hazard. This was corrected during planning after verifying that a synchronous `verify` calling `asyncio.run` raises `RuntimeError: asyncio.run() cannot be called from a running event loop` when invoked from an async route (which every P9 route is).

### Verified against the real dependency

The crypto assumptions in this plan were checked against the actual resolved packages (`pyjwt 2.14.0`, `cryptography 50.0.1`) before writing, not assumed:

- `jwt.algorithms.RSAAlgorithm.from_jwk(jwk)` returns an `RSAPublicKey` and accepts a JWK carrying `kid`/`use`/`alg`. (`to_jwk` emits `n`/`e`/`kty`/`key_ops`; the fixtures add `kid`/`use`/`alg`.)
- An `EC` entry and an RSA entry missing `n`/`e` both raise `InvalidKeyError` (a `ValueError`), which the implementation's `except (ValueError, TypeError, KeyError)` catches — malformed entries are skipped, not coerced.
- `jwt.decode(..., algorithms=["RS256"], options={"verify_aud": False, "verify_iss": False})` succeeds and defers `iss`/`aud` to `claims_to_principal`.
- `HS256` and `alg: none` both raise `InvalidAlgorithmError` under that allow-list, so the allow-list genuinely blocks them (asserted by `test_hs256_rejected` and `test_alg_none_rejected`).
- `jwt.get_unverified_header` exposes `alg` and `kid`.
- A synchronous `verify` bridging to the async cache with `asyncio.run` **fails** from an async route (`RuntimeError: asyncio.run() cannot be called from a running event loop`). The plan's `verify`/`get_key` are therefore async and the route awaits them; this was confirmed working end-to-end (a signed token verifies through an async FastAPI route, a bad token is rejected) in a scratch environment before the plan was finalized.

## Global Notes

- No remote commits/pushes, deploys, cloud resources, real-data migrations, provider calls, or sends.
- Record exact command output in `PROGRESS.md`; every unexecuted check is **NOT RUN**.
- Execution requires a recorded dependency waiver (BO-003/BO-004 prerequisites) and may use `superpowers:subagent-driven-development` or `superpowers:executing-plans`.
