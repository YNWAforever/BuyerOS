import asyncio
import json
import logging

import pytest
from sqlalchemy.exc import OperationalError, TimeoutError as PoolTimeout
from starlette.requests import Request

from buyeros_api.api.errors import internal_error_handler

REQUEST_ID = '1d123054-2633-40b7-8e07-b6aed83dad98'
SECRETS = ('postgresql://actor:private-password@db.invalid/private',
           'eyJfixture.eyJprivate.secret-signature', 'secret-sql-bind')


def request():
    value = Request({'type': 'http', 'method': 'GET', 'path': '/v1/workspaces', 'headers': []})
    value.state.request_id = REQUEST_ID
    return value


@pytest.mark.parametrize(('state', 'classification'), [
    ('42P01', 'missing_relation'), ('42501', 'insufficient_privilege'),
    ('08006', 'connection_failure'),
])
def test_database_error_diagnostics_redacts_secrets(caplog, state, classification):
    class DriverError(Exception):
        sqlstate = state
    error = OperationalError('SELECT ' + SECRETS[2], {'password': SECRETS[0]}, DriverError(SECRETS[1]))
    with caplog.at_level(logging.ERROR):
        response = asyncio.run(internal_error_handler(request(), error))
    fields = getattr(caplog.records[-1], 'diagnostic', {})
    assert fields.get('sqlstate') == state
    assert fields.get('request_id') == REQUEST_ID
    assert fields.get('error_class') == 'OperationalError'
    assert fields.get('classification') == classification
    rendered = caplog.text + json.dumps(fields)
    assert all(secret not in rendered for secret in SECRETS)
    assert caplog.records[-1].exc_info is None
    assert response.status_code == 500
    assert json.loads(response.body) == {
        'code': 'INTERNAL_ERROR', 'message': 'request failed',
        'request_id': REQUEST_ID, 'retryable': True,
    }


def test_pool_timeout_is_distinguished_without_logging_exception_message(caplog):
    with caplog.at_level(logging.ERROR):
        asyncio.run(internal_error_handler(request(), PoolTimeout(SECRETS[0])))
    fields = getattr(caplog.records[-1], 'diagnostic', {})
    assert fields.get('classification') == 'pool_timeout'
    assert fields.get('sqlstate') is None
    assert fields.get('pool_wait_ms') is None
    assert SECRETS[0] not in caplog.text


def test_unknown_operational_failure_stays_unconfirmed(caplog, monkeypatch):
    monkeypatch.delenv('BUYEROS_SOURCE_SHA', raising=False)
    monkeypatch.delenv('VERCEL_GIT_COMMIT_SHA', raising=False)
    error = OperationalError(SECRETS[0], {'bind': SECRETS[2]}, Exception(SECRETS[1]))
    with caplog.at_level(logging.ERROR):
        asyncio.run(internal_error_handler(request(), error))
    fields = getattr(caplog.records[-1], 'diagnostic', {})
    assert fields.get('classification') == 'unconfirmed'
    assert set(fields) >= {'schema_head', 'runtime_role', 'source_sha', 'connection_timeout', 'pool_wait_ms'}
    assert all(fields[key] is None for key in ('sqlstate', 'schema_head', 'runtime_role', 'source_sha', 'connection_timeout', 'pool_wait_ms'))
    assert 'cold_start' not in json.dumps(fields)


def test_diagnostic_context_rejects_secret_bearing_and_invalid_metadata(caplog, monkeypatch):
    value = request()
    value.state.database_diagnostics = {
        'schema_head': SECRETS[0], 'runtime_role': SECRETS[1],
        'pool_wait_ms': SECRETS[2], 'connection_timeout': SECRETS[0],
    }
    monkeypatch.setenv('BUYEROS_SOURCE_SHA', SECRETS[0])
    with caplog.at_level(logging.ERROR):
        asyncio.run(internal_error_handler(value, OperationalError(SECRETS[0], {}, Exception(SECRETS[1]))))
    fields = getattr(caplog.records[-1], 'diagnostic', {})
    assert fields.get('request_id') == REQUEST_ID
    assert all(fields.get(key) is None for key in ('schema_head', 'runtime_role', 'pool_wait_ms', 'connection_timeout', 'source_sha'))
    assert all(secret not in caplog.text + json.dumps(fields) for secret in SECRETS)


@pytest.mark.parametrize('wait', [True, float('nan'), float('inf'), -1, 10**400])
def test_bad_pool_timing_cannot_break_error_envelope(caplog, wait):
    value = request()
    value.state.database_diagnostics = {'pool_wait_ms': wait}
    with caplog.at_level(logging.ERROR):
        response = asyncio.run(internal_error_handler(value, Exception('private')))
    assert response.status_code == 500
    assert caplog.records[-1].diagnostic['pool_wait_ms'] is None


def test_observed_connect_timeout_distinct_from_pool_timeout(caplog, monkeypatch):
    value = request()
    value.state.database_diagnostics = {
        'connection_timeout': True, 'pool_wait_ms': 3.5,
        'schema_head': '0037_bulk_manifests', 'runtime_role': 'buyeros_api',
    }
    monkeypatch.setenv('BUYEROS_SOURCE_SHA', 'a' * 40)
    with caplog.at_level(logging.ERROR):
        asyncio.run(internal_error_handler(value, TimeoutError(SECRETS[0])))
    fields = caplog.records[-1].diagnostic
    assert fields['classification'] == 'connection_timeout'
    assert fields['connection_timeout'] is True
    assert fields['pool_wait_ms'] == 3.5
    assert fields['schema_head'] == '0037_bulk_manifests'
    assert fields['runtime_role'] == 'buyeros_api'
    assert fields['source_sha'] == 'a' * 40
    assert SECRETS[0] not in caplog.text


def test_generic_timeout_does_not_prove_connect_timeout(caplog):
    with caplog.at_level(logging.ERROR):
        asyncio.run(internal_error_handler(request(), TimeoutError('private')))
    assert caplog.records[-1].diagnostic['classification'] == 'unconfirmed'


def test_alembic_configuration_preserves_api_diagnostic_logger(monkeypatch):
    from io import StringIO
    from pathlib import Path
    from alembic import command
    from alembic.config import Config
    from buyeros_api.settings import get_settings

    root = Path(__file__).resolve().parents[1]
    logger = logging.getLogger('buyeros_api.api.errors')
    monkeypatch.setattr(logger, 'disabled', False)
    monkeypatch.setenv('BUYEROS_DATABASE_URL', 'postgresql://fixture:fixture@127.0.0.1/buyeros_test_offline')
    monkeypatch.setenv('BUYEROS_DATABASE_MIGRATION_URL', 'postgresql://fixture:fixture@127.0.0.1/buyeros_test_offline')
    get_settings.cache_clear()
    config = Config(str(root / 'alembic.ini'), output_buffer=StringIO())
    config.set_main_option('script_location', str(root / 'alembic'))
    try:
        command.upgrade(config, '0037_bulk_manifests:head', sql=True)
        assert logger.disabled is False, 'migration logging disabled the existing API diagnostic logger'
    finally:
        get_settings.cache_clear()


def test_unknown_exception_class_name_cannot_disclose_secret_metadata(caplog):
    error_type = type('CANARY_PRIVATE_TOKEN', (Exception,), {})
    with caplog.at_level(logging.ERROR, logger='buyeros_api.api.errors'):
        response = asyncio.run(internal_error_handler(request(), error_type(SECRETS[0])))
    assert response.status_code == 500
    assert caplog.records[-1].diagnostic['error_class'] == 'UnexpectedError'
    assert 'CANARY_PRIVATE_TOKEN' not in caplog.text
    assert SECRETS[0] not in caplog.text
