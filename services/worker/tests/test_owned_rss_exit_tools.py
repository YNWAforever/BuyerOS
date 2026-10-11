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


def linux_read(tmp_path,status):
    file=tmp_path/'status';file.write_text(status,encoding='utf-8')
    function=reader()._process_rss
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
