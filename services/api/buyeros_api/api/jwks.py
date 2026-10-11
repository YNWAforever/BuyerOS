"""JWKS fetch/cache/rotation for RS256 verification (P10).

The only stateful, network-touching unit in the auth path. Given a `kid` it
returns a usable public key or raises - it never returns an empty set and never
skips verification, so a JWKS outage can never become a signature bypass.
"""

import asyncio
import time
from concurrent.futures import Future
from threading import Lock
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
    if entry.get("kty") != "RSA" or entry.get("alg") not in (None,"RS256") or "d" in entry:
        return None
    if entry.get("use") not in (None, "sig"):
        return None
    if entry.get("key_ops") is not None and entry["key_ops"] != ["verify"]:
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
        key_parser: Callable[[dict], object | None] = _public_key,
    ) -> None:
        self._fetch_jwks = fetch_jwks
        self._key_parser = key_parser
        if cache_seconds <= 0 or max_stale_seconds <= 0 or min_refetch_seconds <= 0:
            raise ValueError("JWKS cache intervals must be positive")
        self._cache_seconds = cache_seconds
        self._max_stale_seconds = max_stale_seconds
        self._min_refetch_seconds = min_refetch_seconds
        self._now = now
        self._keys: dict[str, object] = {}
        self._fetched_at: float | None = None
        self._last_attempt_at: float | None = None
        self._lock = Lock()
        self._inflight: Future | None = None

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
        # A cache can be shared by ASGI requests on different event loops. Keep
        # only short synchronous state changes under a thread lock; marshal a
        # single fetch result to each waiter's own loop through wrap_future.
        with self._lock:
            future = self._inflight
            owner = future is None
            if owner:
                if self._last_attempt_at != seen_attempt or not self._cooldown_elapsed():
                    return
                future = Future()
                self._inflight = future
                self._last_attempt_at = self._now()
        if not owner:
            # Cancelling one request must not cancel the shared completion or
            # strand another signed request waiting for the same key set.
            await asyncio.shield(asyncio.wrap_future(future))
            return
        try:
            document = await self._fetch_jwks()
            if not isinstance(document,dict) or not isinstance(document.get("keys"),list):
                raise JwksError("invalid key set")
            keys: dict[str, object] = {}
            for entry in document.get("keys", []):
                if not isinstance(entry, dict):
                    continue
                kid = entry.get("kid")
                if not isinstance(kid,str) or not 0<len(kid)<=255:
                    continue
                key = self._key_parser(entry)
                if key is not None:
                    if kid in keys:raise JwksError("ambiguous key id")
                    keys[kid] = key
            with self._lock:
                # Empty rotation retains existing keys under their old hard
                # ceiling, exactly as before; it never extends stale trust.
                if keys or not self._keys:
                    self._keys = keys
                    self._fetched_at = self._now()
        except BaseException as exc:
            # Owner cancellation remains cancellation for that request, while
            # other requests receive a fail-closed fetch error and can finish.
            future.set_exception(exc if isinstance(exc, Exception) else JwksError("key fetch interrupted"))
            raise
        else:
            future.set_result(None)
        finally:
            with self._lock:
                if self._inflight is future:
                    self._inflight = None

    async def get_key(self, kid: str):
        if not isinstance(kid,str) or not 0<len(kid)<=255:raise JwksError("invalid key id")
        if kid in self._keys and self._fresh():
            return self._keys[kid]
        # Every refetch is rate limited, not just the unknown-kid one: an outage keeps the
        # cache permanently stale, so without this a bogus kid would drive one fetch per request.
        # A concurrent cold miss must join the existing shared fetch completion.
        # Recheck cooldown while claiming ownership; joining never starts another fetch.
        with self._lock:
            fetching = self._inflight is not None
        if self._cooldown_elapsed() or fetching:
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
