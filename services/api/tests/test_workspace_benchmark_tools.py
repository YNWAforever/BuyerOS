"""Opt-in directory runner must refuse inherited database configuration."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[3]
RUNNER=ROOT/'scripts/benchmark-workspace-directory.py'
DATABASE_VARIABLES=('BUYEROS_TEST_DATABASE_URL','BUYEROS_DATABASE_URL','DATABASE_URL','BUYEROS_WORKER_DATABASE_URL')


@pytest.mark.parametrize('variable',DATABASE_VARIABLES)
def test_directory_runner_refuses_inherited_dsn_without_starting_db(variable,tmp_path):
    assert RUNNER.is_file(),'Q10 owned workspace benchmark runner missing'
    env={k:v for k,v in os.environ.items() if k not in DATABASE_VARIABLES}
    env[variable]='postgresql://never-connect.example/shared'
    result=subprocess.run([sys.executable,str(RUNNER),'--output',str(tmp_path/'new.json')],env=env,capture_output=True,text=True,timeout=30)
    assert result.returncode==2 and variable in result.stderr
    assert not list(tmp_path.iterdir())


def test_directory_runner_preserves_existing_evidence(tmp_path):
    assert RUNNER.is_file(),'Q10 owned workspace benchmark runner missing'
    path=tmp_path/'existing.json';path.write_bytes(b'original evidence')
    env={k:v for k,v in os.environ.items() if k not in DATABASE_VARIABLES}
    result=subprocess.run([sys.executable,str(RUNNER),'--output',str(path)],env=env,capture_output=True,text=True,timeout=30)
    assert result.returncode==2 and path.read_bytes()==b'original evidence'


def test_directory_runner_rejects_insufficient_samples(tmp_path):
    assert RUNNER.is_file(),'Q10 owned workspace benchmark runner missing'
    env={k:v for k,v in os.environ.items() if k not in DATABASE_VARIABLES}
    result=subprocess.run([sys.executable,str(RUNNER),'--samples','0','--output',str(tmp_path/'new.json')],env=env,capture_output=True,text=True,timeout=30)
    assert result.returncode==2 and not list(tmp_path.iterdir())


def test_partial_directory_runner_refuses_unverified_actor_matrix_before_dispatch(monkeypatch,tmp_path):
    import importlib.util
    spec=importlib.util.spec_from_file_location('directory_runner_review',RUNNER)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    for key in DATABASE_VARIABLES:monkeypatch.delenv(key,raising=False)
    monkeypatch.setattr(sys,'argv',[str(RUNNER),'--actors','10','--output',str(tmp_path/'new.json')])
    def forbidden(*args,**kwargs):raise AssertionError('unverified actor option reached DB dispatch')
    monkeypatch.setattr(module.subprocess,'run',forbidden)
    with pytest.raises(SystemExit) as refused:module.main()
    assert refused.value.code==2 and not list(tmp_path.iterdir())
