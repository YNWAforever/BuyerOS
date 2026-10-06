"""JWKS fetch/cache/rotation for RS256 verification (P10).

The only stateful, network-touching unit in the auth path. Given a `kid` it
returns a usable public key or raises - it never returns an empty set and never
skips verification, so a JWKS outage can never become a signature bypass.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable

import jwt


class JwksError(Exception):
    pass


def _public_key(entry: dict):
    """Build an RSA public key from one JWK entry, or None if it is not usable.

    Catches ``jwt.PyJWTError`` deliberately: ``InvalidKeyError`` derives from it
    alone (not from ValueError/KeyError), so a malformed entry must be caught here
    or it would abort the whole fetch and empty the key set.
    """
    if not isinstance(entry, dict):
        return None
    if entry.get("kty") != "RSA":
        return None
    if entry.get("use") not in (None, "sig"):
        return None
    try:
        return jwt.algorithms.RSAAlgorithm.from_jwk(entry)
    except (jwt.PyJWTError, ValueError, TypeError, KeyError):
        return None


class JwksKeyCache:
    """Per-process key cache: TTL hit, rate-limited refetch on unknown kid, fail closed."""

    def __init__(
        self,
        fetch_jwks: Callable[[], Awaitable[dict]],
        *,
        cache_seconds: int = 300,
        max_stale_seconds: int = 3600,
        min_refetch_seconds: int = 10,
        now: Callable[[], float] = time.monotonic,
    ) -> None:
        self._fetch_jwks = fetch_jwks
        if cache_seconds <= 0 or max_stale_seconds <= 0 or min_refetch_seconds <= 0:
            raise ValueError("JWKS cache intervals must be positive")
        self._cache_seconds = cache_seconds
        self._max_stale_seconds = max_stale_seconds
        self._min_refetch_seconds = min_refetch_seconds
        self._now = now
        self._keys: dict[str, object] = {}
        self._fetched_at: float | None = None
        self._last_attempt_at: float | None = None
        self._lock = asyncio.Lock()

    def _age(self) -> float | None:
        return None if self._fetched_at is None else self._now() - self._fetched_at

    def _within_hard_ceiling(self) -> bool:
        age = self._age()
        return age is not None and 0 <= age < self._max_stale_seconds

    def _fresh(self) -> bool:
        age = self._age()
        return age is not None and 0 <= age < self._cache_seconds and self._within_hard_ceiling()

    def _cooldown_elapsed(self) -> bool:
        return self._last_attempt_at is None or (self._now() - self._last_attempt_at) >= self._min_refetch_seconds

    def invalidate(self) -> None:
        self._fetched_at = None

    async def _refetch(self, seen_attempt: float | None) -> None:
        async with self._lock:
            # Another caller already refetched (or tried) while we waited for the lock.
            if self._last_attempt_at != seen_attempt or not self._cooldown_elapsed():
                return
            self._last_attempt_at = self._now()
            document = await self._fetch_jwks()
            keys: dict[str, object] = {}
            for entry in document.get("keys", []):
                if not isinstance(entry, dict):
                    continue
                kid = entry.get("kid")
                if not kid:
                    continue
                key = _public_key(entry)
                if key is not None:
                    keys[kid] = key
            # An empty-but-valid response is not a successful rotation: keep the keys we hold
            # rather than letting a provider misconfiguration wipe every published key.
            if keys or not self._keys:
                self._keys = keys
                self._fetched_at = self._now()

    async def get_key(self, kid: str):
        if kid in self._keys and self._fresh():
            return self._keys[kid]
        # Every refetch is rate limited, not just the unknown-kid one: an outage keeps the
        # cache permanently stale, so without this a bogus kid would drive one fetch per request.
        # A concurrent cold miss must join the fetch already holding this lock.
        # Recheck cooldown under the lock, so joining never performs another fetch.
        if self._cooldown_elapsed() or self._lock.locked():
            seen_attempt = self._last_attempt_at
            try:
                await self._refetch(seen_attempt)
            except Exception as exc:  # noqa: BLE001 - any fetch failure is an auth failure
                if kid not in self._keys:
                    raise JwksError("key set unavailable") from exc
        if kid not in self._keys:
            raise JwksError("unknown key id")
        if not self._within_hard_ceiling():
            raise JwksError("cached key exceeded hard staleness ceiling")
        return self._keys[kid]
