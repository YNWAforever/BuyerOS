"""Always attempt every teardown for resources created by the owned capture."""
import json
import os
import signal
import subprocess
import sys


def cleanup_all(actions):
    failures = []
    for action in actions:
        try:
            action()
        except BaseException as exc:
            failures.append(exc)
    if failures:
        raise failures[0]


def capture_then_cleanup(folder, capture, actions):
    try:
        with (folder / 'capture.json').open('x', encoding='utf-8') as file:
            json.dump(capture, file, indent=2, allow_nan=False)
            file.write('\n')
    finally:
        cleanup_all(actions)


def run_owned_child(command, *, timeout, grace=60, **kwargs):
    """Linux session owned by this Popen; cooperate, then bound group cleanup."""
    if sys.platform != 'linux':
        raise RuntimeError('owned timeout requires native Linux process groups')
    child = subprocess.Popen(command, start_new_session=True, **kwargs)

    def signal_group(sig):
        try: os.killpg(child.pid, sig)
        except ProcessLookupError: pass

    try:
        try:
            return subprocess.CompletedProcess(command, child.wait(timeout=timeout))
        except BaseException:
            signal_group(signal.SIGINT)
            try: child.wait(timeout=grace)
            except subprocess.TimeoutExpired: pass
            raise
    finally:
        # Covers stubborn descendants even when their parent exits cooperatively.
        signal_group(signal.SIGKILL)
        child.wait(timeout=10)
