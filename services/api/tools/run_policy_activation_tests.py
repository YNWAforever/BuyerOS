"""Owned local test entrypoint. Validates container/endpoint before test imports."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

API = Path(__file__).resolve().parents[1]
ROOT = API.parents[1]
sys.path.insert(0, str(API))
CONFTEXTS = {(API / "tests/conftest.py").resolve(), (ROOT / "services/worker/tests/conftest.py").resolve()}


class OwnedFixturePlugin:
    """Pytest may load this repository's conftest under two module names."""
    def __init__(self, factory, validator=None):
        self.factory = factory
        self.validator = validator
        self.patched = set()
        self.migration_wrappers = []

    def install(self, module):
        path = getattr(module, "__file__", None)
        if not path or Path(path).resolve() not in CONFTEXTS:
            return
        if id(module) in self.patched:
            return
        original = module._docker
        factory = self.factory
        def owned_docker(*args):
            if args and args[0] == "rm" and args[-1] in factory.created:
                return subprocess.run(["docker", "rm", "-f", "-v", factory.created[args[-1]]],
                                      capture_output=True, text=True, timeout=30)
            return original(*args)
        module._start_container = factory
        module._docker = owned_docker
        self.patched.add(id(module))

    def pytest_plugin_registered(self, plugin, plugin_name, manager):
        self.install(plugin)

    def pytest_configure(self, config):
        import importlib
        # Preload the second alias before tests copy its allocator with
        # `from tests.conftest import _start_container`.
        self.install(importlib.import_module("tests.conftest"))
        for module in list(sys.modules.values()):
            self.install(module)
        if self.validator:
            # A global migration URL would accidentally send a fresh-cluster
            # rehearsal to its parent. Each fixture selects its own explicit
            # owner URL. Guard the actual resolved URL before Alembic creates
            # a client; an application/default/foreign endpoint cannot pass.
            os.environ.pop("BUYEROS_DATABASE_MIGRATION_URL", None)
            from alembic import command
            from buyeros_api.settings import get_settings
            from functools import wraps
            for name in ("upgrade", "downgrade", "stamp"):
                original = getattr(command, name)
                @wraps(original)
                def guarded(*args, _original=original, **kwargs):
                    # Offline Alembic only renders SQL; it never opens a client.
                    # The online gate remains mandatory for all real targets.
                    if kwargs.get("sql") is True:
                        return _original(*args, **kwargs)
                    dsn = os.environ.get("BUYEROS_DATABASE_MIGRATION_URL") or os.environ.get("BUYEROS_DATABASE_URL")
                    if not dsn:
                        raise ValueError("explicit owned migration target required")
                    self.validator(dsn)
                    get_settings.cache_clear()
                    return _original(*args, **kwargs)
                setattr(command, name, guarded)
                self.migration_wrappers.append((command, name, original, guarded))

    def pytest_unconfigure(self, config):
        for module, name, original, wrapper in reversed(self.migration_wrappers):
            if getattr(module, name) is wrapper:
                setattr(module, name, original)

    def pytest_collection_finish(self, session):
        for module in list(sys.modules.values()):
            self.install(module)

    def pytest_fixture_setup(self, fixturedef, request):
        fields = getattr(fixturedef.func, "__globals__", {})
        path = fields.get("__file__")
        if path and Path(path).resolve() in CONFTEXTS:
            module = sys.modules.get(fixturedef.func.__module__)
            if module is not None:
                self.install(module)
            if fields.get("_start_container") is not self.factory:
                raise RuntimeError("owned fixture allocator was not installed before fixture setup")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-receipt", type=Path, required=True)
    parser.add_argument("--suite", choices=("api", "worker", "browser"), required=True)
    parser.add_argument("--native-browser", action="store_true")
    parser.add_argument("--browser-phase", choices=("red", "full"), default="full")
    parser.add_argument("--fresh-target", action="store_true")
    parser.add_argument("--worker-process", action="store_true")
    options, rest = parser.parse_known_args()
    options.target_receipt = options.target_receipt.resolve()
    if options.worker_process:
        import importlib.util
        spec = importlib.util.spec_from_file_location("_buyeros_owned_policy_gate", API / "tests/policy_activation_target.py")
        target_module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = target_module
        spec.loader.exec_module(target_module)
    else:
        from tests import policy_activation_target as target_module
    target = target_module.inspect_target(options.target_receipt)
    # Explicit test binding; there is no application/production URL fallback.
    dsn = os.environ["BUYEROS_TEST_DATABASE_URL"]
    os.environ.update(BUYEROS_DATABASE_URL=dsn, BUYEROS_DATABASE_MIGRATION_URL=dsn,
                      BUYEROS_STRICT_INTEGRATION="1", BUYEROS_PAID_ADMISSION_ENABLED="false",
                      BUYEROS_DELIVERY_ADMISSION_ENABLED="false", BUYEROS_CLOUDFLARE_EXECUTION_ENABLED="false",
                      BUYEROS_POLICY_TARGET_RECEIPT=str(options.target_receipt.resolve()),
                      NEXT_TELEMETRY_DISABLED="1", WRANGLER_SEND_METRICS="false")
    for key in tuple(os.environ):
        if key.startswith(("BUYEROS_NEON_", "BUYEROS_EXA_", "BUYEROS_OPENCODE_", "BUYEROS_CONTACT_")):
            os.environ.pop(key, None)
    if rest[:1] == ["--"]:
        rest = rest[1:]
    print(f"Owned target verified: {target.run_id}; {target.container_id[:12]}; fixture-only", flush=True)
    if options.suite == "api":
        os.chdir(API)
        owned_cluster_factory = target_module.owned_cluster_factory
        receipt_path = options.target_receipt.resolve()
        root_factory, root_name = None, None
        if options.fresh_target:
            root_factory = owned_cluster_factory(receipt_path)
            root_name, fresh_dsn = root_factory()
            receipt_path = receipt_path.parent / (root_name.removeprefix("buyeros-") + ".target.json")
            os.environ.update(BUYEROS_TEST_DATABASE_URL=fresh_dsn, BUYEROS_DATABASE_URL=fresh_dsn,
                              BUYEROS_DATABASE_MIGRATION_URL=fresh_dsn, BUYEROS_POLICY_TARGET_RECEIPT=str(receipt_path))
        from tests.conftest import DB_NAME
        factory = owned_cluster_factory(receipt_path, database_name=DB_NAME)
        import pytest
        try:
            return pytest.main(rest, plugins=[OwnedFixturePlugin(factory, target_module.assert_owned_test_dsn)])
        finally:
            if root_factory and root_name:
                remove_owned(root_factory.created[root_name])
    if options.suite == "worker":
        owned_cluster_factory = target_module.owned_cluster_factory
        if not options.worker_process:
            factory = owned_cluster_factory(options.target_receipt.resolve(), database_name="buyeros_test_worker")
            name, worker_dsn = factory()
            receipt = options.target_receipt.resolve().parent / (name.removeprefix("buyeros-") + ".target.json")
            os.environ.update(BUYEROS_TEST_DATABASE_URL=worker_dsn, BUYEROS_DATABASE_URL=worker_dsn,
                              BUYEROS_DATABASE_MIGRATION_URL=worker_dsn, BUYEROS_POLICY_TARGET_RECEIPT=str(receipt))
            python = ROOT / "services/worker/.venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            if not python.is_file():
                raise RuntimeError("frozen worker environment required; no interpreter fallback")
            try:
                return subprocess.call([str(python), str(Path(__file__).resolve()),
                    "--target-receipt", str(receipt), "--suite", "worker", "--worker-process", "--", *rest],
                    cwd=ROOT / "services/worker")
            finally:
                remove_owned(factory.created[name])
        factory = owned_cluster_factory(options.target_receipt.resolve(), database_name="buyeros_test_worker")
        # Worker and API both intentionally have a package called tests. The
        # gate has already run; retain its allocator object, then select only
        # the worker namespace for pytest. Do not substitute its fixture model.
        for name in tuple(sys.modules):
            if name == "tests" or name.startswith("tests."):
                sys.modules.pop(name, None)
        worker = ROOT / "services/worker"
        os.chdir(worker)
        sys.path.insert(0, str(worker))
        import pytest
        return pytest.main(rest, plugins=[OwnedFixturePlugin(factory, target_module.assert_owned_test_dsn)])
    if rest:
        parser.error("browser suite does not accept arbitrary commands or origins")
    owned_cluster_factory = target_module.owned_cluster_factory
    factory = owned_cluster_factory(options.target_receipt.resolve())
    name, browser_dsn = factory()
    receipt = options.target_receipt.resolve().parent / (name.removeprefix("buyeros-") + ".target.json")
    os.environ.update(BUYEROS_TEST_DATABASE_URL=browser_dsn, BUYEROS_DATABASE_URL=browser_dsn,
                      BUYEROS_DATABASE_MIGRATION_URL=browser_dsn, BUYEROS_POLICY_TARGET_RECEIPT=str(receipt))
    config = "playwright.lead-workflow.config.ts" if options.native_browser else "playwright.policy-activation.config.ts"
    try:
        command = ["pnpm.cmd" if os.name == "nt" else "pnpm", "exec", "playwright", "test", "--config", config]
        # Playwright clears its outputDir before execution. Retain the original
        # pre-run inventory beside this exact owned child receipt instead.
        discovery = receipt.with_name(receipt.stem + (
            ".native-discovery.json" if options.native_browser else ".policy-discovery.json"))
        with discovery.open("x", encoding="utf-8") as output:
            result = subprocess.call([*command, "--list", "--reporter=json"], cwd=ROOT, stdout=output)
        if result:
            return result
        print(f"Original browser discovery retained: {discovery}", flush=True)
        selectors = ["--grep", "^admin_submits_and_designated_owner_decides_exact_terms$", "--max-failures=1"] if options.browser_phase == "red" else []
        return subprocess.call([*command, "--workers=1", *selectors], cwd=ROOT)
    finally:
        remove_owned(factory.created[name])


def remove_owned(container_id):
    result = subprocess.run(["docker", "rm", "-f", "-v", container_id],
                            capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise RuntimeError("owned cleanup failed; preserve receipt and stop")


if __name__ == "__main__":
    raise SystemExit(main())
