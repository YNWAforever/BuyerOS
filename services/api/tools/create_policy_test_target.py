"""Owned CI fixture only: no application URL, cloud project or credential fallback."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4

API = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API))
from tests.policy_activation_target import (
    LOCAL_ENGINES, FIXTURE_ISSUER, inspect_target, assert_local_docker_environment, wait_for_owned_sql,
)
from tests.conftest import DB_USER, DB_PASSWORD, POSTGRES_IMAGE


def docker(*args):
    return subprocess.check_output(["docker", *args], text=True, encoding="utf-8").strip()


def bind_fixture(receipt):
    # These are the repository's public, disposable-fixture constants. Never
    # read DATABASE_URL, provider settings or a user's secret configuration.
    dsn = f"postgresql://{DB_USER}:{DB_PASSWORD}@127.0.0.1:{receipt['port']}/{receipt['database']}"
    os.environ.update(BUYEROS_TEST_DATABASE_URL=dsn, BUYEROS_DATABASE_URL=dsn,
                      BUYEROS_DATABASE_MIGRATION_URL=dsn)
    return dsn


def create_target(receipt_path: Path, image=None):
    assert_local_docker_environment()
    if receipt_path.exists():
        raise ValueError("receipt already exists; inspect/reuse the original target, never overwrite it")
    context = docker("context", "show")
    endpoint = docker("context", "inspect", context, "--format", "{{.Endpoints.docker.Host}}")
    if endpoint not in LOCAL_ENGINES:
        raise ValueError("Docker transport must be an explicitly local engine")
    image = image or POSTGRES_IMAGE
    if image != POSTGRES_IMAGE and not (image.startswith("sha256:") and len(image) == 71):
        raise ValueError("only the fixture image or a reviewed local image digest is accepted")
    image_id = docker("image", "inspect", image, "--format", "{{.Id}}")
    run_id = "policy-ci-" + uuid4().hex
    cid = docker("run", "--pull=never", "-d", "--label", "buyeros.policy.run=" + run_id,
                 "--memory", "384m", "--cpus", "1",
                 "-e", "POSTGRES_USER=" + DB_USER, "-e", "POSTGRES_PASSWORD=" + DB_PASSWORD,
                 "-e", "POSTGRES_DB=buyeros_test_policy", "-p", "127.0.0.1::5432", image_id)
    mapping = docker("port", cid, "5432/tcp")
    port = int(mapping.rsplit(":", 1)[1])
    receipt = {"run_id": run_id, "container_id": cid, "image_id": image_id, "docker_context": context,
               "owns_entire_container": True, "host": "127.0.0.1", "port": port,
               "database": "buyeros_test_policy", "auth_issuer": FIXTURE_ISSUER}
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    bind_fixture(receipt)
    inspect_target(receipt_path)  # Actual metadata before the first SQL probe.
    receipt["server_version_num"] = wait_for_owned_sql(os.environ["BUYEROS_TEST_DATABASE_URL"])
    receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    return receipt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--image")
    parser.add_argument("--github-env", action="store_true")
    parser.add_argument("--cleanup", action="store_true")
    parser.add_argument("--run-suite", choices=("native-browser", "policy-browser"))
    options = parser.parse_args()
    path = options.receipt.resolve()
    if options.cleanup or options.run_suite and path.exists():
        receipt = json.loads(path.read_text(encoding="utf-8"))
        bind_fixture(receipt)
        inspect_target(path)
    else:
        receipt = create_target(path, options.image)
    if options.cleanup:
        result = subprocess.run(["docker", "rm", "-f", "-v", receipt["container_id"]],
                                capture_output=True, text=True, timeout=30)
        if result.returncode:
            raise RuntimeError("exact owned fixture cleanup failed")
        path.with_suffix(".cleanup.json").write_text(
            json.dumps({"container_id": receipt["container_id"], "removed": True}), encoding="utf-8")
        return 0
    if options.github_env:
        destination = os.environ.get("GITHUB_ENV")
        if not destination:
            raise ValueError("explicit GitHub job environment file required")
        entries = {"BUYEROS_TEST_DATABASE_URL": bind_fixture(receipt),
                   "BUYEROS_POLICY_TARGET_RECEIPT": str(path), "PYTEST_PLUGINS": "tools.policy_activation_pytest"}
        with open(destination, "a", encoding="utf-8") as output:
            for key, value in entries.items():
                if "\n" in value or "\r" in value:
                    raise ValueError("single-line fixture environment required")
                output.write(key + "=" + value + "\n")
    print(f"Owned fixture ready: {receipt['container_id'][:12]}; PG {receipt['server_version_num']}; no cloud target")
    if options.run_suite:
        command = [sys.executable, str(API / "tools/run_policy_activation_tests.py"),
                   "--target-receipt", str(path), "--suite", "browser"]
        if options.run_suite == "native-browser":
            command.append("--native-browser")
        return subprocess.call(command, cwd=API)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
