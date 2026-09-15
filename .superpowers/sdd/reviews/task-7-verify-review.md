# task-7-verify review package
## commits
```
77df73c fix(worker): make failed/partial/paused_budget runs retryable
bfd2c81 feat(worker): run lifecycle transition table
```
## stat (lockfiles excluded)
```
 services/worker/buyeros_worker/run_lifecycle.py | 27 +++++++++++++
 services/worker/tests/test_run_lifecycle.py     | 50 +++++++++++++++++++++++++
 2 files changed, 77 insertions(+)
```
## diff (lockfiles excluded)
```diff
diff --git a/services/worker/buyeros_worker/run_lifecycle.py b/services/worker/buyeros_worker/run_lifecycle.py
new file mode 100644
index 0000000..642b818
--- /dev/null
+++ b/services/worker/buyeros_worker/run_lifecycle.py
@@ -0,0 +1,27 @@
+RUN_STATES = ("draft", "queued", "running", "partial", "paused_budget", "completed", "failed", "cancel_requested", "cancelled")
+TERMINAL = {"completed", "cancelled"}
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
+    ("paused_budget", "retry"): "queued",
+    ("paused_budget", "resume"): "running",
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
index 0000000..50b0210
--- /dev/null
+++ b/services/worker/tests/test_run_lifecycle.py
@@ -0,0 +1,50 @@
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
+    assert transition_run("cancelled", "start") == "cancelled"
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
+
+
+def test_failed_and_paused_budget_are_retryable():
+    assert transition_run("failed", "retry") == "queued"
+    assert transition_run("partial", "retry") == "queued"
+    assert transition_run("paused_budget", "retry") == "queued"
+    assert transition_run("paused_budget", "resume") == "running"
+
+
+def test_only_completed_and_cancelled_are_terminal():
+    assert terminal("completed") is True
+    assert terminal("cancelled") is True
+    assert terminal("failed") is False
+    assert terminal("partial") is False
+    assert terminal("paused_budget") is False
+
+
+def test_terminal_states_never_regress_even_on_retry():
+    assert transition_run("completed", "retry") == "completed"
+    assert transition_run("cancelled", "retry") == "cancelled"
+
+
+def test_remaining_edges():
+    assert transition_run("draft", "enqueue") == "queued"
+    assert transition_run("running", "fail") == "failed"
+    assert transition_run("running", "partial") == "partial"
+    assert transition_run("running", "pause_budget") == "paused_budget"
+    assert transition_run("cancel_requested", "cancel") == "cancelled"

```
## lockfile stat (contents omitted)
```
```
