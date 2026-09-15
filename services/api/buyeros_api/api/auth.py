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
