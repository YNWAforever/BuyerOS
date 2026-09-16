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
                # Signature and algorithm only. Every claim rule (iss/aud/exp/nbf/sub) is owned by
                # claims_to_principal, so PyJWT's own claim checks must be off: its default exp/nbf
                # verification would reject a token inside the spec's 60s nbf skew before our rules
                # ever run, and would put exp/nbf ownership in two places at once.
                options={
                    "verify_aud": False,
                    "verify_iss": False,
                    "verify_exp": False,
                    "verify_nbf": False,
                    "verify_iat": False,
                },
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
