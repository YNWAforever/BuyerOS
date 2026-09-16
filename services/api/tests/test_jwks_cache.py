import asyncio
import json

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from buyeros_api.api.jwks import JwksError, JwksKeyCache

# A real key: `from_jwk` rejects a hand-written modulus that is not > the exponent.
_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_PUBLIC_JWK = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(_KEY.public_key()))


def _entry(kid: str) -> dict:
    return {**_PUBLIC_JWK, "kid": kid, "use": "sig"}


def _doc(*kids: str) -> dict:
    return {"keys": [_entry(kid) for kid in kids]}


class Clock:
    """Mutable clock so tests can cross the TTL and the refetch cooldown."""

    def __init__(self, t: float = 1000.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t


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
    cache = JwksKeyCache(fetcher, now=Clock())
    assert asyncio.run(cache.get_key("k1")) is not None
    assert asyncio.run(cache.get_key("k1")) is not None
    assert fetcher.calls == 1


def test_unknown_kid_refetches_once_for_rotation():
    clock = Clock()
    fetcher = Fetcher(_doc("k1"), _doc("k1", "k2"))
    cache = JwksKeyCache(fetcher, now=clock)
    asyncio.run(cache.get_key("k1"))
    clock.t += 11  # past the refetch cooldown
    assert asyncio.run(cache.get_key("k2")) is not None
    assert fetcher.calls == 2


def test_unknown_kid_is_rate_limited_so_it_cannot_hammer_the_provider():
    clock = Clock()
    fetcher = Fetcher(_doc("k1"))
    cache = JwksKeyCache(fetcher, now=clock)
    asyncio.run(cache.get_key("k1"))  # calls == 1
    clock.t += 11
    for _ in range(3):
        with pytest.raises(JwksError):
            asyncio.run(cache.get_key("nope"))
    # exactly one rotation refetch for all three attempts, never one per attempt
    assert fetcher.calls == 2


def test_stale_entry_refetches_and_picks_up_new_keys():
    clock = Clock()
    fetcher = Fetcher(_doc("k1"), _doc("k1", "k2"))
    cache = JwksKeyCache(fetcher, now=clock)
    asyncio.run(cache.get_key("k1"))
    clock.t += 301  # past cache_seconds
    assert asyncio.run(cache.get_key("k2")) is not None
    assert fetcher.calls == 2


def test_outage_serves_a_previously_fetched_key():
    clock = Clock()
    fetcher = Fetcher(_doc("k1"))
    cache = JwksKeyCache(fetcher, now=clock)
    asyncio.run(cache.get_key("k1"))
    clock.t += 301  # stale, so the next lookup must attempt a refresh
    fetcher.error = RuntimeError("network down")
    assert asyncio.run(cache.get_key("k1")) is not None


def test_outage_with_no_cached_key_raises_rather_than_bypassing():
    fetcher = Fetcher(_doc("k1"))
    fetcher.error = RuntimeError("network down")
    cache = JwksKeyCache(fetcher, now=Clock())
    with pytest.raises(JwksError):
        asyncio.run(cache.get_key("k1"))


def test_malformed_entries_are_skipped_without_failing_the_set():
    def document():
        return {
            "keys": [
                {"kty": "EC", "kid": "ec", "crv": "P-256", "x": "a", "y": "b"},
                {"kty": "RSA", "kid": "no-material"},
                _entry("good"),
            ]
        }

    fetcher = Fetcher(document())
    cache = JwksKeyCache(fetcher, now=Clock())
    with pytest.raises(JwksError):
        asyncio.run(cache.get_key("ec"))
    # the malformed entries did not abort the fetch: the good key is usable
    assert asyncio.run(cache.get_key("good")) is not None
