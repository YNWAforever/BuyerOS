"""Linux-native owned parent/grandchild timeout regression; no network or DB."""
import importlib.util
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time


def check_owned_timeout():
    spec = importlib.util.spec_from_file_location('mixed_cleanup', Path(__file__).with_name('mixed_workload_cleanup.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    run = getattr(module, 'run_owned_child', subprocess.run)
    with tempfile.TemporaryDirectory(prefix='buyeros-owned-timeout-') as name:
        folder = Path(name)
        pidfile = folder / 'grandchild.pid'
        parent = (
            "import subprocess,signal,sys,time,pathlib; signal.signal(signal.SIGINT,signal.SIG_IGN); "
            "p=subprocess.Popen([sys.executable,'-c',\"import signal,time; signal.signal(signal.SIGINT,signal.SIG_IGN); time.sleep(20)\"]); "
            "pathlib.Path(sys.argv[1]).write_text(str(p.pid)); time.sleep(20)"
        )
        try:
            try:
                run([sys.executable, '-c', parent, str(pidfile)], timeout=1.5, **({'grace': .3} if hasattr(module, 'run_owned_child') else {}))
            except subprocess.TimeoutExpired:
                pass
            else:
                raise AssertionError('owned parent must time out')
            pid = int(pidfile.read_text())
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                stat = Path(f'/proc/{pid}/stat')
                if not stat.exists() or stat.read_text().split()[2] == 'Z':
                    break
                time.sleep(.02)
            else:
                raise AssertionError('owned grandchild still executing after parent timeout')
        finally:
            if pidfile.exists():
                try: os.kill(int(pidfile.read_text()), signal.SIGKILL)
                except ProcessLookupError: pass
        receipt = folder / 'teardown.txt'
        cooperative = "import pathlib,sys,time\ntry: time.sleep(20)\nfinally: pathlib.Path(sys.argv[1]).write_text('owned-finally-ran')"
        try:
            run([sys.executable, '-c', cooperative, str(receipt)], timeout=1.5, **({'grace': 2} if hasattr(module, 'run_owned_child') else {}))
        except subprocess.TimeoutExpired:
            pass
        else:
            raise AssertionError('cooperative owned child must time out')
        assert receipt.read_text() == 'owned-finally-ran', 'cooperative teardown skipped'


if __name__ == '__main__':
    check_owned_timeout()
    print('owned stubborn grandchild stopped and cooperative teardown ran')
