# task-3 review package
## commits
```
ce5f850 feat(worker): lease expiry and fencing primitives
```
## stat (lockfiles excluded)
```
 services/worker/buyeros_worker/leases.py | 15 +++++++++++++++
 services/worker/tests/test_leases.py     | 26 ++++++++++++++++++++++++++
 2 files changed, 41 insertions(+)
```
## diff (lockfiles excluded)
```diff
diff --git a/services/worker/buyeros_worker/leases.py b/services/worker/buyeros_worker/leases.py
new file mode 100644
index 0000000..256ec9a
--- /dev/null
+++ b/services/worker/buyeros_worker/leases.py
@@ -0,0 +1,15 @@
+from datetime import datetime, timedelta
+
+
+def lease_expiry(now: datetime, seconds: int) -> datetime:
+    return now + timedelta(seconds=seconds)
+
+
+def can_claim(state: str, expires_at: datetime | None, now: datetime) -> bool:
+    if state == "free" or expires_at is None:
+        return True
+    return expires_at <= now
+
+
+def fence_ok(worker_generation: int, row_generation: int) -> bool:
+    return worker_generation == row_generation
diff --git a/services/worker/tests/test_leases.py b/services/worker/tests/test_leases.py
new file mode 100644
index 0000000..b3741bb
--- /dev/null
+++ b/services/worker/tests/test_leases.py
@@ -0,0 +1,26 @@
+from datetime import datetime, timedelta, timezone
+
+from buyeros_worker.leases import can_claim, fence_ok, lease_expiry
+
+NOW = datetime(2026, 9, 15, tzinfo=timezone.utc)
+
+
+def test_free_lease_can_be_claimed():
+    assert can_claim("free", None, NOW) is True
+
+
+def test_unexpired_lease_cannot_be_claimed():
+    assert can_claim("held", NOW + timedelta(seconds=30), NOW) is False
+
+
+def test_expired_lease_can_be_claimed():
+    assert can_claim("held", NOW - timedelta(seconds=1), NOW) is True
+
+
+def test_lease_expiry_adds_seconds():
+    assert lease_expiry(NOW, 120) == NOW + timedelta(seconds=120)
+
+
+def test_fence_rejects_stale_worker():
+    assert fence_ok(3, 3) is True
+    assert fence_ok(2, 3) is False

```
## lockfile stat (contents omitted)
```
```
