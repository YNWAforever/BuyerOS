"""Owned loopback EdDSA diagnostic only; no BuyerOS DB/membership/domain API."""
import hashlib
import json
import os
import re
import time
from datetime import datetime
from urllib.parse import urlparse
import httpx
import jwt
from fastapi import FastAPI, Header, HTTPException
import uvicorn
def read_configuration(env):
    if env.get("N00_FLOW_FIXTURE")!="yes":raise ValueError("N00_DIAGNOSTIC_FIXTURE_REQUIRED")
    manifest=json.loads(env["N00_REAL_TARGET_JSON"])
    stable=json.loads(json.dumps(manifest));stable["readback"].pop("observedAt")
    fingerprint=hashlib.sha256(json.dumps(stable,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
    auth=manifest["auth"]
    for field,key in [("issuer","N00_AUTH_ISSUER"),("audience","N00_AUTH_AUDIENCE"),("jwksUrl","N00_AUTH_JWKS_URL"),("baseUrl","NEON_AUTH_BASE_URL"),("algorithm","N00_AUTH_ALGORITHM")]:
        if auth[field]!=env.get(key):raise ValueError("N00_DIAGNOSTIC_CONTEXT")
    if fingerprint!=env.get("N00_TARGET_FINGERPRINT") or fingerprint!=env.get("N00_DIAGNOSTIC_FINGERPRINT"):raise ValueError("N00_DIAGNOSTIC_CONTEXT")
    if not all(manifest[k].startswith("fictional-probe-") for k in ("projectId","branchId","authId")):raise ValueError("N00_DIAGNOSTIC_FIXTURE_REQUIRED")
    if any(urlparse(auth[k]).scheme!="https" or not urlparse(auth[k]).hostname.endswith(".fixture.invalid") for k in ("issuer","baseUrl","jwksUrl")):raise ValueError("N00_DIAGNOSTIC_FIXTURE_REQUIRED")
    if auth["algorithm"]!="EdDSA" or auth["keyType"]!="OKP" or auth["curve"]!="Ed25519":raise ValueError("N00_DIAGNOSTIC_TRUST")
    created=datetime.fromisoformat(manifest["createdAt"].replace("Z","+00:00")).timestamp()
    expires=datetime.fromisoformat(manifest["expiresAt"].replace("Z","+00:00")).timestamp()
    nonce=env.get("N00_DIAGNOSTIC_NONCE","")
    if not created<=time.time()<expires or expires-created!=7200 or not re.fullmatch(r"[-_a-zA-Z0-9]{43,128}",nonce):raise ValueError("N00_DIAGNOSTIC_SCOPE")
    return {"issuer":auth["issuer"],"audience":auth["audience"],"fingerprint":fingerprint,"expires":expires,"nonce":nonce}
def verify_token(token,config,keys):
    try:
        if time.time()>=config["expires"]:raise ValueError("Target expired")
        header=jwt.get_unverified_header(token)
        if header.get("alg")!="EdDSA" or not header.get("kid"):raise ValueError("Algorithm/key refused")
        matching=[key for key in keys if key.get("kid")==header["kid"] and key.get("alg")=="EdDSA" and key.get("kty")=="OKP" and key.get("crv")=="Ed25519" and key.get("use")=="sig"]
        if len(matching)!=1:raise ValueError("Key refused")
        claims=jwt.decode(token,jwt.PyJWK.from_dict(matching[0]).key,algorithms=["EdDSA"],issuer=config["issuer"],audience=config["audience"],options={"require":["sub","iss","aud","exp","iat"],"strict_aud":True})
        if not isinstance(claims["sub"],str) or not claims["sub"]:raise ValueError("Subject refused")
        return claims["sub"]
    except (jwt.PyJWTError,KeyError,TypeError) as error:raise ValueError("N00 token refused") from error
def create_app(config):
    app=FastAPI()
    @app.get("/verify")
    async def verify(authorization:str|None=Header(default=None),x_n00_owner:str|None=Header(default=None)):
        if x_n00_owner!=config["nonce"]:raise HTTPException(403,"Owner required")
        if not authorization or not authorization.startswith("Bearer "):raise HTTPException(401,"Bearer required")
        try:
            async with httpx.AsyncClient(trust_env=False,follow_redirects=False) as client:
                response=await client.get("http://127.0.0.1:44891/fixture/auth/jwks",timeout=3)
                response.raise_for_status()
            subject=verify_token(authorization[7:],config,response.json()["keys"])
        except (ValueError,KeyError,httpx.HTTPError) as error:raise HTTPException(401,"N00 token refused") from error
        return {"subject":subject,"fingerprint":config["fingerprint"],"protocol_fixture_only":True}
    return app
if __name__=="__main__":
    try:configuration=read_configuration(os.environ)
    except Exception:raise SystemExit("N00_DIAGNOSTIC_CONFIGURATION_REFUSED")
    uvicorn.run(create_app(configuration),host="127.0.0.1",port=44892,access_log=False)
