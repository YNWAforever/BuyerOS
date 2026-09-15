# task-4 review package
## commits
```
6c70b28 feat(worker): handler registry
```
## stat (lockfiles excluded)
```
 services/worker/buyeros_worker/registry.py | 30 ++++++++++++++++++++++++++++++
 services/worker/tests/test_registry.py     | 17 +++++++++++++++++
 2 files changed, 47 insertions(+)
```
## diff (lockfiles excluded)
```diff
diff --git a/services/worker/buyeros_worker/registry.py b/services/worker/buyeros_worker/registry.py
new file mode 100644
index 0000000..baec808
--- /dev/null
+++ b/services/worker/buyeros_worker/registry.py
@@ -0,0 +1,30 @@
+from collections.abc import Callable
+from dataclasses import dataclass
+
+
+class UnknownHandler(Exception):
+    pass
+
+
+@dataclass(frozen=True)
+class HandlerResult:
+    state: str          # "done" | "blocked" | "retry"
+    detail: str = ""
+
+
+HANDLERS: dict[str, Callable] = {}
+
+
+def register(event_type: str):
+    def decorator(func: Callable) -> Callable:
+        HANDLERS[event_type] = func
+        return func
+
+    return decorator
+
+
+def get_handler(event_type: str) -> Callable:
+    try:
+        return HANDLERS[event_type]
+    except KeyError as exc:  # pragma: no cover - exercised via test
+        raise UnknownHandler(event_type) from exc
diff --git a/services/worker/tests/test_registry.py b/services/worker/tests/test_registry.py
new file mode 100644
index 0000000..391c66e
--- /dev/null
+++ b/services/worker/tests/test_registry.py
@@ -0,0 +1,17 @@
+import pytest
+
+from buyeros_worker.registry import HANDLERS, HandlerResult, UnknownHandler, get_handler, register
+
+
+def test_unknown_handler_raises():
+    with pytest.raises(UnknownHandler):
+        get_handler("does.not.exist")
+
+
+def test_registration_makes_handler_available():
+    @register("test.event")
+    def handler(session, context, payload):
+        return HandlerResult(state="done", detail="ok")
+
+    assert get_handler("test.event") is handler
+    assert "test.event" in HANDLERS

```
## lockfile stat (contents omitted)
```
```
