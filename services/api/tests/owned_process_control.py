"""Real signal-handler child used to verify the owned process crash boundary."""
import multiprocessing
import os
import signal
import time

from tests.owned_api_process import OwnedAPIProcess


def ignore_termination(control):
    signal.signal(signal.SIGTERM, lambda *_: None)
    control.send({'pid': os.getpid(), 'sigterm_handler': True})
    control.recv()  # intentionally blocked until hard process death


def hard_stop_signal_handler_child():
    ctx = multiprocessing.get_context('spawn')
    parent, child = ctx.Pipe()
    process = ctx.Process(target=ignore_termination, args=(child,))
    process.start()
    child.close()
    owned = OwnedAPIProcess({})
    owned.process, owned.control = process, parent
    try:
        assert parent.poll(10), 'owned signal-handler child did not start'
        before = parent.recv()
        assert before['pid'] == process.pid and process.is_alive()
        started = time.monotonic()
        owned.stop(hard=True)
        elapsed = time.monotonic() - started
        assert owned.exit['pid'] == before['pid']
        assert owned.exit['hard'] is True and owned.exit['alive'] is False
        assert process.exitcode is not None
        if os.name == 'posix':
            assert process.exitcode == -signal.SIGKILL
        return dict(before=before, exit=owned.exit, stop_seconds=elapsed,
                    platform=os.name, live_acceptance=False)
    finally:
        # Exact Process reference created here only, including failed RED cleanup.
        if process.is_alive():
            process.kill()
            process.join(timeout=5)
        assert not process.is_alive()
        parent.close()
