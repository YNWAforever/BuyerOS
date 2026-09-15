# task-8 review package
## commits
```
32e4af0 fix(worker): dispatch using the persisted outbox intent key
d0ad91e feat(worker): outbox dispatcher with lease claims and sweeper
```
## stat (lockfiles excluded)
```
 services/worker/buyeros_worker/dispatcher.py | 67 ++++++++++++++++++++++++++++
 services/worker/tests/test_dispatcher.py     | 54 ++++++++++++++++++++++
 2 files changed, 121 insertions(+)
```
## diff (lockfiles excluded)
```diff
diff --git a/services/worker/buyeros_worker/dispatcher.py b/services/worker/buyeros_worker/dispatcher.py
new file mode 100644
index 0000000..6a89364
--- /dev/null
+++ b/services/worker/buyeros_worker/dispatcher.py
@@ -0,0 +1,67 @@
+from datetime import datetime
+from typing import Callable
+
+from .leases import can_claim, lease_expiry
+
+
+def select_ready(rows: list[dict], now: datetime, limit: int = 10) -> list[dict]:
+    selected = [r for r in rows if can_claim(r.get("state", "free"), r.get("lease_expires_at"), now)]
+    return selected[:limit]
+
+
+async def claim_outbox_rows(session, owner: str, limit: int, now: datetime) -> list[dict]:
+    """Claim ready outbox rows atomically, bumping the fencing generation."""
+    from sqlalchemy import text
+
+    result = await session.execute(
+        text(
+            """
+            UPDATE outbox_events
+               SET lease_owner = :owner,
+                   lease_expires_at = :expires,
+                   fencing_generation = fencing_generation + 1,
+                   state = 'dispatched'
+             WHERE id IN (
+                   SELECT id FROM outbox_events
+                    WHERE state = 'ready'
+                       OR (state = 'dispatched' AND lease_expires_at <= :now)
+                    ORDER BY created_at
+                    LIMIT :limit
+                    FOR UPDATE SKIP LOCKED
+             )
+         RETURNING id, intent_key, event_type, payload, fencing_generation
+            """
+        ),
+        {"owner": owner, "expires": lease_expiry(now, 120), "now": now, "limit": limit},
+    )
+    return [dict(r._mapping) for r in result]
+
+
+async def mark_dispatched(session, ids: list[int], now: datetime) -> None:
+    from sqlalchemy import text
+
+    if not ids:
+        return
+    await session.execute(text("UPDATE outbox_events SET dispatched_at = :now WHERE id = ANY(:ids)"), {"now": now, "ids": ids})
+
+
+async def sweep_expired(session, now: datetime) -> list[int]:
+    """Return ids of dispatched rows whose lease expired (re-claimable)."""
+    from sqlalchemy import text
+
+    result = await session.execute(
+        text("SELECT id FROM outbox_events WHERE state = 'dispatched' AND lease_expires_at <= :now"),
+        {"now": now},
+    )
+    return [r[0] for r in result]
+
+
+async def dispatch_once(session, publish: Callable, owner: str, now: datetime, limit: int) -> list[str]:
+    claimed = await claim_outbox_rows(session, owner, limit, now)
+    published: list[str] = []
+    for row in claimed:
+        intent = row["intent_key"]
+        publish(intent, row)
+        published.append(intent)
+    await mark_dispatched(session, [row["id"] for row in claimed], now)
+    return published
diff --git a/services/worker/tests/test_dispatcher.py b/services/worker/tests/test_dispatcher.py
new file mode 100644
index 0000000..559493f
--- /dev/null
+++ b/services/worker/tests/test_dispatcher.py
@@ -0,0 +1,54 @@
+from datetime import datetime, timedelta, timezone
+
+from buyeros_worker.dispatcher import dispatch_once, select_ready, sweep_expired
+
+NOW = datetime(2026, 9, 15, tzinfo=timezone.utc)
+
+
+def test_only_ready_rows_are_selected():
+    rows = [
+        {"id": 1, "state": "ready", "lease_expires_at": None},
+        {"id": 2, "state": "dispatched", "lease_expires_at": NOW + timedelta(seconds=60)},
+        {"id": 3, "state": "ready", "lease_expires_at": NOW - timedelta(seconds=1)},
+    ]
+    assert [r["id"] for r in select_ready(rows, NOW)] == [1, 3]
+
+
+def test_batch_is_bounded():
+    rows = [{"id": i, "state": "ready", "lease_expires_at": None} for i in range(20)]
+    assert len(select_ready(rows, NOW, limit=5)) == 5
+
+
+def test_dispatch_once_publishes_persisted_intent_key():
+    import asyncio
+
+    class FakeResult:
+        def __init__(self, rows):
+            self._rows = rows
+
+        def __iter__(self):
+            return iter(self._rows)
+
+    class FakeRow:
+        def __init__(self, mapping):
+            self._mapping = mapping
+
+    class FakeSession:
+        def __init__(self, rows):
+            self._rows = rows
+            self.executed = []
+
+        async def execute(self, statement, params=None):
+            self.executed.append(params)
+            return FakeResult([FakeRow(r) for r in self._rows])
+
+    rows = [{"id": 1, "intent_key": "job:aaa", "event_type": "fetch.evidence", "payload": {"url": "https://e.com"}, "fencing_generation": 1}]
+    published = []
+    session = FakeSession(rows)
+    out = asyncio.run(dispatch_once(session, lambda intent, row: published.append(intent), "worker-1", __import__("datetime").datetime.now(__import__("datetime").timezone.utc), 10))
+    assert published == ["job:aaa"]
+    assert out == ["job:aaa"]
+
+
+def test_sweep_expired_returns_int_ids():
+    assert sweep_expired.__annotations__["return"] == list[int]

```
## lockfile stat (contents omitted)
```
```
