"""N00 loopback protocol diagnostic. No BuyerOS DB or membership access."""
import jwt
import httpx
import uvicorn
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
ISSUER = "http://127.0.0.1:44891"
AUDIENCE = "http://127.0.0.1:44891"
JWKS_URL = "http://127.0.0.1:44891/fixture/auth/.well-known/jwks.json"
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:44890"], allow_methods=["GET"], allow_headers=["Authorization"])
@app.get("/verify")
async def verify(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Bearer required")
    token = authorization[7:]
    try:
        header = jwt.get_unverified_header(token)
        if header.get("alg") != "EdDSA":
            raise ValueError("Algorithm refused")
        async with httpx.AsyncClient(trust_env=False) as client:
            response = await client.get(JWKS_URL, timeout=3)
            response.raise_for_status()
        key = next(k for k in response.json()["keys"] if k.get("kid") == header.get("kid") and k.get("alg") == "EdDSA" and k.get("kty") == "OKP" and k.get("crv") == "Ed25519")
        claims = jwt.decode(token, jwt.PyJWK.from_dict(key).key, algorithms=["EdDSA"], issuer=ISSUER, audience=AUDIENCE, options={"require":["sub","iss","aud","exp","iat"]})
    except (jwt.PyJWTError, ValueError, StopIteration, httpx.HTTPError) as error:
        raise HTTPException(401, "N00 token refused") from error
    return {"subject":claims["sub"], "protocol_fixture_only":True}
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=44892)
