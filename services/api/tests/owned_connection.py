"""Bounded Windows-only acquisition for disposable loopback test databases."""
import time
import warnings

import psycopg
from psycopg.conninfo import conninfo_to_dict


def _owned(args, kwargs):
    try:
        values = dict(kwargs)
        conninfo = args[0] if args else values.pop("conninfo", "")
        parameters = conninfo_to_dict(conninfo, **values)
    except (TypeError, psycopg.Error):
        return False
    name, host, hostaddr = parameters.get("dbname", ""), parameters.get("host"), parameters.get("hostaddr")
    if not isinstance(name, str) or not isinstance(host, str):
        return False
    return (host in {"127.0.0.1", "localhost", "::1"}
            and (hostaddr is None or hostaddr in {"", "127.0.0.1", "localhost", "::1"})
            and (name == "buyeros_test" or name.startswith("buyeros_test_")))


def connect_owned(factory, *args, windows, sleep=time.sleep, **kwargs):
    """No connection was returned, so no SQL or provider operation is replayed."""
    attempts = 0
    while True:
        try:
            return factory(*args, **kwargs)
        except psycopg.OperationalError as error:
            attempts += 1
            message = str(error).lower()
            if (not windows or attempts >= 3 or error.sqlstate is not None
                    or "10048" not in message or "address already in use" not in message
                    or not _owned(args, kwargs)):
                raise
            warnings.warn(
                f"OWNED_WIN_SOCKET_10048: connection acquisition retry {attempts+1}/3 before SQL",
                RuntimeWarning, stacklevel=2,
            )
            sleep(0.05)
