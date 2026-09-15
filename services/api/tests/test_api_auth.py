import pytest

from buyeros_api.api.auth import AuthError, claims_to_principal, jwks_uri_for


def test_missing_configuration_fails_closed():
    from buyeros_api.api.auth import principal_from_token

    with pytest.raises(AuthError):
        principal_from_token("whatever", issuer=None, audience=None)


def test_wrong_audience_rejected():
    claims = {"iss": "https://t.example/", "aud": "other", "exp": 9999999999, "sub": "auth0|1"}
    with pytest.raises(AuthError):
        claims_to_principal(claims, issuer="https://t.example/", audience="buyeros-api")


def test_valid_claims_ok():
    claims = {"iss": "https://t.example/", "aud": "buyeros-api", "exp": 9999999999, "sub": "auth0|1"}
    principal = claims_to_principal(claims, issuer="https://t.example/", audience="buyeros-api")
    assert principal.subject == "auth0|1"


def test_jwks_uri_derivation():
    assert jwks_uri_for("https://t.example/") == "https://t.example/.well-known/jwks.json"


def test_wrong_issuer_rejected():
    claims = {"iss": "https://other.example/", "aud": "buyeros-api", "exp": 9999999999, "sub": "auth0|1"}
    with pytest.raises(AuthError):
        claims_to_principal(claims, issuer="https://t.example/", audience="buyeros-api")


def test_expired_token_rejected():
    claims = {"iss": "https://t.example/", "aud": "buyeros-api", "exp": 100, "sub": "auth0|1"}
    with pytest.raises(AuthError):
        claims_to_principal(claims, issuer="https://t.example/", audience="buyeros-api", now=200)


def test_missing_subject_rejected():
    claims = {"iss": "https://t.example/", "aud": "buyeros-api", "exp": 9999999999}
    with pytest.raises(AuthError):
        claims_to_principal(claims, issuer="https://t.example/", audience="buyeros-api")


def test_list_audience_accepted():
    claims = {"iss": "https://t.example/", "aud": ["other", "buyeros-api"], "exp": 9999999999, "sub": "auth0|1"}
    principal = claims_to_principal(claims, issuer="https://t.example/", audience="buyeros-api")
    assert principal.subject == "auth0|1"


@pytest.mark.parametrize("exp", ["not-a-number", None])
def test_malformed_exp_fails_closed(exp):
    claims = {"iss": "https://t.example/", "aud": "buyeros-api", "exp": exp, "sub": "auth0|1"}
    with pytest.raises(AuthError):
        claims_to_principal(claims, issuer="https://t.example/", audience="buyeros-api")


@pytest.mark.parametrize("nbf", ["not-a-number", None])
def test_malformed_nbf_fails_closed(nbf):
    claims = {"iss": "https://t.example/", "aud": "buyeros-api", "exp": 9999999999, "nbf": nbf, "sub": "auth0|1"}
    with pytest.raises(AuthError):
        claims_to_principal(claims, issuer="https://t.example/", audience="buyeros-api")


def test_future_nbf_rejected():
    claims = {"iss": "https://t.example/", "aud": "buyeros-api", "exp": 9999999999, "nbf": 5000, "sub": "auth0|1"}
    with pytest.raises(AuthError):
        claims_to_principal(claims, issuer="https://t.example/", audience="buyeros-api", now=1000)


def test_nbf_within_clock_skew_accepted():
    claims = {"iss": "https://t.example/", "aud": "buyeros-api", "exp": 9999999999, "nbf": 1050, "sub": "auth0|1"}
    principal = claims_to_principal(claims, issuer="https://t.example/", audience="buyeros-api", now=1000)
    assert principal.subject == "auth0|1"


def _protected_app():
    from fastapi import Depends
    from fastapi.testclient import TestClient

    from buyeros_api.api.app import create_app
    from buyeros_api.api.auth import Principal, get_principal

    app = create_app()

    @app.get("/protected")
    async def protected(principal: Principal = Depends(get_principal)):
        return {"data": {"subject": principal.subject}, "request_id": "x", "data_mode": "live"}

    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize(
    "headers",
    [{}, {"Authorization": ""}, {"Authorization": "Basic abc"}, {"Authorization": "bearer"}],
)
def test_get_principal_missing_or_invalid_header_is_unauthorized(headers):
    response = _protected_app().get("/protected", headers=headers)
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHENTICATED"


def test_get_principal_bearer_scheme_is_case_insensitive(monkeypatch):
    from fastapi import Depends
    from fastapi.testclient import TestClient

    from buyeros_api.api import auth
    from buyeros_api.api.app import create_app

    seen = {}

    def fake_principal_from_token(token, *, issuer, audience):
        seen["token"] = token
        return auth.Principal(issuer=issuer or "issuer", subject="auth0|1")

    monkeypatch.setattr(auth, "principal_from_token", fake_principal_from_token)
    app = create_app()

    @app.get("/protected")
    async def protected(principal: auth.Principal = Depends(auth.get_principal)):
        return {"data": {"subject": principal.subject}, "request_id": "x", "data_mode": "live"}

    response = TestClient(app).get("/protected", headers={"Authorization": "bearer test-token"})
    assert response.status_code == 200
    assert seen["token"] == "test-token"
