"""Protocol-only N00 configuration and crypto tests; no conftest/DB fixtures."""
import importlib.util
import json
import time
from pathlib import Path
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import jwt
def subject_module():
    path=Path(__file__).with_name("verify.py")
    assert path.exists(), "runtime-bound verifier is not implemented"
    spec=importlib.util.spec_from_file_location("n00_runtime_verifier",path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module
def config():
    now=time.time()
    return {"issuer":"https://explicit-issuer.fixture.invalid","audience":"fictional-probe-audience","fingerprint":"a"*64,"expires":now+3600,"nonce":"n"*43}
def issued(private,kind="valid"):
    now=int(time.time())
    claims={"sub":"fictional-user","iss":config()["issuer"],"aud":config()["audience"],"iat":now,"exp":now+300}
    if kind=="wrong-issuer":claims["iss"]="https://wrong.fixture.invalid"
    if kind=="wrong-audience":claims["aud"]="different"
    if kind=="array-audience":claims["aud"]=[claims["aud"]]
    if kind=="expired":claims["exp"]=now-60
    if kind=="empty-sub":claims["sub"]=""
    return jwt.encode(claims,private,algorithm="EdDSA",headers={"kid":"key"})
@pytest.mark.parametrize("kind",["valid","wrong-issuer","wrong-audience","array-audience","expired","empty-sub","unknown-key"])
def test_exact_eddsa_trust(kind):
    module=subject_module();private=Ed25519PrivateKey.generate()
    public=json.loads(jwt.algorithms.OKPAlgorithm.to_jwk(private.public_key()))
    public.update(kid="wrong" if kind=="unknown-key" else "key",alg="EdDSA",use="sig")
    if kind=="valid":assert module.verify_token(issued(private),config(),[public])=="fictional-user"
    else:
        with pytest.raises(ValueError):module.verify_token(issued(private,kind),config(),[public])
def test_expired_target_rejects_even_a_fresh_token():
    module=subject_module();private=Ed25519PrivateKey.generate()
    public=json.loads(jwt.algorithms.OKPAlgorithm.to_jwk(private.public_key()));public.update(kid="key",alg="EdDSA",use="sig")
    value=config();value["expires"]=time.time()-1
    with pytest.raises(ValueError):module.verify_token(issued(private),value,[public])
