"""Evidence failures cannot leave owned children alive or skip later teardown."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


def capture_cleanup(folder,capture,actions):
    path=Path(__file__).with_name('mixed_workload_cleanup.py')
    if path.exists():
        spec=importlib.util.spec_from_file_location('mixed_cleanup',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        return module.capture_then_cleanup(folder,capture,actions)
    # Existing mixed-case finally order, kept only until the fix exists.
    with (folder/'capture.json').open('x',encoding='utf-8') as file:json.dump(capture,file)
    for action in actions:action()


@pytest.mark.parametrize('failure',['write','serialize','first_teardown'])
def test_capture_and_teardown_failures_still_terminate_every_owned_child(tmp_path,failure):
    children=[subprocess.Popen([sys.executable,'-c','import time; time.sleep(20)']) for _ in range(2)]
    def stop(child):
        if child.poll() is None:child.terminate();child.wait(timeout=5)
    def fault():raise RuntimeError('first owned teardown failed')
    capture={'invalid':object()} if failure=='serialize' else {'complete':False}
    if failure=='write':(tmp_path/'capture.json').mkdir()
    actions=[lambda p=p:stop(p) for p in children]
    if failure=='first_teardown':actions.insert(0,fault)
    try:
        with pytest.raises((OSError,TypeError,RuntimeError)):capture_cleanup(tmp_path,capture,actions)
        assert all(p.poll() is not None for p in children), 'owned child leaked after capture/teardown error'
    finally:
        for p in children:stop(p)
