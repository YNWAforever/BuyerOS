"""Test-only pre-client identity gate. Never imported by application services."""
from dataclasses import dataclass
import json
import os
import re
from pathlib import Path
import subprocess
import time
from uuid import uuid4
from urllib.parse import urlsplit

FIXTURE_ISSUER = "https://oidc.buyeros.test/"
LOCAL_ENGINES = {"npipe:////./pipe/dockerDesktopLinuxEngine", "unix:///var/run/docker.sock"}
_VERIFIED_ENDPOINTS = set()


@dataclass(frozen=True)
class OwnedTarget:
    run_id: str
    container_id: str
    host: str
    port: int
    database: str
    auth_issuer: str


def assert_owned_target(receipt: dict, container_metadata: dict, env_endpoints: dict) -> OwnedTarget:
    r, m, e = receipt, container_metadata, env_endpoints
    ports = m.get("ports", {}).get("5432/tcp", [])
    if (not r.get("run_id") or r.get("owns_entire_container") is not True
        or not isinstance(r.get("container_id"), str) or len(r["container_id"]) != 64
        or r.get("container_id") != m.get("id") or r.get("image_id") != m.get("image_id")
        or m.get("labels", {}).get("buyeros.policy.run") != r["run_id"]
        or m.get("docker_context") != r.get("docker_context")
        or m.get("docker_endpoint") not in LOCAL_ENGINES
        or m.get("running") is not True
        or any(item.get("Type") == "bind" for item in m.get("mounts", []))
        or r.get("host") != "127.0.0.1" or e.get("host") != r["host"]
        or e.get("port") != r.get("port") or e.get("database") != r.get("database")
        or not str(r.get("database", "")).startswith("buyeros_test_")
        or r.get("auth_issuer") != FIXTURE_ISSUER or e.get("auth_issuer") != FIXTURE_ISSUER
        or ports != [{"HostIp": "127.0.0.1", "HostPort": str(r.get("port"))}]):
        raise ValueError("owned disposable DB/Auth target is unproven or drifted; no client allowed")
    return OwnedTarget(r["run_id"], r["container_id"], r["host"], int(r["port"]), r["database"], FIXTURE_ISSUER)


def inspect_target(receipt_path: Path) -> OwnedTarget:
    assert_local_docker_environment()
    receipt = json.loads(receipt_path.read_text(encoding="utf-8-sig"))
    # Only the known container's non-secret fields leave this helper.
    def command(args):
        return subprocess.check_output(args, text=True, encoding="utf-8").strip()
    context = command(["docker", "context", "show"])
    endpoint = command(["docker", "context", "inspect", context, "--format", "{{.Endpoints.docker.Host}}"])
    raw = json.loads(command(["docker", "inspect", receipt["container_id"]]))[0]
    meta = {"id": raw["Id"], "image_id": raw["Image"], "labels": raw["Config"].get("Labels", {}),
            "ports": raw["NetworkSettings"]["Ports"], "mounts": raw.get("Mounts", []),
            "running": raw["State"]["Running"], "docker_context": context, "docker_endpoint": endpoint}
    parsed = urlsplit(os.environ.get("BUYEROS_TEST_DATABASE_URL", ""))
    if parsed.scheme != "postgresql" or parsed.query or parsed.fragment:
        raise ValueError("explicit owned test URL required")
    env = {"host": parsed.hostname, "port": parsed.port, "database": parsed.path.lstrip("/"),
           "auth_issuer": FIXTURE_ISSUER}
    result = assert_owned_target(receipt, meta, env)
    _VERIFIED_ENDPOINTS.add((result.host, result.port))
    return result


def assert_local_docker_environment():
    if os.environ.get("DOCKER_HOST") and os.environ["DOCKER_HOST"] not in LOCAL_ENGINES:
        raise ValueError("Docker transport override must be an explicit local engine")


def assert_owned_test_dsn(dsn: str) -> None:
    parsed = urlsplit(dsn)
    if ((parsed.hostname, parsed.port) not in _VERIFIED_ENDPOINTS
        or not parsed.path.lstrip("/").startswith("buyeros_test_") or parsed.query or parsed.fragment):
        raise ValueError("test helper refuses an unverified or foreign SQL target")


def wait_for_owned_sql(dsn: str) -> int:
    """Internal pg_isready can see the temporary init server. Verify host SQL."""
    assert_owned_test_dsn(dsn)
    import psycopg
    last_error = None
    for attempt in range(30):
        try:
            with psycopg.connect(dsn, connect_timeout=2) as db:
                return int(db.execute("SHOW server_version_num").fetchone()[0])
        except psycopg.OperationalError as error:
            if error.sqlstate not in {None, "57P03"}:
                raise
            last_error = error
            if attempt < 29:
                time.sleep(1)
    raise RuntimeError("verified owned host SQL did not become ready") from last_error


def owned_cluster_factory(parent_receipt_path: Path, *, database_name: str | None = None):
    """Supply legacy isolated fixtures with newly verified clusters, not a bypass.

    0002 creates cluster-global roles; separate migration clusters must remain
    separate. Validate each newly allocated cluster before its first SQL probe.
    """
    parent = json.loads(parent_receipt_path.read_text(encoding="utf-8-sig"))
    database = database_name if database_name is not None else parent["database"]
    if not re.fullmatch(r"buyeros_test_[a-z0-9_]{1,50}", database):
        raise ValueError("exact owned disposable fixture database name required")
    created = {}

    def start():
        def command(args):
            return subprocess.check_output(args, text=True, encoding="utf-8").strip()
        run = parent["run_id"] + "-" + uuid4().hex[:8]
        name = "buyeros-" + run
        cid = command([
            "docker", "run", "--pull=never", "-d", "--name", name,
            "--label", "buyeros.policy.run=" + run, "--memory", "384m", "--cpus", "1",
            "-e", "POSTGRES_USER=buyeros", "-e", "POSTGRES_PASSWORD=buyeros",
            "-e", "POSTGRES_DB=" + database, "-p", "127.0.0.1::5432", parent["image_id"],
        ])
        raw = json.loads(command(["docker", "inspect", cid]))[0]
        context = command(["docker", "context", "show"])
        endpoint = command(["docker", "context", "inspect", context, "--format", "{{.Endpoints.docker.Host}}"])
        port = int(raw["NetworkSettings"]["Ports"]["5432/tcp"][0]["HostPort"])
        receipt = {**parent, "run_id": run, "container_id": cid, "port": port, "database": database}
        meta = {"id": raw["Id"], "image_id": raw["Image"], "labels": raw["Config"].get("Labels", {}),
                "ports": raw["NetworkSettings"]["Ports"], "mounts": raw.get("Mounts", []),
                "running": raw["State"]["Running"], "docker_context": context, "docker_endpoint": endpoint}
        env = {"host": "127.0.0.1", "port": port, "database": database, "auth_issuer": FIXTURE_ISSUER}
        assert_owned_target(receipt, meta, env)
        _VERIFIED_ENDPOINTS.add(("127.0.0.1", port))
        created[name] = cid
        (parent_receipt_path.parent / (run + ".target.json")).write_text(json.dumps(receipt), encoding="utf-8")
        (parent_receipt_path.parent / (run + ".metadata.json")).write_text(json.dumps(meta), encoding="utf-8")
        # First host SQL probe, after independent container/endpoint validation.
        fixture_login = "buyeros"
        dsn = f"postgresql://{fixture_login}:{fixture_login}@127.0.0.1:{port}/{database}"
        receipt["server_version_num"] = wait_for_owned_sql(dsn)
        (parent_receipt_path.parent / (run + ".target.json")).write_text(json.dumps(receipt), encoding="utf-8")
        return name, dsn
    start.created = created
    return start
