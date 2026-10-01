"""A separately prepared preview overlay cannot turn into a production executor."""
import hashlib
import hmac
import importlib.util
import json
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = ROOT / "scripts/cloudflare-preview/runtime_probe.py"
PREPARER = ROOT / "scripts/prepare-cloudflare-preview.py"
NOW = datetime.now(timezone.utc)
SECRET = "fictional-preview-secret-at-least-32-bytes"
PATH = "/v1/internal/runtime-probe"


def load_module(path, name):
    assert path.is_file(), "protected preview diagnostic preparation is missing"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def target():
    return {"vercel_project_id": "prj_fixture_preview", "vercel_project_name": "buyeros-cf-preview",
            "neon_project_id": "fictional-preview-12345678", "neon_project_name": "BuyerOS-CF-preview-20261001",
            "neon_branch_id": "br-fictional-preview", "neon_host": "ep-fictional-preview.ap-southeast-1.aws.neon.tech",
            "database": "buyeros_cf_preview", "worker_role": "buyeros_cf_preview_worker",
            "api_role": "buyeros_cf_preview_api", "source_sha": "a" * 40,
            "session_started_at": NOW.isoformat(), "expires_at": (NOW + timedelta(hours=2)).isoformat()}


def environment():
    worker = "postgresql://buyeros_cf_preview_worker:fictional@" + target()["neon_host"] + "/buyeros_cf_preview?sslmode=require"
    return {"VERCEL_ENV": "preview", "VERCEL_PROJECT_ID": target()["vercel_project_id"],
            "BUYEROS_PREVIEW_PROBE_ENABLED": "true", "BUYEROS_PREVIEW_PROBE_SOURCE_SHA": "a" * 40,
            "BUYEROS_PREVIEW_PROBE_KEY_ID": "cf-preview-fixture", "BUYEROS_PREVIEW_PROBE_SECRET": SECRET,
            "BUYEROS_EXECUTION_DATABASE_URL": worker, "BUYEROS_CHECKPOINT_DATABASE_URL": worker,
            "BUYEROS_DATABASE_URL": worker.replace("buyeros_cf_preview_worker:", "buyeros_cf_preview_api:")}


def headers(body, *, path=PATH, nonce=None, now=None):
    stamp = str(int((now or datetime.now(timezone.utc)).timestamp()))
    nonce = str(uuid.uuid4()) if nonce is None else nonce
    message = f"POST\n{path}\n{stamp}\n{nonce}\n{hashlib.sha256(body).hexdigest()}".encode()
    return {"x-buyeros-worker-key-id": "cf-preview-fixture", "x-buyeros-worker-timestamp": stamp,
            "x-buyeros-worker-nonce": nonce,
            "x-buyeros-worker-signature": hmac.new(SECRET.encode(), message, hashlib.sha256).hexdigest()}


@pytest.mark.parametrize("change", [
    {"BUYEROS_PREVIEW_PROBE_ENABLED": "false"}, {"VERCEL_ENV": "production"},
    {"VERCEL_PROJECT_ID": "prj_qLOzTdqNiKvoS5rBjy5zZ2GeZgMw"},
    {"BUYEROS_PREVIEW_PROBE_SOURCE_SHA": "b" * 40},
    {"BUYEROS_EXECUTION_DATABASE_URL": "postgresql://owner:secret@production.neon.tech/neondb"},
    {"BUYEROS_DATABASE_MIGRATION_URL": "postgresql://owner:secret@production.neon.tech/neondb"},
    {"BUYEROS_PAID_ADMISSION_ENABLED": "true"}, {"BUYEROS_R2_ENABLED": "true"},
    {"BUYEROS_CLOUDFLARE_EXECUTION_ENABLED": "true"}, {"BUYEROS_PREVIEW_PROBE_SECRET": "short"},
])
def test_preview_guard_denies_before_any_runtime_io(change):
    module = load_module(TEMPLATE, "cf_preview_diagnostic")
    with pytest.raises(ValueError):
        module.require_preview(target(), environment() | change, NOW)


@pytest.mark.parametrize("change", [
    {"neon_project_id": "nameless-bar-15324691"}, {"vercel_project_name": "buyer-os"},
    {"expires_at": (NOW - timedelta(seconds=1)).isoformat()},
    {"expires_at": (NOW + timedelta(hours=3)).isoformat()},
    {"worker_role": "neondb_owner"}, {"neon_host": "localhost"}, {"source_sha": "main"},
    {"secret": "must-never-be-in-a-target-manifest"},
])
def test_preview_target_pins_fresh_names_roles_and_two_hour_window(change):
    module = load_module(TEMPLATE, "cf_preview_diagnostic")
    with pytest.raises(ValueError):
        module.require_preview(target() | change, environment(), NOW)


def test_preview_guard_accepts_only_pinned_tls_database_and_non_owner_roles():
    module = load_module(TEMPLATE, "cf_preview_diagnostic")
    assert module.require_preview(target(), environment(), NOW) == environment()["BUYEROS_CHECKPOINT_DATABASE_URL"]
    for suffix in ("&host=production.neon.tech", "#other", "&sslmode=disable", "&options=-csearch_path=public"):
        env = environment()
        env["BUYEROS_CHECKPOINT_DATABASE_URL"] += suffix
        with pytest.raises(ValueError):
            module.require_preview(target(), env, NOW)


def test_preview_signature_is_distinct_and_binds_exact_request():
    module = load_module(TEMPLATE, "cf_preview_diagnostic")
    raw = b'{"operation":"native"}'
    good = headers(raw, now=NOW)
    principal = module.verify_probe_request(raw, good, environment(), NOW)
    assert principal.key_id == "cf-preview-fixture"
    for body, supplied in ((raw + b" ", good), (raw, headers(raw, path="/v1/internal/worker/claim", now=NOW)),
                           (raw, good | {"x-buyeros-worker-nonce": "not-a-uuid"}),
                           (raw, good | {"x-buyeros-worker-timestamp": "0"}), (raw, {})):
        with pytest.raises(Exception) as exc:
            module.verify_probe_request(body, supplied, environment(), NOW)
        assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_disabled_preview_and_release_api_have_no_diagnostic(monkeypatch):
    from buyeros_api.api.app import create_app
    module = load_module(TEMPLATE, "cf_preview_diagnostic")
    monkeypatch.delenv("BUYEROS_PREVIEW_PROBE_ENABLED", raising=False)
    for app in (module.create_preview_app(target()), create_app()):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://fixture") as client:
            response = await client.post(PATH, content=b'{"operation":"native"}')
            assert response.status_code == 404
        assert PATH not in app.openapi()["paths"]


@pytest.mark.asyncio
async def test_preview_rejects_unsigned_query_and_unknown_operations_before_io(monkeypatch):
    module = load_module(TEMPLATE, "cf_preview_diagnostic")
    for key, value in environment().items():
        monkeypatch.setenv(key, value)
    app = module.create_preview_app(target())
    raw = b'{"operation":"native"}'
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://fixture") as client:
        assert (await client.post(PATH, content=raw)).status_code == 401
        assert (await client.post(PATH + "?dsn=production", content=raw, headers=headers(raw))).status_code == 401
        for body in (b'{"operation":"native","dsn":"production"}', b'{"operation":"delivery"}',
                     b'{"operation":"native","operation":"duration"}', b"not-json"):
            result = await client.post(PATH, content=body, headers=headers(body))
            assert result.status_code == 422
        assert (await client.post(PATH, content=b"x" * 257)).status_code == 413


def test_prepared_overlay_preserves_release_routes_and_binds_ninety_second_budgets(tmp_path):
    module = load_module(PREPARER, "cf_preview_preparer")
    paths = (ROOT / "vercel.json", ROOT / "app/v1/[...path]/route.ts")
    before = {str(path): path.read_bytes() for path in paths}
    files = module.render_overlay(ROOT, target())
    config = json.loads(files["vercel.json"])
    assert config["services"]["api"]["entrypoint"] == "buyeros_api.api.preview_vercel:app"
    assert config["services"]["api"]["functions"] == {"buyeros_api/api/preview_vercel.py": {"maxDuration": 90}}
    assert config["rewrites"] == json.loads(before[str(paths[0])])["rewrites"]
    route = files["app/v1/[...path]/route.ts"]
    assert "'/v1/internal/runtime-probe'" in route
    assert "x-vercel-protection-bypass" not in route
    assert before == {str(path): path.read_bytes() for path in paths}
    assert "BUYEROS_PREVIEW_PROBE_ENABLED" not in before[str(paths[1])].decode()
    assert module.DURATION_SECONDS == 61


def test_preparer_guard_import_has_no_application_side_effects():
    module = load_module(TEMPLATE, "cf_preview_diagnostic")
    assert not hasattr(module, "app"), "the overlay template must be safe for the stdlib-only preparer to import"


def test_native_child_requires_compiled_target_before_driver_io(monkeypatch, capsys):
    import io
    module = load_module(TEMPLATE, "cf_preview_diagnostic")
    data = {"target": target(), "dsn": environment()["BUYEROS_CHECKPOINT_DATABASE_URL"]}
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(json.dumps(data).encode())))
    def forbidden(*_args):
        raise AssertionError("native driver I/O must not run without the compiled target")
    monkeypatch.setattr(module, "native_checks", forbidden)
    assert module.main_child() == 1
    assert json.loads(capsys.readouterr().out) == {"error_type": "ValueError"}


def test_preparer_accepts_clean_windows_checkout_but_refuses_changes_or_unsafe_output(tmp_path, monkeypatch):
    import subprocess
    module = load_module(PREPARER, "cf_preview_preparer")
    paths = ("scripts/cloudflare-preview/runtime_probe.py", "scripts/prepare-cloudflare-preview.py",
             "vercel.json", "app/v1/[...path]/route.ts")
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=tmp_path, stderr=subprocess.DEVNULL, text=True).strip()
    git("init", "--quiet")
    git("config", "core.autocrlf", "true")
    (tmp_path / ".gitattributes").write_text("* text eol=crlf\n", encoding="utf-8")
    for relative in paths:
        file = tmp_path / relative
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes((ROOT / relative).read_bytes())
    git("add", "--", ".gitattributes", *paths)
    git("-c", "user.name=BuyerOS Fixture", "-c", "user.email=fixture@example.test", "commit", "--quiet", "-m", "fixture")
    for relative in paths:
        file = tmp_path / relative
        file.write_bytes(file.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
    git("diff", "--exit-code", "HEAD", "--", *paths)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    inputs = tmp_path / "target.json"
    inputs.write_text(json.dumps(target() | {"source_sha": git("rev-parse", "HEAD")}), encoding="utf-8")
    destination = tmp_path / ".sites-runtime/cf-preview-fixture"
    report = module.prepare_overlay(inputs, destination)
    assert report["hosted_verified"] is False
    for relative, digest in report["files_sha256"].items():
        assert hashlib.sha256((destination / relative).read_bytes()).hexdigest() == digest
    for unsafe in (destination, tmp_path / "outside"):
        with pytest.raises(ValueError, match="new owned"):
            module.prepare_overlay(inputs, unsafe)
    file = tmp_path / paths[-1]
    file.write_text(file.read_text(encoding="utf-8") + "\n// Unreviewed change\n", encoding="utf-8")
    with pytest.raises(ValueError, match="commit and review"):
        module.prepare_overlay(inputs, tmp_path / ".sites-runtime/cf-preview-unreviewed")


@pytest.fixture(scope="module")
def probe_database():
    from tests.cloudflare_fixtures import cloudflare_database
    # Reuse the owned module-scoped fixture, never a supplied/shared DB.
    yield from cloudflare_database.__wrapped__()


@pytest.fixture
def local_probe_app(probe_database, monkeypatch):
    import psycopg
    from urllib.parse import urlsplit, urlunsplit
    from buyeros_api.settings import get_settings
    from tests.conftest import _require_disposable_test_dsn
    _require_disposable_test_dsn(probe_database)
    with psycopg.connect(probe_database, autocommit=True) as db:
        db.execute("CREATE ROLE buyeros_cf_preview_worker LOGIN PASSWORD 'test-only' IN ROLE buyeros_worker")
    parsed = urlsplit(probe_database)
    dsn = urlunsplit(parsed._replace(netloc=f"buyeros_cf_preview_worker:test-only@127.0.0.1:{parsed.port}"))
    module = load_module(TEMPLATE, "cf_preview_diagnostic")
    for key, value in environment().items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("BUYEROS_EXECUTION_DATABASE_URL", dsn)
    # Host/TLS guard is tested separately. This fixture exercises the handler's
    # real PostgreSQL nonce path only, without adding a remote/loopback override.
    monkeypatch.setattr(module, "require_preview", lambda *_: dsn)
    get_settings.cache_clear()
    yield module, module.create_preview_app(target()), dsn
    get_settings.cache_clear()
    with psycopg.connect(probe_database, autocommit=True) as db:
        db.execute("DROP ROLE buyeros_cf_preview_worker")


@pytest.mark.asyncio
async def test_preview_failure_commits_nonce_and_hides_exception_details(local_probe_app, monkeypatch):
    module, app, _dsn = local_probe_app
    def fail(*_args):
        raise RuntimeError("secret DSN and credential must not appear in response")
    monkeypatch.setattr(module, "run_native_probe", fail)
    raw = b'{"operation":"native"}'
    signed = headers(raw)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://fixture") as client:
        result = await client.post(PATH, content=raw, headers=signed)
        assert result.status_code == 503
        assert result.json() == {"code": "PROBE_FAILED", "error_type": "RuntimeError"}
        assert "credential" not in result.text
        assert result.headers["cache-control"] == "private, no-store"
        assert (await client.post(PATH, content=raw, headers=signed)).status_code == 409


@pytest.mark.asyncio
async def test_preview_actual_sixty_one_second_sleep_and_durable_replay(local_probe_app):
    module, app, _dsn = local_probe_app
    raw = b'{"operation":"duration"}'
    signed = headers(raw)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://fixture") as client:
        result = await client.post(PATH, content=raw, headers=signed)
        assert result.status_code == 200, result.text
        assert result.json()["slept_seconds"] == 61
        assert result.json()["wall_seconds"] >= 61
        assert result.json()["hosted_feasible"] is False
        output = ROOT / "artifacts/cloudflare/CF00-preview-duration-local.json"
        output.write_text(json.dumps({"environment": "local_owned_fixture", "two_hop_hosted": False,
                                      "result": result.json()}, indent=2) + "\n", encoding="utf-8")
    # A fresh application process must still reject the consumed nonce.
    restarted = module.create_preview_app(target())
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=restarted), base_url="http://fixture") as client:
        assert (await client.post(PATH, content=raw, headers=headers(raw, nonce=signed["x-buyeros-worker-nonce"]))).status_code == 409


def test_preview_native_pdf_interruption_and_cross_tenant_checkpoint(local_probe_app):
    module, _app, dsn = local_probe_app
    report = module.native_checks(dsn)
    rows = {row["check"]: row for row in report["records"]}
    assert {key for key, row in rows.items() if row["state"] == "verified"} >= {
        "native_imports", "pdf_native", "pdf_isolation", "pdf_timeout", "postgres_role", "postgres_checkpoint"}
    assert rows["postgres_checkpoint"]["details"]["cross_tenant_read_closed"]
    assert rows["postgres_checkpoint"]["details"]["committed_node_replayed"] is False
    assert report["hosted_feasible"] is False
    assert "test-only" not in json.dumps(report)
    output = ROOT / "artifacts/cloudflare/CF00-preview-native-local.json"
    output.write_text(json.dumps({"environment": "local_owned_fixture", "guard_override": "loopback fixture only",
                                  "child_wrapper_hosted": False, "result": report}, indent=2) + "\n", encoding="utf-8")
