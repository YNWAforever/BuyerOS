"""CLI boundaries use a child process; never a production URL or credential."""
import json
import os
from pathlib import Path
import subprocess
import sys
import asyncio
import importlib.util

import psycopg
from tests.policy_activation_fixtures import policy_case, manifest_body

SCRIPT = Path(__file__).resolve().parents[3] / "scripts/policy-authority.py"


def test_cli_requires_explicit_migration_url_without_application_fallback(tmp_path):
    assert SCRIPT.is_file(), "authority CLI is not implemented"
    empty = tmp_path / "empty.json"
    empty.write_text("{}", encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if not k.startswith("BUYEROS_")}
    env["BUYEROS_DATABASE_URL"] = "postgresql://do-not-use@production.invalid/neondb"
    result = subprocess.run([sys.executable, str(SCRIPT), "--manifest", str(empty),
                             "--authorization", str(empty), "--target-contract", str(empty)],
                            env=env, capture_output=True, text=True, timeout=15)
    assert result.returncode == 2
    assert json.loads(result.stdout)["code"] == "MIGRATION_URL_REQUIRED"
    assert "production.invalid" not in result.stdout + result.stderr


def test_cli_default_dry_run_does_not_write(policy_case, tmp_path):
    assert SCRIPT.is_file(), "authority CLI is not implemented"
    from buyeros_api.services.policy_activation_bootstrap import AuthorityManifest, manifest_digest
    manifest = AuthorityManifest.model_validate(manifest_body(policy_case))
    auth = {"manifest_sha256": manifest_digest(manifest), "target_sha256": manifest.target_sha256,
            "source_sha": manifest.source_sha, "approval_reference": "fixture://approved-run",
            "approval_evidence_sha256": "b" * 64}
    contract = {"target_sha256": manifest.target_sha256, "source_sha": manifest.source_sha}
    paths = []
    for name, body in (("manifest", manifest.model_dump(mode="json")), ("authorization", auth), ("target", contract)):
        path = tmp_path / (name + ".json")
        path.write_text(json.dumps(body), encoding="utf-8")
        paths.append(str(path))
    env = {k: v for k, v in os.environ.items() if not k.startswith("BUYEROS_")}
    env["BUYEROS_DATABASE_MIGRATION_URL"] = policy_case["dsn"]
    result = subprocess.run([sys.executable, str(SCRIPT), "--manifest", paths[0],
                             "--authorization", paths[1], "--target-contract", paths[2]],
                            env=env, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["mode"] == "dry-run"
    with psycopg.connect(policy_case["dsn"]) as db:
        assert db.execute("SELECT count(*) FROM policy_controller_authorities").fetchone()[0] == 0


def test_cli_lost_commit_response_is_unknown_not_invalid_input(policy_case, tmp_path, monkeypatch, capsys):
    from buyeros_api.services.policy_activation_bootstrap import AuthorityManifest, manifest_digest
    manifest = AuthorityManifest.model_validate(manifest_body(policy_case))
    auth = {"manifest_sha256": manifest_digest(manifest), "target_sha256": manifest.target_sha256,
            "source_sha": manifest.source_sha, "approval_reference": "fixture://approved-run",
            "approval_evidence_sha256": "b" * 64}
    paths = []
    for name, body in (("manifest", manifest.model_dump(mode="json")), ("authorization", auth),
                       ("target", {"target_sha256": manifest.target_sha256, "source_sha": manifest.source_sha})):
        p = tmp_path / (name + ".json")
        p.write_text(json.dumps(body), encoding="utf-8")
        paths.append(str(p))
    monkeypatch.setenv("BUYEROS_DATABASE_MIGRATION_URL", policy_case["dsn"])
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "--manifest", paths[0], "--authorization", paths[1],
                                    "--target-contract", paths[2], "--mode", "apply"])
    real_run = asyncio.Runner.run
    def lose_after_commit(self, coro, *args, **kwargs):
        real_run(self, coro, *args, **kwargs)
        raise OSError("synthetic response lost after confirmed DB commit")
    spec = importlib.util.spec_from_file_location("owned_authority_cli", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with monkeypatch.context() as patch:
        patch.setattr(asyncio.Runner, "run", lose_after_commit)
        result = module.main()
    assert result == 3
    data = json.loads(capsys.readouterr().out)
    assert data["unknown_outcome"] is True and data["manifest_sha256"] == manifest_digest(manifest)
    with psycopg.connect(policy_case["dsn"]) as db:
        assert db.execute("SELECT count(*) FROM policy_controller_authorities").fetchone()[0] == 1
