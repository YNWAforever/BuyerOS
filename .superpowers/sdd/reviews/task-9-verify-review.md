# task-9-verify review package
## commits
```
ac4abb6 fix(worker): reuse engine, retry on retry state, ack unknown handlers
24c615b feat(worker): celery task entrypoint with commit-before-ack
```
## stat (lockfiles excluded)
```
 services/worker/buyeros_worker/tasks.py | 70 +++++++++++++++++++++++++++++++++
 services/worker/tests/test_tasks.py     | 43 ++++++++++++++++++++
 2 files changed, 113 insertions(+)
```
## diff (lockfiles excluded)
```diff
diff --git a/services/worker/buyeros_worker/tasks.py b/services/worker/buyeros_worker/tasks.py
new file mode 100644
index 0000000..671d4be
--- /dev/null
+++ b/services/worker/buyeros_worker/tasks.py
@@ -0,0 +1,70 @@
+import asyncio
+from threading import Lock
+
+from . import handlers  # noqa: F401  (import registers handlers)
+from .app import celery_app
+from .registry import get_handler
+
+_engine_lock = Lock()
+_engine = None
+
+
+def get_engine():
+    """One process-wide async engine; disposing happens at worker shutdown."""
+    global _engine
+    if _engine is None:
+        with _engine_lock:
+            if _engine is None:
+                from sqlalchemy.ext.asyncio import create_async_engine
+
+                from buyeros_api.settings import get_settings
+
+                _engine = create_async_engine(get_settings().database_url)
+    return _engine
+
+
+def dispose_engine() -> None:
+    global _engine
+    _engine = None
+
+
+async def run_intent(handler, payload, session, context) -> str:
+    """Execute one handler inside the tenant session and commit before ack.
+
+    The caller passes a session already scoped with the transaction-local
+    tenant context; nothing is committed if the handler raises.
+    """
+    result = handler(session, context, payload)
+    if asyncio.iscoroutine(result):
+        result = await result
+    await session.commit()
+    return result.state
+
+
+def resolve_handler_state(event_type: str) -> str:
+    from .registry import UnknownHandler, get_handler
+
+    try:
+        get_handler(event_type)
+    except UnknownHandler:
+        return "unknown_handler"
+    return "known"
+
+
+@celery_app.task(name="buyeros.execute_intent", acks_late=True, bind=True)
+def execute_intent(self, intent_key: str, event_type: str, payload: dict, generation: int) -> str:
+    if resolve_handler_state(event_type) == "unknown_handler":
+        return "unknown_handler"
+    handler = get_handler(event_type)
+
+    async def _run() -> str:
+        from buyeros_api.db.session import tenant_session
+
+        engine = get_engine()
+        async with tenant_session(engine, payload["workspace_id"]) as session:
+            return await run_intent(handler, payload, session, context={"workspace_id": payload["workspace_id"]})
+
+    result_state = asyncio.run(_run())
+    if result_state == "retry":
+        raise self.retry(countdown=30, max_retries=3)
+    return result_state
diff --git a/services/worker/tests/test_tasks.py b/services/worker/tests/test_tasks.py
new file mode 100644
index 0000000..1faff11
--- /dev/null
+++ b/services/worker/tests/test_tasks.py
@@ -0,0 +1,43 @@
+from buyeros_worker.registry import HandlerResult
+from buyeros_worker.tasks import run_intent
+
+
+class FakeSession:
+    def __init__(self):
+        self.committed = False
+
+    async def __aenter__(self):
+        return self
+
+    async def __aexit__(self, *exc):
+        return False
+
+    async def commit(self):
+        self.committed = True
+
+
+def test_run_intent_returns_handler_state():
+    session = FakeSession()
+
+    async def handler(s, context, payload):
+        return HandlerResult(state="done", detail="ok")
+
+    state = __import__("asyncio").run(run_intent(handler, {}, session, context={"workspace_id": "w"}))
+    assert state == "done"
+    assert session.committed is True
+
+
+def test_run_intent_reports_blocked_without_raising():
+    session = FakeSession()
+
+    async def handler(s, context, payload):
+        return HandlerResult(state="blocked", detail="no provider")
+
+    state = __import__("asyncio").run(run_intent(handler, {}, session, context={"workspace_id": "w"}))
+    assert state == "blocked"
+
+
+def test_unknown_handler_state_is_terminal():
+    from buyeros_worker.tasks import resolve_handler_state
+
+    assert resolve_handler_state("does.not.exist") == "unknown_handler"

```
## lockfile stat (contents omitted)
```
```
