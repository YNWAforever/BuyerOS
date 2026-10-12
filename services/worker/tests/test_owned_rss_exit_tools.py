"""Keep exited-process sampling compatible with the bulk caller's OSError gate."""
import importlib.util
import os
from pathlib import Path
from types import FunctionType, SimpleNamespace

import pytest


def reader():
    spec=importlib.util.spec_from_file_location('owned_rss',Path(__file__).with_name('worker_capacity_driver.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def linux_read(tmp_path,status,reader_module=None):
    file=tmp_path/'status';file.write_text(status,encoding='utf-8')
    function=(reader_module or reader())._process_rss
    bindings=dict(function.__globals__,os=SimpleNamespace(name='posix'),sys=SimpleNamespace(platform='linux'),Path=lambda _:file)
    return FunctionType(function.__code__,bindings)


@pytest.mark.parametrize('state',['Z (zombie)','X (dead)'])
def test_kernel_confirmed_exit_is_oserror_not_live_rss_failure(tmp_path,state):
    read=linux_read(tmp_path,'Name:\towned-child\nState:\t'+state+'\n')
    with pytest.raises(ProcessLookupError):read(12345)


def test_live_process_without_rss_still_refuses_measurement(tmp_path):
    read=linux_read(tmp_path,'Name:\towned-child\nState:\tS (sleeping)\n')
    with pytest.raises(ValueError,match='live process RSS unavailable'):read(12345)


def test_matching_actual_owned_process_reports_positive_rss():
    rss,method=reader()._process_rss(os.getpid())
    assert rss>0 and method in {'linux_proc_status_VmRSS','windows_GetProcessMemoryInfo_WorkingSetSize'}


def owned_poll_sequence(*values):
    results=iter(values)
    return SimpleNamespace(pid=12345,poll=lambda:next(results))


def test_owned_exit_between_initial_poll_and_missing_vmrss_does_not_fabricate_sample(tmp_path,monkeypatch):
    m=reader();monkeypatch.setattr(m,'_owned_process_tree',lambda p:[(p,None,0)])
    monkeypatch.setattr(m,'_process_rss',linux_read(tmp_path,'State:\tR (running)\n',m))
    samples=[]
    m.sample_worker_resources([owned_poll_sequence(None,0)],0,samples)
    assert samples==[]


def test_missing_vmrss_with_live_owned_popen_still_refuses(tmp_path,monkeypatch):
    m=reader();monkeypatch.setattr(m,'_owned_process_tree',lambda p:[(p,None,0)])
    monkeypatch.setattr(m,'_process_rss',linux_read(tmp_path,'State:\tR (running)\n',m))
    with pytest.raises(ValueError,match='live process RSS unavailable'):
        m.sample_worker_resources([owned_poll_sequence(None,None)],0,[])


def test_exited_owner_does_not_hide_invalid_rss_units(tmp_path,monkeypatch):
    m=reader();monkeypatch.setattr(m,'_owned_process_tree',lambda p:[(p,None,0)])
    monkeypatch.setattr(m,'_process_rss',linux_read(tmp_path,'State:\tR (running)\nVmRSS:\t123 wrong\n',m))
    with pytest.raises(ValueError,match='unexpected proc RSS unit'):
        m.sample_worker_resources([owned_poll_sequence(None,0)],0,[])


def test_owner_exit_is_not_proof_that_unmeasured_descendant_exited(tmp_path,monkeypatch):
    m=reader();monkeypatch.setattr(m,'_owned_process_tree',lambda p:[(p+1,p,1)])
    monkeypatch.setattr(m,'_process_rss',linux_read(tmp_path,'State:\tR (running)\n',m))
    with pytest.raises(ValueError,match='live process RSS unavailable'):
        m.sample_worker_resources([owned_poll_sequence(None,0)],0,[])
