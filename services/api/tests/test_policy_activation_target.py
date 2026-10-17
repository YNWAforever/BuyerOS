import importlib
import importlib.util

import pytest


def validator():
    assert importlib.util.find_spec("tests.policy_activation_target"), "owned target gate is not implemented"
    return importlib.import_module("tests.policy_activation_target").assert_owned_target


def target():
    receipt = {
        "run_id": "synthetic-policy-run", "container_id": "c" * 64, "image_id": "sha256:" + "d" * 64,
        "host": "127.0.0.1", "port": 62481, "database": "buyeros_test_policy",
        "auth_issuer": "https://oidc.buyeros.test/", "owns_entire_container": True,
        "docker_context": "desktop-linux",
    }
    metadata = {
        "id": "c" * 64, "image_id": "sha256:" + "d" * 64,
        "labels": {"buyeros.policy.run": "synthetic-policy-run"},
        "ports": {"5432/tcp": [{"HostIp": "127.0.0.1", "HostPort": "62481"}]},
        "mounts": [], "running": True,
        "docker_context": "desktop-linux", "docker_endpoint": "npipe:////./pipe/dockerDesktopLinuxEngine",
    }
    env = {"host": "127.0.0.1", "port": 62481, "database": "buyeros_test_policy",
           "auth_issuer": "https://oidc.buyeros.test/"}
    return receipt, metadata, env


def test_target_gate_precedes_any_database_client():
    gate = validator()
    receipt, meta, env = target()
    calls = []
    with pytest.raises(ValueError):
        # A successful validation is the only route to the client constructor.
        verified = gate(receipt, {**meta, "id": "x" * 64}, env)
        calls.append(verified)
    assert calls == []


@pytest.mark.parametrize("change", [
    {"host": "production.neon.tech"}, {"port": 5432}, {"database": "neondb"},
    {"auth_issuer": "https://company-auth.example.com/"},
])
def test_gate_rejects_endpoint_and_auth_drift(change):
    gate = validator()
    receipt, meta, env = target()
    with pytest.raises(ValueError):
        gate(receipt, meta, {**env, **change})


def test_owned_gate_requires_independent_labels_image_and_loopback_mapping():
    gate = validator()
    receipt, meta, env = target()
    assert gate(receipt, meta, env).database == "buyeros_test_policy"
    for change in [
        {"labels": {}}, {"image_id": "sha256:" + "f" * 64},
        {"ports": {"5432/tcp": [{"HostIp": "0.0.0.0", "HostPort": "62481"}]}},
        {"mounts": [{"Type": "bind", "Source": "C:/shared"}]}, {"running": False},
        {"docker_endpoint": "ssh://shared-server"},
    ]:
        with pytest.raises(ValueError):
            gate(receipt, {**meta, **change}, env)
def test_owned_allocator_covers_worker_conftest_alias_before_fixture_setup():
    from types import SimpleNamespace
    from pathlib import Path
    from tools.run_policy_activation_tests import OwnedFixturePlugin
    root = Path(__file__).resolve().parents[3]
    def allocate():
        return "verified-child", "no-network-sentinel"
    allocate.created = {}
    module = SimpleNamespace(__file__=str(root / "services/worker/tests/conftest.py"),
                             _start_container=lambda: (_ for _ in ()).throw(AssertionError("unverified allocator")),
                             _docker=lambda *args: None)
    plugin = OwnedFixturePlugin(allocate)
    plugin.install(module)
    assert module._start_container() == ("verified-child", "no-network-sentinel")


def test_remote_docker_override_is_refused_before_metadata_or_sql(tmp_path, monkeypatch):
    import json
    import subprocess
    from tests.policy_activation_target import inspect_target
    receipt, _, _ = target()
    path = tmp_path / "synthetic.target.json"
    path.write_text(json.dumps(receipt), encoding="utf-8")
    monkeypatch.setenv("DOCKER_HOST", "tcp://remote.example.test:2376")
    def forbidden(*args, **kwargs):
        raise AssertionError("Docker metadata contacted before local transport gate")
    monkeypatch.setattr(subprocess, "check_output", forbidden)
    with pytest.raises(ValueError, match="Docker transport"):
        inspect_target(path)


def test_ci_target_constructor_refuses_remote_transport_before_allocation(tmp_path, monkeypatch):
    name = "tools.create_policy_test_target"
    assert importlib.util.find_spec(name) is not None, "owned CI target constructor missing"
    module = importlib.import_module(name)
    monkeypatch.setenv("DOCKER_HOST", "tcp://remote.example.test:2376")
    with pytest.raises(ValueError, match="Docker transport"):
        module.create_target(tmp_path / "owned.target.json")


def test_owned_readiness_waits_for_real_host_sql_after_temporary_init_server(monkeypatch):
    import psycopg
    from types import SimpleNamespace
    from tests import policy_activation_target as module
    assert hasattr(module, "wait_for_owned_sql"), "host SQL readiness probe missing"
    monkeypatch.setattr(module, "_VERIFIED_ENDPOINTS", {("127.0.0.1", 62481)})
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    attempts = []
    class Ready:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def execute(self, sql):
            assert sql == "SHOW server_version_num"
            return SimpleNamespace(fetchone=lambda: (180006,))
    def connect(dsn, *, connect_timeout):
        attempts.append(dsn)
        if len(attempts) == 1:
            raise psycopg.OperationalError("temporary init server restarted before host forwarding")
        return Ready()
    monkeypatch.setattr(psycopg, "connect", connect)
    result = module.wait_for_owned_sql("postgresql://fixture@127.0.0.1:62481/buyeros_test_policy")
    assert result == 180006 and len(attempts) == 2


def test_owned_allocator_preserves_legacy_database_name_in_container_receipt_and_dsn(tmp_path, monkeypatch):
    """A dump/restore command's DB_NAME must name the actually owned database."""
    import json
    from urllib.parse import urlsplit
    from tests import policy_activation_target as module
    receipt, _, _ = target()
    path = tmp_path / "parent.target.json"
    path.write_text(json.dumps(receipt), encoding="utf-8")
    monkeypatch.delenv("DOCKER_HOST", raising=False)
    monkeypatch.setattr(module, "_VERIFIED_ENDPOINTS", set())
    monkeypatch.setattr(module, "wait_for_owned_sql", lambda _: 180006)
    for database in ("buyeros_test_api", "buyeros_test_worker"):
        observed = {}
        def command(args, **kwargs):
            if args[:2] == ["docker", "run"]:
                observed["args"] = args
                observed["label"] = args[args.index("--label") + 1].split("=", 1)[1]
                return "e" * 64
            if args[:2] == ["docker", "inspect"]:
                return json.dumps([{"Id": "e" * 64, "Image": receipt["image_id"],
                    "Config": {"Labels": {"buyeros.policy.run": observed["label"]}},
                    "NetworkSettings": {"Ports": {"5432/tcp": [{"HostIp": "127.0.0.1", "HostPort": "62481"}]}},
                    "Mounts": [], "State": {"Running": True}}])
            if args == ["docker", "context", "show"]:
                return "desktop-linux"
            if args[:3] == ["docker", "context", "inspect"]:
                return "npipe:////./pipe/dockerDesktopLinuxEngine"
            raise AssertionError("unexpected metadata command")
        monkeypatch.setattr(module.subprocess, "check_output", command)
        allocate = module.owned_cluster_factory(path, database_name=database)
        name, dsn = allocate()
        saved = json.loads((tmp_path / (name.removeprefix("buyeros-") + ".target.json")).read_text())
        assert f"POSTGRES_DB={database}" in observed["args"]
        assert urlsplit(dsn).path == "/" + database and saved["database"] == database
    with pytest.raises(ValueError):
        module.owned_cluster_factory(path, database_name="neondb")
