"""CLI admission contract; DB/JWT authority is covered by actual DB tests."""
import importlib.util
import json
from pathlib import Path

def tool():
    path=Path(__file__).resolve().parents[1]/'tools/link_user_identities.py'
    spec=importlib.util.spec_from_file_location('c61_identity_tool',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def test_cli_never_falls_back_to_general_owner_database(tmp_path,monkeypatch,capsys):
    module=tool();manifest=tmp_path/'manifest.json';manifest.write_text('[]')
    monkeypatch.setenv('BUYEROS_IDENTITY_ADMIN_TOKEN','fixture-invalid-token')
    monkeypatch.delenv('BUYEROS_IDENTITY_WRITER_DATABASE_URL',raising=False)
    monkeypatch.setenv('BUYEROS_DATABASE_URL','postgresql://negative-canary@db.invalid/buyeros')
    def forbidden(*a,**k):raise AssertionError('must not create a fallback connection')
    monkeypatch.setattr(module,'create_async_engine',forbidden)
    assert module.main(['--manifest',str(manifest)])==2
    result=json.loads(capsys.readouterr().out);assert result=={'error':{'code':'IDENTITY_WRITER_UNAVAILABLE'}}

def test_cli_rejects_duplicate_json_keys_before_engine_or_credentials(tmp_path,monkeypatch,capsys):
    module=tool();manifest=tmp_path/'manifest.json';manifest.write_text('[{"issuer":"one","issuer":"two"}]')
    def forbidden(*a,**k):raise AssertionError('must reject duplicate manifest before connection')
    monkeypatch.setattr(module,'create_async_engine',forbidden)
    assert module.main(['--manifest',str(manifest)])==2
    assert json.loads(capsys.readouterr().out)=={'error':{'code':'INVALID_MANIFEST'}}

def test_cli_requires_explicit_apply_flag(tmp_path,monkeypatch,capsys):
    module=tool();manifest=tmp_path/'manifest.json';manifest.write_text('[{}]');seen=[]
    monkeypatch.setenv('BUYEROS_IDENTITY_ADMIN_TOKEN','fixture-token')
    monkeypatch.setenv('BUYEROS_IDENTITY_WRITER_DATABASE_URL','postgresql://fixture@127.0.0.1/buyeros_test_cli')
    class Engine:
        async def dispose(self):pass
    monkeypatch.setattr(module,'create_async_engine',lambda *a,**k:Engine())
    async def reconcile(rows,**kwargs):seen.append(kwargs['apply']);return [{'status':'would-link' if not kwargs['apply'] else 'linked'}]
    monkeypatch.setattr(module,'reconcile_identity_manifest',reconcile)
    assert module.main(['--manifest',str(manifest)])==0
    assert seen==[False] and json.loads(capsys.readouterr().out)['apply'] is False
