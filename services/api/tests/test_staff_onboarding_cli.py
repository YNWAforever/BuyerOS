"""CLI parsing/output contracts; DB and real signature behavior are separately required."""
import importlib.util
import json
from pathlib import Path

import pytest


def tool():
    path = Path(__file__).resolve().parents[1] / 'tools/reconcile_staff_membership.py'
    spec = importlib.util.spec_from_file_location('c61_staff_tool', path)
    module = importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('apply', [False, True])
def test_cli_default_is_dry_run_and_token_is_only_read_from_environment(tmp_path, monkeypatch, capsys, apply):
    module = tool();seen = []
    manifest = tmp_path / 'manifest.json';manifest.write_text('[]')
    async def inspect(value, *, token, apply):
        seen.append((value, token, apply))
        return [{'status': 'created' if apply else 'would-create'}]
    monkeypatch.setattr(module, 'reconcile_staff_manifest', inspect)
    monkeypatch.setenv('BUYEROS_STAFF_ADMIN_TOKEN', 'CANARY_PRIVATE_TOKEN')
    argv = ['--manifest', str(manifest)] + (['--apply'] if apply else [])
    assert module.main(argv) == 0
    assert seen == [([], 'CANARY_PRIVATE_TOKEN', apply)]
    output = capsys.readouterr().out
    assert 'CANARY_PRIVATE_TOKEN' not in output and json.loads(output)['apply'] is apply


def test_cli_missing_token_fails_without_any_database_call(tmp_path, monkeypatch, capsys):
    module = tool();path = tmp_path / 'manifest.json';path.write_text('[]')
    monkeypatch.delenv('BUYEROS_STAFF_ADMIN_TOKEN', raising=False)
    async def forbidden(*args, **kwargs):
        pytest.fail('missing token must not open a database')
    monkeypatch.setattr(module, 'reconcile_staff_manifest', forbidden)
    assert module.main(['--manifest', str(path)]) == 2
    assert json.loads(capsys.readouterr().out) == {'error': {'code': 'UNAUTHENTICATED'}}


def test_cli_duplicate_json_keys_are_rejected_before_execution(tmp_path, monkeypatch, capsys):
    module = tool();path = tmp_path / 'manifest.json';path.write_text('[{"roles":["viewer"],"roles":["workspace_admin"]}]')
    monkeypatch.setenv('BUYEROS_STAFF_ADMIN_TOKEN', 'CANARY_PRIVATE_TOKEN')
    async def forbidden(*args, **kwargs):
        pytest.fail('ambiguous manifest must not execute')
    monkeypatch.setattr(module, 'reconcile_staff_manifest', forbidden)
    assert module.main(['--manifest', str(path)]) == 2
    output = capsys.readouterr().out
    assert json.loads(output) == {'error': {'code': 'INVALID_MANIFEST'}} and 'CANARY_PRIVATE_TOKEN' not in output
