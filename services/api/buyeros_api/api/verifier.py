"""RS256 token verification over a JWKS cache (P10).

Enforces the algorithm allow-list and key selection, then defers claim rules to
the pure `claims_to_principal` so claim logic stays in one tested place.
"""

import httpx
import jwt

from .auth import AuthError, Principal, claims_to_principal, jwks_uri_for
from .jwks import JwksError, JwksKeyCache
from .auth_trust import TrustConfig,TrustSetVerifier,public_key_for,trusts_from_settings

ALLOWED_ALGORITHMS = ("RS256",)


async def fetch_jwks_document(jwks_uri: str) -> dict:
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(jwks_uri)
        response.raise_for_status()
        return response.json()


class TokenVerifier:
    def __init__(self, jwks_cache: JwksKeyCache, *, issuer: str | None = None, audience: str | None = None, trust: TrustConfig | None = None) -> None:
        if trust is not None:
            if issuer is not None or audience is not None:raise ValueError("one explicit trust source required")
            issuer,audience=trust.issuer,trust.audience
        self._jwks = jwks_cache
        self._issuer = issuer
        self._audience = audience
        self._algorithms = trust.algorithms if trust else ALLOWED_ALGORITHMS

    @property
    def issuer(self):return self._issuer

    async def verify(self, token: str) -> Principal:
        if not isinstance(token,str) or not 0<len(token)<=16384:raise AuthError("malformed token")
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise AuthError("malformed token") from exc
        if header.get("alg") not in self._algorithms:
            raise AuthError("unsupported algorithm")
        if any(name in header for name in ("jku","x5u","jwk","crit","b64")):raise AuthError("unsupported key header")
        kid = header.get("kid")
        if not isinstance(kid,str) or not 0<len(kid)<=255 or kid!=kid.strip() or any(ord(c)<32 or ord(c)==127 for c in kid):
            raise AuthError("missing key id")
        try:
            key = await self._jwks.get_key(kid)
        except JwksError as exc:
            raise AuthError("key set unavailable") from exc
        try:
            claims = jwt.decode(
                token,
                key,
                algorithms=list(self._algorithms),
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
                    "verify_sub": False,
                },
            )
        except (jwt.PyJWTError,ValueError,TypeError) as exc:
            raise AuthError("signature verification failed") from exc
        return claims_to_principal(claims, issuer=self._issuer, audience=self._audience)


def default_verifier(settings):
    trusts=trusts_from_settings(settings)
    verifiers=[]
    for trust in trusts:
        cache=JwksKeyCache(
            lambda trust=trust:fetch_jwks_document(trust.jwks_url),
            cache_seconds=settings.jwks_cache_seconds,
            max_stale_seconds=settings.jwks_max_stale_seconds,
            key_parser=lambda entry,trust=trust:public_key_for(trust,entry),
        )
        verifiers.append(TokenVerifier(cache,trust=trust))
    if settings.auth_mode=="auth0":return verifiers[0]
    deadline=int(settings.auth_migration_expires_at) if settings.auth_mode=="dual" else None
    return TrustSetVerifier(verifiers,expires_at=deadline)
