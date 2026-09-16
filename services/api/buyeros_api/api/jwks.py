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
        min_refetch_seconds: int = 10,
        now: Callable[[], float] = time.monotonic,
    ) -> None:
        self._fetch_jwks = fetch_jwks
        self._cache_seconds = cache_seconds
        self._min_refetch_seconds = min_refetch_seconds
        self._now = now
        self._keys: dict[str, object] = {}
        self._fetched_at: float | None = None
        self._last_attempt_at: float | None = None
        self._lock = asyncio.Lock()

    def _fresh(self) -> bool:
        return self._fetched_at is not None and (self._now() - self._fetched_at) < self._cache_seconds

    def _cooldown_elapsed(self) -> bool:
        return self._last_attempt_at is None or (self._now() - self._last_attempt_at) >= self._min_refetch_seconds

    def invalidate(self) -> None:
        self._fetched_at = None

    async def _refetch(self, seen_attempt: float | None) -> None:
        async with self._lock:
            # Another caller already refetched (or tried) while we waited for the lock.
            if self._last_attempt_at != seen_attempt:
                return
            self._last_attempt_at = self._now()
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
        # Unknown kid with a fresh cache is the rotation path: allow one refetch, but
        # rate-limit it so a stream of bogus kids cannot hammer the identity provider.
        # A stale cache always gets its refresh attempt.
        if self._fresh() and not self._cooldown_elapsed():
            raise JwksError("key id unknown and refresh is rate limited")
        seen_attempt = self._last_attempt_at
        try:
            await self._refetch(seen_attempt)
        except Exception as exc:  # noqa: BLE001 - any fetch failure is an auth failure
            if kid in self._keys:
                return self._keys[kid]  # outage: serve a previously fetched key
            raise JwksError("key set unavailable") from exc
        if kid not in self._keys:
            raise JwksError("unknown key id")
        return self._keys[kid]
