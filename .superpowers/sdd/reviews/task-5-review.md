# task-5 review package
## commits
```
c1c6821 feat(worker): fail-closed handlers for unverified provider job types
```
## stat (lockfiles excluded)
```
 services/worker/buyeros_worker/handlers/__init__.py        |  1 +
 .../worker/buyeros_worker/handlers/capability_blocked.py   | 13 +++++++++++++
 services/worker/tests/test_capability_blocked.py           | 14 ++++++++++++++
 3 files changed, 28 insertions(+)
```
## diff (lockfiles excluded)
```diff
diff --git a/services/worker/buyeros_worker/handlers/__init__.py b/services/worker/buyeros_worker/handlers/__init__.py
new file mode 100644
index 0000000..ab9c357
--- /dev/null
+++ b/services/worker/buyeros_worker/handlers/__init__.py
@@ -0,0 +1 @@
+"""Worker handlers."""
diff --git a/services/worker/buyeros_worker/handlers/capability_blocked.py b/services/worker/buyeros_worker/handlers/capability_blocked.py
new file mode 100644
index 0000000..6433b29
--- /dev/null
+++ b/services/worker/buyeros_worker/handlers/capability_blocked.py
@@ -0,0 +1,13 @@
+from ..registry import HandlerResult, register
+
+BLOCKED_EVENTS = frozenset({"run.discover", "contact.submit", "draft.generate"})
+
+
+def blocked(session, context, payload) -> HandlerResult:
+    """Fail closed: no verified provider/model, so make no external call."""
+    event_type = (payload or {}).get("event_type", "unknown")
+    return HandlerResult(state="blocked", detail=f"{event_type}: no verified provider or model is configured")
+
+
+for _event in BLOCKED_EVENTS:
+    register(_event)(blocked)
diff --git a/services/worker/tests/test_capability_blocked.py b/services/worker/tests/test_capability_blocked.py
new file mode 100644
index 0000000..9f6635e
--- /dev/null
+++ b/services/worker/tests/test_capability_blocked.py
@@ -0,0 +1,14 @@
+# services/worker/tests/test_capability_blocked.py
+from buyeros_worker.handlers.capability_blocked import BLOCKED_EVENTS, blocked
+from buyeros_worker.registry import get_handler
+
+
+def test_blocked_handlers_are_registered():
+    for event in BLOCKED_EVENTS:
+        assert get_handler(event) is blocked
+
+
+def test_blocked_result_makes_no_external_call():
+    result = blocked(session=None, context=None, payload={})
+    assert result.state == "blocked"
+    assert "no verified provider" in result.detail.lower()

```
## lockfile stat (contents omitted)
```
```
