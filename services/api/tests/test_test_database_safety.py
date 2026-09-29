"""Destructive fixtures may only receive a disposable local test database."""

import pytest

from conftest import pg_dsn


def test_external_shared_database_is_rejected_before_connect(monkeypatch):
    monkeypatch.setenv("BUYEROS_TEST_DATABASE_URL", "postgresql://u:p@db.example.com/production")
    with pytest.raises(pytest.UsageError, match="disposable"):
        next(pg_dsn.__wrapped__())


def test_strict_integration_missing_docker_fails_instead_of_skipping(monkeypatch):
    monkeypatch.delenv("BUYEROS_TEST_DATABASE_URL", raising=False)
    monkeypatch.setenv("BUYEROS_STRICT_INTEGRATION", "1")
    monkeypatch.setattr("conftest.shutil.which", lambda _: None)
    with pytest.raises(BaseException) as raised:
        next(pg_dsn.__wrapped__())
    assert isinstance(raised.value, pytest.fail.Exception), raised.value
    assert "Docker" in str(raised.value)


def test_docker_cli_hang_is_bounded_and_reported(monkeypatch):
    import subprocess
    from conftest import _docker

    def hung(command, *, capture_output, text, timeout):
        assert command[:2] == ["docker", "run"]
        assert timeout <= 30
        raise subprocess.TimeoutExpired(command, timeout)

    monkeypatch.setattr("conftest.subprocess.run", hung)
    result = _docker("run", "--name", "buyeros-test-deadbeef")
    assert result.returncode == 124
    assert "timed out" in result.stderr
