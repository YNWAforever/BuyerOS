"""Start an explicitly activated Render process, or wait without executing jobs."""

import argparse
import ipaddress
import os
import signal
import sys
from threading import Event
from urllib.parse import parse_qs, unquote, urlsplit


class ConfigurationError(ValueError):
    pass


def remote_connection(value, schemes):
    try:
        parsed = urlsplit(value)
        host = parsed.hostname
        port = parsed.port
    except ValueError:
        raise ConfigurationError("Invalid runtime connection configuration") from None
    if parsed.scheme not in schemes or not host or parsed.fragment:
        raise ConfigurationError("Invalid runtime connection configuration")
    if host == "localhost" or host.endswith(".localhost"):
        raise ConfigurationError("Runtime connections must use the selected remote services")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address and (address.is_loopback or address.is_unspecified or address.is_link_local):
        raise ConfigurationError("Runtime connections must use the selected remote services")
    if port is not None and not 1 <= port <= 65535:
        raise ConfigurationError("Invalid runtime connection configuration")
    return parsed


def launch_command(role, environment):
    if role not in {"worker", "dispatcher"}:
        raise ConfigurationError("Unknown worker process role")
    enabled = environment.get("BUYEROS_WORKER_RUNTIME_ENABLED", "false")
    if enabled not in {"true", "false"}:
        raise ConfigurationError("BUYEROS_WORKER_RUNTIME_ENABLED must be true or false")
    if enabled == "false":
        return None
    if environment.get("BUYEROS_ENVIRONMENT") != "production":
        raise ConfigurationError("BUYEROS_ENVIRONMENT must be production for this launcher")
    database = remote_connection(environment.get("BUYEROS_DATABASE_URL", ""), {"postgresql", "postgresql+psycopg"})
    if unquote(database.username or "") != "buyeros_worker_runtime" or not database.password or database.path in {"", "/"}:
        raise ConfigurationError("BUYEROS_DATABASE_URL must use the dedicated buyeros_worker_runtime login")
    if parse_qs(database.query).get("sslmode") not in (["require"], ["verify-ca"], ["verify-full"]):
        raise ConfigurationError("BUYEROS_DATABASE_URL must require TLS")
    broker = remote_connection(environment.get("BUYEROS_BROKER_URL", ""), {"redis", "rediss"})
    if broker.query or broker.path not in {"", "/", "/0"}:
        raise ConfigurationError("BUYEROS_BROKER_URL must use the one broker database zero")
    if broker.hostname.endswith(".render.com") and broker.scheme != "rediss":
        raise ConfigurationError("External broker connections must require TLS")
    if role == "worker":
        return [sys.executable, "-m", "celery", "-A", "buyeros_worker.app:celery_app", "worker",
                "--pool=prefork", "--concurrency=1", "--prefetch-multiplier=1", "--max-tasks-per-child=100",
                "--loglevel=WARNING", "--beat", "--schedule=/tmp/buyeros-celerybeat-schedule"]
    return [sys.executable, "-m", "buyeros_worker.cli", "dispatch", "--loop",
            "--max-total", "10", "--time-budget-seconds", "10", "--idle-seconds", "2"]


def wait_in_standby(role):
    stopped = Event()
    for signum in (signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, lambda *_: stopped.set())
    print(f"BuyerOS {role}: standby; no jobs or connections started", flush=True)
    stopped.wait()
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("role", choices=("worker", "dispatcher"))
    parser.add_argument("--check", action="store_true", help="validate configuration without connections or execution")
    args = parser.parse_args(argv)
    try:
        command = launch_command(args.role, os.environ)
    except ConfigurationError as error:
        print(str(error), file=sys.stderr)
        return 2
    if args.check:
        state = "standby" if command is None else "configuration verified"
        print(f"BuyerOS {args.role}: {state}; no jobs or connections started")
        return 0
    if command is None:
        return wait_in_standby(args.role)
    os.execv(sys.executable, command)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
