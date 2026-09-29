"""The worker's destructive fixture has the same disposable-only rule."""

import pytest

from tests.conftest import pg_dsn


def test_worker_rejects_external_shared_database_before_connect(monkeypatch):
    monkeypatch.setenv("BUYEROS_TEST_DATABASE_URL", "postgresql://u:p@db.example.com/production")
    with pytest.raises(pytest.UsageError, match="disposable"):
        next(pg_dsn.__wrapped__())


def test_worker_strict_integration_missing_docker_fails_instead_of_skipping(monkeypatch):
    monkeypatch.delenv("BUYEROS_TEST_DATABASE_URL", raising=False)
    monkeypatch.setenv("BUYEROS_STRICT_INTEGRATION", "1")
    monkeypatch.setattr("tests.conftest.shutil.which", lambda _: None)
    with pytest.raises(BaseException) as raised:
        next(pg_dsn.__wrapped__())
    assert isinstance(raised.value, pytest.fail.Exception), raised.value
    assert "Docker" in str(raised.value)
