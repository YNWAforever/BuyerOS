# task-6-rereview review package
## commits
```
ca3a23d fix(worker): make fetch.evidence payload handling fail closed
ba2d48d fix(worker): fail closed on malformed fetch URLs
cf1f57b feat(worker): SSRF-safe fetch.evidence validation handler
```
## stat (lockfiles excluded)
```
 .../worker/buyeros_worker/handlers/__init__.py     |  3 +-
 .../buyeros_worker/handlers/fetch_evidence.py      | 58 ++++++++++++++++++++
 services/worker/tests/test_fetch_evidence.py       | 62 ++++++++++++++++++++++
 3 files changed, 122 insertions(+), 1 deletion(-)
```
## diff (lockfiles excluded)
```diff
diff --git a/services/worker/buyeros_worker/handlers/__init__.py b/services/worker/buyeros_worker/handlers/__init__.py
index ab9c357..f7b26e4 100644
--- a/services/worker/buyeros_worker/handlers/__init__.py
+++ b/services/worker/buyeros_worker/handlers/__init__.py
@@ -1 +1,2 @@
-"""Worker handlers."""
+"""Worker handlers. Importing this package registers its handlers."""
+from . import capability_blocked, fetch_evidence  # noqa: F401
diff --git a/services/worker/buyeros_worker/handlers/fetch_evidence.py b/services/worker/buyeros_worker/handlers/fetch_evidence.py
new file mode 100644
index 0000000..25832d7
--- /dev/null
+++ b/services/worker/buyeros_worker/handlers/fetch_evidence.py
@@ -0,0 +1,58 @@
+from urllib.parse import urlsplit
+
+from buyeros_api.services.safe_fetch import is_blocked_host, normalize_url
+
+from ..registry import HandlerResult, register
+
+MAX_DECODED_BYTES = 2 * 1024 * 1024
+ALLOWED_CONTENT_TYPES = frozenset({"text/html", "text/plain", "text/markdown", "application/xhtml+xml"})
+
+
+class FetchRejected(Exception):
+    pass
+
+
+def _reject_if_blocked_host(host: str) -> None:
+    try:
+        blocked = is_blocked_host(host)
+    except ValueError:
+        return  # hostname; DNS/IP pinning happens at connection time
+    if blocked:
+        raise FetchRejected(f"blocked host {host}")
+
+
+def validate_fetch(url: str, content_type: str, size: int) -> None:
+    try:
+        normalized = normalize_url(url)
+    except ValueError:
+        raise FetchRejected(f"malformed url: {url}") from None
+    parsed = urlsplit(normalized)
+    if parsed.scheme not in {"http", "https"}:
+        raise FetchRejected(f"unsupported scheme {parsed.scheme}")
+    _reject_if_blocked_host(parsed.hostname or "")
+    if size < 0 or size > MAX_DECODED_BYTES:
+        raise FetchRejected("decoded body size out of range")
+    media_type = (content_type or "").split(";")[0].strip().lower()
+    if media_type not in ALLOWED_CONTENT_TYPES:
+        raise FetchRejected(f"content type {media_type} not allowed")
+
+
+@register("fetch.evidence")
+def handle(session, context, payload) -> HandlerResult:
+    """Validate and (in the fetch client) retrieve permitted evidence.
+
+    The live HTTP client is intentionally not wired here: it must run with
+    DNS/IP pinning against the deployed egress policy. Validation is enforced
+    now so an unsafe URL can never be dispatched.
+    """
+    if not isinstance(payload, dict):
+        return HandlerResult(state="blocked", detail="fetch.evidence: invalid payload")
+    try:
+        size = int(payload.get("size", 0))
+    except (TypeError, ValueError):
+        return HandlerResult(state="blocked", detail="fetch.evidence: invalid size")
+    try:
+        validate_fetch(payload.get("url", ""), payload.get("content_type", ""), size)
+    except FetchRejected as exc:
+        return HandlerResult(state="blocked", detail=str(exc))
+    return HandlerResult(state="done", detail="validated; retrieval client is not enabled in this phase")
diff --git a/services/worker/tests/test_fetch_evidence.py b/services/worker/tests/test_fetch_evidence.py
new file mode 100644
index 0000000..148dbf2
--- /dev/null
+++ b/services/worker/tests/test_fetch_evidence.py
@@ -0,0 +1,62 @@
+import pytest
+
+from buyeros_worker.handlers.fetch_evidence import (
+    MAX_DECODED_BYTES,
+    FetchRejected,
+    handle,
+    validate_fetch,
+)
+from buyeros_worker.registry import get_handler
+
+
+def test_blocked_host_is_rejected():
+    with pytest.raises(FetchRejected):
+        validate_fetch("http://127.0.0.1/x", "text/html", 10)
+
+
+def test_private_host_is_rejected():
+    with pytest.raises(FetchRejected):
+        validate_fetch("http://10.0.0.1/x", "text/html", 10)
+
+
+def test_oversized_body_is_rejected():
+    with pytest.raises(FetchRejected):
+        validate_fetch("https://example.com/x", "text/html", MAX_DECODED_BYTES + 1)
+
+
+def test_disallowed_content_type_is_rejected():
+    with pytest.raises(FetchRejected):
+        validate_fetch("https://example.com/x", "application/octet-stream", 10)
+
+
+def test_valid_public_html_passes():
+    validate_fetch("https://example.com/x", "text/html; charset=utf-8", 100)
+
+
+def test_handler_is_registered():
+    assert get_handler("fetch.evidence") is not None
+
+
+def test_malformed_url_is_rejected_not_raised():
+    with pytest.raises(FetchRejected):
+        validate_fetch("https://example.com:notaport/x", "text/html", 10)
+
+
+def test_handler_blocks_malformed_url():
+    result = handle(None, None, {"url": "https://example.com:notaport/x", "content_type": "text/html", "size": 1})
+    assert result.state == "blocked"
+
+
+def test_non_numeric_size_is_blocked_not_raised():
+    result = handle(None, None, {"url": "https://example.com/x", "content_type": "text/html", "size": "abc"})
+    assert result.state == "blocked"
+
+
+def test_none_payload_is_blocked_not_raised():
+    result = handle(None, None, None)
+    assert result.state == "blocked"
+
+
+def test_negative_size_is_rejected():
+    with pytest.raises(FetchRejected):
+        validate_fetch("https://example.com/x", "text/html", -1)

```
## lockfile stat (contents omitted)
```
```
