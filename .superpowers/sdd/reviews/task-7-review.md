# task-7 review package
## commits
```
bfd2c81 feat(worker): run lifecycle transition table
```
## stat (lockfiles excluded)
```
 services/worker/buyeros_worker/run_lifecycle.py | 25 +++++++++++++++++++++++++
 services/worker/tests/test_run_lifecycle.py     | 22 ++++++++++++++++++++++
 2 files changed, 47 insertions(+)
```
## diff (lockfiles excluded)
```diff
diff --git a/services/worker/buyeros_worker/run_lifecycle.py b/services/worker/buyeros_worker/run_lifecycle.py
new file mode 100644
index 0000000..fa83056
--- /dev/null
+++ b/services/worker/buyeros_worker/run_lifecycle.py
@@ -0,0 +1,25 @@
+RUN_STATES = ("draft", "queued", "running", "partial", "paused_budget", "completed", "failed", "cancel_requested", "cancelled")
+TERMINAL = {"completed", "failed", "cancelled"}
+
+_TRANSITIONS = {
+    ("draft", "enqueue"): "queued",
+    ("queued", "start"): "running",
+    ("running", "complete"): "completed",
+    ("running", "partial"): "partial",
+    ("running", "pause_budget"): "paused_budget",
+    ("running", "fail"): "failed",
+    ("running", "cancel"): "cancel_requested",
+    ("partial", "retry"): "queued",
+    ("failed", "retry"): "queued",
+    ("cancel_requested", "cancel"): "cancelled",
+}
+
+
+def terminal(state: str) -> bool:
+    return state in TERMINAL
+
+
+def transition_run(current: str, event: str) -> str:
+    if terminal(current):
+        return current
+    return _TRANSITIONS.get((current, event), current)
diff --git a/services/worker/tests/test_run_lifecycle.py b/services/worker/tests/test_run_lifecycle.py
new file mode 100644
index 0000000..d6c65f8
--- /dev/null
+++ b/services/worker/tests/test_run_lifecycle.py
@@ -0,0 +1,22 @@
+from buyeros_worker.run_lifecycle import terminal, transition_run
+
+
+def test_valid_progressions():
+    assert transition_run("queued", "start") == "running"
+    assert transition_run("running", "complete") == "completed"
+    assert transition_run("running", "cancel") == "cancel_requested"
+
+
+def test_terminal_states_do_not_regress():
+    assert transition_run("completed", "start") == "completed"
+    assert transition_run("failed", "start") == "failed"
+
+
+def test_cancel_requested_is_not_terminal():
+    assert terminal("cancel_requested") is False
+    assert terminal("cancelled") is True
+    assert terminal("completed") is True
+
+
+def test_unknown_event_is_ignored():
+    assert transition_run("running", "bogus") == "running"

```
## lockfile stat (contents omitted)
```
```
