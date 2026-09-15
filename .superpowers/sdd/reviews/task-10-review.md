# task-10 review package
## commits
```
600e755 test(worker): disposable valkey broker integration check
```
## stat (lockfiles excluded)
```
 services/worker/tests/test_valkey_integration.py | 45 ++++++++++++++++++++++++
 1 file changed, 45 insertions(+)
```
## diff (lockfiles excluded)
```diff
diff --git a/services/worker/tests/test_valkey_integration.py b/services/worker/tests/test_valkey_integration.py
new file mode 100644
index 0000000..fd797ff
--- /dev/null
+++ b/services/worker/tests/test_valkey_integration.py
@@ -0,0 +1,45 @@
+import shutil
+import subprocess
+import time
+import uuid
+from datetime import datetime, timezone
+
+import pytest
+
+from buyeros_worker.app import celery_app
+from buyeros_worker.dispatcher import select_ready
+
+
+def _valkey_container():
+    if shutil.which("docker") is None:
+        pytest.skip("docker unavailable")
+    name = f"buyeros-valkey-{uuid.uuid4().hex[:8]}"
+    run = subprocess.run(
+        ["docker", "run", "-d", "--name", name, "-p", "127.0.0.1::6379", "valkey/valkey:8"],
+        capture_output=True,
+        text=True,
+    )
+    if run.returncode != 0:
+        pytest.skip(f"could not start valkey: {run.stderr.strip()}")
+    return name
+
+
+def test_broker_is_reachable_and_dispatcher_selection_is_pure():
+    name = _valkey_container()
+    try:
+        time.sleep(3)
+        port_output = subprocess.run(["docker", "port", name, "6379"], capture_output=True, text=True).stdout.strip()
+        if not port_output:
+            pytest.skip(f"could not resolve valkey port for {name}")
+        port = port_output.splitlines()[0].rsplit(":", 1)[1]
+        celery_app.conf.broker_url = f"redis://127.0.0.1:{port}/0"
+        with celery_app.connection() as conn:
+            conn.ensure_connection(max_retries=3)
+        assert celery_app.conf.broker_url.endswith("/0")
+        selected = select_ready(
+            [{"id": 1, "state": "ready", "lease_expires_at": None}],
+            datetime.now(timezone.utc),
+        )
+        assert selected[0]["id"] == 1
+    finally:
+        subprocess.run(["docker", "rm", "-f", name], capture_output=True, text=True)

```
## lockfile stat (contents omitted)
```
```
