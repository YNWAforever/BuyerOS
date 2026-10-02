"""Linux standby process and SIGTERM integration; no credentials or services used."""

import os
from pathlib import Path
import selectors
import subprocess
import sys


if sys.platform != "linux":
    raise SystemExit("This process integration check requires Linux; it was not run")
launcher = Path(__file__).resolve().parents[1] / "scripts/run-render-worker.py"
environment = {key: value for key, value in os.environ.items() if not key.startswith("BUYEROS_")}
passed = 0
for role in ("worker", "dispatcher"):
    process = subprocess.Popen([sys.executable, str(launcher), role], env=environment,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            assert selector.select(timeout=10), "Standby startup did not report within 10 seconds"
        message = process.stdout.readline()
        assert message.strip() == f"BuyerOS {role}: standby; no jobs or connections started"
        assert process.poll() is None, "Standby process exited early"
        process.terminate()
        _, errors = process.communicate(timeout=10)
        assert process.returncode == 0, "Standby SIGTERM was not graceful"
        assert not errors, "Standby process emitted errors"
        passed += 1
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=10)
print(f"Linux standby integration: {passed} passed, 0 failed/skipped; no database/broker/provider")
