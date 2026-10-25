"""Owned synthetic marketing fixture. No inherited application configuration.

From repo root: services/api/.venv/bin/python services/api/tools/run_marketing_intake.py [--serve]
The serve command prints only a receipt and private Node environment file path.
`--github-env --receipt` prepares the same fixture for an unfiltered suite and leaves it running.
`--cleanup --receipt` removes that exact container.
Ctrl-C verifies exact ownership again before removing its own container.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import uuid
from urllib.parse import urlsplit

API = Path(__file__).resolve().parents[1]
ROOT = API.parents[1]
sys.path.insert(0, str(API))


def clean_environment():
    allowed = {"PATH", "HOME", "USER", "LANG", "LC_ALL", "TZ", "TMPDIR", "SYSTEMROOT",
               "SSL_CERT_FILE", "SSL_CERT_DIR", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE",
               "NODE_EXTRA_CA_CERTS", "UV_CACHE_DIR", "COREPACK_HOME"}
    return {key: value for key, value in os.environ.items()
            if key in allowed or key.lower().endswith("_proxy")}


def docker(*args):
    return subprocess.check_output(["docker", *args], text=True, timeout=30).strip()


def allocate(folder):
    from tests.policy_activation_target import local_docker_context, register_created_fixture, fixture_receipt, inspect_target, wait_for_owned_sql
    local_docker_context()
    run = "marketing-" + uuid.uuid4().hex[:12]
    database = "buyeros_test_marketing_" + uuid.uuid4().hex[:12]
    image_id = docker("image", "inspect", "postgres:16", "--format", "{{.Id}}")
    cid = docker("run", "--pull=never", "-d", "--name", "buyeros-" + run,
                 "--label", "buyeros.policy.run=" + run, "--label", "buyeros.marketing.owner=" + run,
                 "--memory", "384m", "--cpus", "1", "-e", "POSTGRES_USER=buyeros",
                 "-e", "POSTGRES_PASSWORD=buyeros", "-e", "POSTGRES_DB=" + database,
                 "-p", "127.0.0.1::5432", image_id)
    raw = json.loads(docker("inspect", cid))[0]
    port = int(raw["NetworkSettings"]["Ports"]["5432/tcp"][0]["HostPort"])
    owner = f"postgresql://buyeros:buyeros@127.0.0.1:{port}/{database}"
    os.environ["BUYEROS_POLICY_FIXTURE_EVIDENCE"] = str(folder)
    register_created_fixture(cid, owner, run_id=run, image=image_id)
    receipt = fixture_receipt(owner)
    os.environ["BUYEROS_TEST_DATABASE_URL"] = owner
    inspect_target(receipt)  # independent current metadata proof before SQL client
    version = wait_for_owned_sql(owner)
    import psycopg
    with psycopg.connect(owner) as connection:
        identity = connection.execute("SELECT current_database(), current_user, session_user, pg_get_userbyid(datdba) FROM pg_database WHERE datname=current_database()").fetchone()
        assert identity == (database, "buyeros", "buyeros", "buyeros")
    data = json.loads(receipt.read_text())
    data.update(server_version_num=version, database_owner=identity[3], migration_user=identity[1],
                planned_runtime_role="marketing_runtime")
    receipt.write_text(json.dumps(data, indent=2))
    (folder / "pre-write-identity.json").write_text(json.dumps(data, indent=2))
    return owner, receipt, data


def prepare(owner, folder):
    import psycopg
    from psycopg import sql
    from buyeros_api.marketing.migrate import migrate
    password = secrets.token_urlsafe(32)
    # Ownership receipt has already been independently checked before these writes.
    with psycopg.connect(owner) as connection:
        migrate(connection)
        connection.execute(sql.SQL("CREATE ROLE marketing_runtime LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOINHERIT PASSWORD {}").format(sql.Literal(password)))
        connection.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
        connection.execute("GRANT USAGE ON SCHEMA marketing_intake TO marketing_runtime")
        connection.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA marketing_intake TO marketing_runtime")
        connection.execute("CREATE SCHEMA private_fixture")
        connection.execute("CREATE TABLE private_fixture.tenant_secrets (secret text)")
        connection.execute("INSERT INTO private_fixture.tenant_secrets VALUES ('synthetic isolation canary')")
    parsed = urlsplit(owner)
    runtime = f"postgresql://marketing_runtime:{password}@127.0.0.1:{parsed.port}{parsed.path}"
    with psycopg.connect(runtime) as connection:
        role = connection.execute("SELECT current_database(), current_user, rolsuper, rolbypassrls, rolcreatedb, rolcreaterole FROM pg_roles WHERE rolname=current_user").fetchone()
        assert role == (parsed.path.lstrip("/"), "marketing_runtime", False, False, False, False)
    (folder / "runtime-role.json").write_text(json.dumps({"database": role[0], "user": role[1], "superuser": role[2], "bypassrls": role[3], "createdb": role[4], "createrole": role[5]}, indent=2))
    return runtime


def marketing_environment(runtime, token, receipt, owner):
    return {"BUYEROS_MARKETING_ENABLED": "1", "BUYEROS_MARKETING_SYNTHETIC_MODE": "1",
            "BUYEROS_MARKETING_DATABASE_URL": runtime, "BUYEROS_MARKETING_GATEWAY_KEY": token,
            "BUYEROS_MARKETING_PUBLIC_ORIGIN": "http://127.0.0.1:5195",
            "BUYEROS_MARKETING_RETENTION_DAYS": "1", "BUYEROS_MARKETING_GLOBAL_PER_HOUR": "100",
            "BUYEROS_MARKETING_EMAIL_PER_DAY": "3", "BUYEROS_MARKETING_CHALLENGES_PER_MINUTE": "200",
            "BUYEROS_MARKETING_TEST_TARGET": str(receipt), "BUYEROS_MARKETING_TEST_OWNER_DSN": owner}


def publish_github_env(entries):
    destination = os.environ.get("GITHUB_ENV")
    if not destination:
        raise ValueError("explicit GitHub job environment file required")
    with open(destination, "a", encoding="utf-8") as output:
        for key, value in entries.items():
            if "\n" in value or "\r" in value:
                raise ValueError("single-line fixture environment required")
            output.write(key + "=" + value + "\n")


def remove_owned(receipt, identity, folder):
    from tests.policy_activation_target import inspect_target
    inspect_target(receipt)
    labels = json.loads(docker("inspect", identity["container_id"], "--format", "{{json .Config.Labels}}"))
    if labels.get("buyeros.marketing.owner") != identity["run_id"]:
        raise ValueError("refusing to remove a container that is not the owned marketing fixture")
    docker("rm", "-f", "-v", identity["container_id"])
    (folder / "cleanup.json").write_text(json.dumps({"container_id": identity["container_id"], "removed": True}))


def cleanup_fixture(receipt_path: Path):
    path = receipt_path.resolve()
    receipt = json.loads(path.read_text(encoding="utf-8"))
    os.environ["BUYEROS_TEST_DATABASE_URL"] = (
        f"postgresql://buyeros:buyeros@127.0.0.1:{receipt['port']}/{receipt['database']}"
    )
    from tests.policy_activation_target import inspect_target
    inspect_target(path)
    labels = json.loads(docker("inspect", receipt["container_id"], "--format", "{{json .Config.Labels}}"))
    if labels.get("buyeros.marketing.owner") != receipt["run_id"]:
        raise ValueError("refusing to remove a container that is not the owned marketing fixture")
    docker("rm", "-f", "-v", receipt["container_id"])
    path.with_suffix(".cleanup.json").write_text(
        json.dumps({"container_id": receipt["container_id"], "removed": True}), encoding="utf-8")
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--github-env", action="store_true")
    parser.add_argument("--cleanup", action="store_true")
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--api-port", type=int, default=8013)
    parser.add_argument("--readback", type=Path)
    parser.add_argument("--receipt-id", type=uuid.UUID)
    args, tests = parser.parse_known_args()
    if args.readback:
        return readback(args.readback, args.receipt_id)
    if args.cleanup:
        if args.github_env or args.serve or args.receipt is None:
            parser.error("cleanup requires only --receipt")
        return cleanup_fixture(args.receipt)
    if args.github_env and (args.serve or args.receipt is None):
        parser.error("github-env requires --receipt and does not serve")
    # Explicit isolation precedes any helper import or SQL client.
    child = clean_environment()
    for name in list(os.environ):
        if name.startswith(("BUYEROS_", "MARKETING_")):
            os.environ.pop(name)
    folder = ROOT / "outputs/marketing-full/intake" / ("run-" + uuid.uuid4().hex[:12])
    folder.mkdir(parents=True, exist_ok=False)
    (folder / "source.json").write_text(json.dumps({"head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "files": {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in [*sorted((API / "buyeros_api/marketing").glob("*.py")), API / "tests/test_marketing_intake.py", Path(__file__)]}}, indent=2))
    owner, receipt, identity = allocate(folder)
    private_path = None
    process = None
    retain = False
    try:
        runtime = prepare(owner, folder)
        token = secrets.token_urlsafe(48)
        if args.github_env:
            kept = args.receipt.resolve()
            if kept.exists():
                raise ValueError("receipt already exists; inspect/reuse the original target, never overwrite it")
            kept.parent.mkdir(parents=True, exist_ok=True)
            kept.write_text(receipt.read_text(encoding="utf-8"), encoding="utf-8")
            receipt = kept
        child.update(marketing_environment(runtime, token, receipt, owner))
        print(json.dumps({"evidence": str(folder), "receipt": str(receipt)}), flush=True)
        if args.github_env:
            publish_github_env({key: value for key, value in child.items() if key.startswith("BUYEROS_MARKETING_")})
            retain = True
            return 0
        if args.serve:
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", args.api_port))
            node = {"MARKETING_ENABLED": "1", "MARKETING_SYNTHETIC_MODE": "1",
                    "MARKETING_API_ORIGIN": f"http://127.0.0.1:{args.api_port}",
                    "MARKETING_PUBLIC_ORIGIN": "http://127.0.0.1:5195", "MARKETING_GATEWAY_KEY": token}
            descriptor, private_name = tempfile.mkstemp(prefix="buyeros-marketing-", suffix=".json")
            private_path = Path(private_name)
            with os.fdopen(descriptor, "w") as output:
                json.dump({"node": node, "api": child, "receipt": str(receipt)}, output)
            print(json.dumps({"node_environment_file": str(private_path), "api_origin": node["MARKETING_API_ORIGIN"]}), flush=True)
            with (folder / "api.log").open("x") as output:
                process = subprocess.Popen([sys.executable, "-m", "uvicorn", "buyeros_api.marketing.router:create_marketing_app", "--factory", "--host", "127.0.0.1", "--port", str(args.api_port), "--no-access-log"], cwd=API, env=child, stdout=output, stderr=subprocess.STDOUT)
                try:
                    return process.wait()
                except KeyboardInterrupt:
                    return 0
        with (folder / "tests.log").open("x") as output:
            result = subprocess.run([sys.executable, "-m", "pytest", "tests/test_marketing_intake.py", "-q", *tests], cwd=API, env=child, stdout=output, stderr=subprocess.STDOUT)
        print("\n".join((folder / "tests.log").read_text().splitlines()[-35:]), flush=True)
        return result.returncode
    finally:
        if process and process.poll() is None:
            process.terminate()
            process.wait(timeout=15)
        if not retain:
            remove_owned(receipt, identity, folder)
        if private_path:
            private_path.unlink(missing_ok=True)


def readback(private_path, receipt_id):
    """Prove the exact live fixture again, then read only public synthetic receipts."""
    path = private_path.resolve(strict=True)
    metadata = path.stat()
    if (private_path.is_symlink() or path.parent != Path(tempfile.gettempdir()).resolve()
        or not path.name.startswith("buyeros-marketing-") or metadata.st_uid != os.getuid()
        or metadata.st_mode & 0o077):
        raise ValueError("expected this user's private marketing fixture handoff")
    data = json.loads(path.read_text())
    owner = data["api"]["BUYEROS_MARKETING_TEST_OWNER_DSN"]
    runtime = data["api"]["BUYEROS_MARKETING_DATABASE_URL"]
    from tests.policy_activation_target import inspect_target
    os.environ["BUYEROS_TEST_DATABASE_URL"] = owner
    target = inspect_target(Path(data["receipt"]))
    parsed = urlsplit(runtime)
    if (parsed.hostname, parsed.port, parsed.path.lstrip("/"), parsed.username) != (target.host, target.port, target.database, "marketing_runtime"):
        raise ValueError("runtime SQL target drifted")
    import psycopg
    with psycopg.connect(runtime) as connection:
        rows = connection.execute("SELECT id::text, locale, synthetic, created_at::text FROM marketing_intake.leads WHERE (%s::uuid IS NULL OR id=%s::uuid) ORDER BY created_at", (receipt_id, receipt_id)).fetchall()
    print(json.dumps({"count": len(rows), "receipts": [{"receipt_id": row[0], "locale": row[1], "synthetic": row[2], "created_at": row[3]} for row in rows]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
