"""The Windows socket workaround is limited to connection establishment, never SQL."""
import importlib
import importlib.util

import psycopg
import pytest

OWNED = "postgresql://127.0.0.1/buyeros_test_socket"
MESSAGE = 'connection to server failed: Address already in use (0x00002740/10048)'


def helper():
    assert importlib.util.find_spec("tests.owned_connection") is not None, "bounded owned connection helper missing"
    return importlib.import_module("tests.owned_connection").connect_owned


def test_owned_windows_socket_collision_retries_only_before_connection_is_returned():
    connect = helper()
    calls, sleeps = [], []
    class Connection:
        def execute(self, *args):
            raise AssertionError("connection setup must not execute or replay SQL")
    connection = Connection()
    def factory(*args, **kwargs):
        calls.append((args, kwargs))
        if len(calls) == 1:
            raise psycopg.OperationalError(MESSAGE)
        return connection
    with pytest.warns(RuntimeWarning, match="OWNED_WIN_SOCKET_10048") as notices:
        assert connect(factory, OWNED, autocommit=True, windows=True, sleep=sleeps.append) is connection
    assert len(notices) == 1 and OWNED not in str(notices[0].message)
    assert calls == [((OWNED,), {"autocommit": True}), ((OWNED,), {"autocommit": True})]
    assert sleeps == [0.05]


@pytest.mark.parametrize("dsn,error", [
    ("postgresql://db.example.test/buyeros_test_socket", psycopg.OperationalError(MESSAGE)),
    ("postgresql://127.0.0.1/production", psycopg.OperationalError(MESSAGE)),
    ("host=127.0.0.1 hostaddr=203.0.113.10 dbname=buyeros_test_socket", psycopg.OperationalError(MESSAGE)),
    (OWNED, psycopg.OperationalError("authentication refused")),
    (OWNED, psycopg.errors.SerializationFailure(MESSAGE)),
], ids=["remote", "not-owned", "remote-hostaddr", "other-connection-error", "server-SQL-error"])
def test_connection_setup_does_not_retry_other_targets_or_error_classes(dsn, error):
    connect = helper()
    calls, sleeps = [], []
    def factory(*args, **kwargs):
        calls.append(1)
        raise error
    with pytest.raises(type(error)) as captured:
        connect(factory, dsn, windows=True, sleep=sleeps.append)
    assert captured.value is error and calls == [1] and sleeps == []


def test_owned_socket_retry_is_bounded_and_preserves_the_original_error():
    connect = helper()
    error = psycopg.OperationalError(MESSAGE)
    calls, sleeps = [], []
    def factory(*args, **kwargs):
        calls.append(1)
        raise error
    with pytest.warns(RuntimeWarning, match="OWNED_WIN_SOCKET_10048") as notices:
        with pytest.raises(psycopg.OperationalError) as captured:
            connect(factory, OWNED, windows=True, sleep=sleeps.append)
    assert len(notices) == 2
    assert captured.value is error
    assert calls == [1, 1, 1] and sleeps == [0.05, 0.05]


def test_other_platforms_keep_the_original_single_connection_attempt():
    connect = helper()
    calls, sleeps = [], []
    def factory(*args, **kwargs):
        calls.append(1)
        raise psycopg.OperationalError(MESSAGE)
    with pytest.raises(psycopg.OperationalError):
        connect(factory, OWNED, windows=False, sleep=sleeps.append)
    assert calls == [1] and sleeps == []
