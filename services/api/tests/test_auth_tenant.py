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


def test_token_within_the_nbf_skew_is_accepted():
    # spec section B allows nbf up to now + 60s. PyJWT's default nbf check would reject this outright, so a
    # green here is what proves claims_to_principal owns nbf rather than the library.
    import time

    principal = _verify(fx.make_token(nbf=int(time.time()) + 30))
    assert principal.subject == "auth0|member"


def test_nbf_beyond_the_skew_is_rejected():
    import time

    with pytest.raises(AuthError):
        _verify(fx.make_token(nbf=int(time.time()) + 600))


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
