"""Protected release reads must never expose credentials or mutate runtime data."""
import hashlib
import importlib
import json

import pytest
from fastapi.testclient import TestClient

from buyeros_api.api.app import create_app
from buyeros_api.settings import get_settings

TOKEN = 'owned-release-probe-token-0123456789abcdef'
SOURCE = 'a' * 40
DEPLOYMENT = 'dpl_ownedcandidate'
DSN = 'postgresql://private_user:private_password@EP-EXAMPLE.NEON.TECH/buyer%20db?sslmode=require'
EXPECTED = hashlib.sha256(b'{"database":"buyer db","host":"ep-example.neon.tech","port":5432}').hexdigest()


def service():
    return importlib.import_module('buyeros_api.services.release_binding')


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv('BUYEROS_RELEASE_PROBE_TOKEN', TOKEN)
    monkeypatch.setenv('BUYEROS_RUNTIME_SOURCE_SHA', SOURCE)
    monkeypatch.setenv('BUYEROS_RUNTIME_DEPLOYMENT_ID', DEPLOYMENT)
    monkeypatch.setenv('BUYEROS_DATABASE_URL', DSN)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_database_target_digest_uses_only_normalized_name_host_port():
    module = service()
    for dsn in (DSN, 'postgresql+psycopg://other:secret@ep-example.neon.tech:5432/buyer%20db'):
        assert module.database_target_sha256(dsn) == EXPECTED
    ipv6 = hashlib.sha256(b'{"database":"buyer","host":"::1","port":5432}').hexdigest()
    assert module.database_target_sha256('postgresql://user:pw@[0:0:0:0:0:0:0:1]/buyer') == ipv6
    assert module.database_target_sha256(DSN.replace('/buyer%20db', '/other')) != EXPECTED


@pytest.mark.parametrize('dsn', [
    'postgresql:///buyer', 'postgresql://host/', 'https://host/buyer',
    'postgresql://host/buyer?host=other', 'postgresql://host/buyer?dbname=other',
    'postgresql://host/buyer?hostaddr=127.0.0.1', 'postgresql://host:0/buyer',
    'postgresql://host/buyer#fragment', 'postgresql://host/a%2Fb',
])
def test_database_target_digest_refuses_ambiguous_target(dsn):
    with pytest.raises(ValueError):
        service().database_target_sha256(dsn)


def test_missing_and_wrong_credentials_do_not_open_database(configured, monkeypatch):
    from buyeros_api.api import deps
    calls = []
    monkeypatch.setattr(deps, 'get_engine', lambda: calls.append('opened'))
    with TestClient(create_app()) as client:
        for headers in ({}, {'Authorization': 'Bearer wrong'}, {'Authorization': 'Bearer ' + TOKEN, 'X-Other': 'unused'}):
            if headers.get('Authorization') == 'Bearer ' + TOKEN:
                headers = [('Authorization', 'Bearer ' + TOKEN), ('Authorization', 'Bearer ' + TOKEN)]
            response = client.get('/v1/internal/release-binding', headers=headers)
            assert response.status_code == 401, response.text
            assert response.json()['code'] == 'UNAUTHENTICATED'
            assert response.headers['cache-control'] == 'no-store'
    assert calls == []


def test_release_binding_fixed_response_and_constant_time_auth(configured, monkeypatch):
    module = service()
    routes = importlib.import_module('buyeros_api.api.routes.release_binding')
    compared = []
    real = module.hmac.compare_digest
    monkeypatch.setattr(module.hmac, 'compare_digest', lambda a, b: (compared.append((a, b)), real(a, b))[1])
    async def read():
        return {'schema': 'buyeros.runtime-db-binding.v1', 'source_sha': SOURCE,
                'deployment_id': DEPLOYMENT, 'schema_head': '0054_buyer_source_checks', 'db_target_sha256': EXPECTED}
    monkeypatch.setattr(routes, 'read_binding', read)
    with TestClient(create_app()) as client:
        response = client.get('/v1/internal/release-binding', headers={'Authorization': 'Bearer ' + TOKEN})
    assert response.status_code == 200, response.text
    assert set(response.json()) == {'schema', 'source_sha', 'deployment_id', 'schema_head', 'db_target_sha256'}
    assert response.json()['db_target_sha256'] == EXPECTED
    assert response.headers['cache-control'] == 'no-store'
    assert compared == [(TOKEN.encode(), TOKEN.encode())]
    assert all(secret not in response.text for secret in (DSN, 'private_user', 'private_password', TOKEN))


@pytest.mark.parametrize('missing', ['BUYEROS_RUNTIME_SOURCE_SHA', 'BUYEROS_RUNTIME_DEPLOYMENT_ID'])
def test_release_binding_refuses_incomplete_runtime_identity(configured, monkeypatch, missing):
    monkeypatch.delenv(missing)
    monkeypatch.delenv('VERCEL_DEPLOYMENT_ID', raising=False)
    get_settings.cache_clear()
    from buyeros_api.api import deps
    calls = []
    monkeypatch.setattr(deps, 'get_engine', lambda: calls.append('opened'))
    with TestClient(create_app()) as client:
        response = client.get('/v1/internal/release-binding', headers={'Authorization': 'Bearer ' + TOKEN})
    assert response.status_code == 503
    assert response.headers['cache-control'] == 'no-store'
    assert calls == []
    assert TOKEN not in response.text


def test_release_binding_sanitizes_database_failures(configured, monkeypatch):
    routes = importlib.import_module('buyeros_api.api.routes.release_binding')
    async def failed():
        raise RuntimeError(DSN)
    monkeypatch.setattr(routes, 'read_binding', failed)
    with TestClient(create_app()) as client:
        response = client.get('/v1/internal/release-binding', headers={'Authorization': 'Bearer ' + TOKEN})
    assert response.status_code == 503
    assert response.json()['code'] == 'RELEASE_BINDING_UNAVAILABLE'
    assert response.headers['cache-control'] == 'no-store'
    assert 'private_password' not in response.text
