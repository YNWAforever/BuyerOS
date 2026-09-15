# task-9 review package
## commits
```
24c615b feat(worker): celery task entrypoint with commit-before-ack
```
## stat (lockfiles excluded)
```
 services/worker/buyeros_worker/tasks.py | 40 +++++++++++++++++++++++++++++++++
 services/worker/tests/test_tasks.py     | 39 ++++++++++++++++++++++++++++++++
 2 files changed, 79 insertions(+)
```
## diff (lockfiles excluded)
```diff
diff --git a/services/worker/buyeros_worker/tasks.py b/services/worker/buyeros_worker/tasks.py
new file mode 100644
index 0000000..9e8e35a
--- /dev/null
+++ b/services/worker/buyeros_worker/tasks.py
@@ -0,0 +1,40 @@
+import asyncio
+
+from . import handlers  # noqa: F401  (import registers handlers)
+from .app import celery_app
+from .registry import get_handler
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
+@celery_app.task(name="buyeros.execute_intent", acks_late=True)
+def execute_intent(intent_key: str, event_type: str, payload: dict, generation: int) -> str:
+    handler = get_handler(event_type)
+
+    async def _run() -> str:
+        from buyeros_api.db.session import tenant_session
+
+        engine = _engine()
+        async with tenant_session(engine, payload["workspace_id"]) as session:
+            return await run_intent(handler, payload, session, context={"workspace_id": payload["workspace_id"]})
+
+    return asyncio.run(_run())
+
+
+def _engine():
+    from sqlalchemy.ext.asyncio import create_async_engine
+
+    from buyeros_api.settings import get_settings
+
+    return create_async_engine(get_settings().database_url)
diff --git a/services/worker/tests/test_tasks.py b/services/worker/tests/test_tasks.py
new file mode 100644
index 0000000..d2f50a0
--- /dev/null
+++ b/services/worker/tests/test_tasks.py
@@ -0,0 +1,39 @@
+import pytest
+
+from buyeros_worker.registry import HandlerResult, UnknownHandler
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

```
## lockfile stat (contents omitted)
```
```
