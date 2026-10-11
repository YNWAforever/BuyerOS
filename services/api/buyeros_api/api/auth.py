import time
import math
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
    now = time.time() if now is None else now
    if not isinstance(claims,dict) or not isinstance(claims.get("iss"),str) or claims.get("iss") != issuer:
        raise AuthError("bad issuer")
    aud = claims.get("aud")
    if isinstance(aud,list):
        if not aud or not all(isinstance(item,str) and item for item in aud) or audience not in aud:
            raise AuthError("bad audience")
    elif not isinstance(aud,str) or aud != audience:
        raise AuthError("bad audience")
    def numeric_date(name):
        value=claims.get(name)
        if type(value) not in (int,float):raise AuthError("bad "+name)
        try:
            if not math.isfinite(value):raise AuthError("bad "+name)
        except (OverflowError,TypeError,ValueError) as error:raise AuthError("bad "+name) from error
        return value
    if numeric_date("exp") <= now:raise AuthError("expired")
    if "nbf" in claims and numeric_date("nbf") > now+60:raise AuthError("token not yet valid")
    if "iat" in claims:numeric_date("iat")
    subject=claims.get("sub")
    if not isinstance(subject,str) or not 0<len(subject)<=255 or subject!=subject.strip() or any(ord(c)<32 or ord(c)==127 for c in subject):
        raise AuthError("bad subject")
    return Principal(issuer=issuer,subject=subject)


_VERIFIER = None
_VERIFIER_KEY: tuple | None = None


def _verifier_from_settings():
    """One verifier per process, so its JWKS cache is shared rather than rebuilt per request.

    Building a verifier per call would give every request a cold cache and therefore a JWKS
    fetch, defeating the cache entirely. The key includes the settings the verifier derives
    from, so a configuration change (or a test that swaps env) builds a fresh one.
    """
    global _VERIFIER, _VERIFIER_KEY

    from ..settings import get_settings
    from .verifier import default_verifier

    settings = get_settings()
    key = (settings.auth_mode,settings.auth0_issuer,settings.auth0_audience,
           settings.neon_issuer,settings.neon_audience,settings.neon_jwks_url,
           settings.neon_expected_issuer,settings.neon_expected_audience,
           settings.neon_expected_jwks_url,settings.auth_migration_expires_at,
           settings.environment,settings.jwks_cache_seconds,settings.jwks_max_stale_seconds)
    if _VERIFIER is None or _VERIFIER_KEY != key:
        _VERIFIER = default_verifier(settings)
        _VERIFIER_KEY = key
    return _VERIFIER


async def get_principal(request: Request) -> Principal:
    from .errors import ApiError

    settings = get_settings()
    if settings.auth_mode=="auth0" and (not settings.auth0_issuer or not settings.auth0_audience):
        raise ApiError(401, "UNAUTHENTICATED", "authentication is not configured")
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise ApiError(401, "UNAUTHENTICATED", "missing bearer token")
    try:
        return await _verifier_from_settings().verify(token.strip())
    except AuthError as exc:
        raise ApiError(401, "UNAUTHENTICATED", "token rejected") from exc
