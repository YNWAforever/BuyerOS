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
