# task-6-verify review package
## commits
```
5b5d384 fix(worker): block IPv6-literal and empty-host fetch URLs
5d2d0be fix(worker): fail closed on non-string fetch payload fields
ca3a23d fix(worker): make fetch.evidence payload handling fail closed
ba2d48d fix(worker): fail closed on malformed fetch URLs
cf1f57b feat(worker): SSRF-safe fetch.evidence validation handler
```
## stat (lockfiles excluded)
```
 .../worker/buyeros_worker/handlers/__init__.py     |  3 +-
 .../buyeros_worker/handlers/fetch_evidence.py      | 66 +++++++++++++++
 services/worker/tests/test_fetch_evidence.py       | 95 ++++++++++++++++++++++
 3 files changed, 163 insertions(+), 1 deletion(-)
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
index 0000000..82ac135
--- /dev/null
+++ b/services/worker/buyeros_worker/handlers/fetch_evidence.py
@@ -0,0 +1,66 @@
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
+        normalize_url(url)
+    except ValueError:
+        raise FetchRejected(f"malformed url: {url}") from None
+    parts = urlsplit(url)
+    if parts.scheme not in {"http", "https"}:
+        raise FetchRejected(f"unsupported scheme {parts.scheme}")
+    host = parts.hostname
+    if not host:
+        raise FetchRejected("missing host")
+    _reject_if_blocked_host(host)
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
+    url = payload.get("url")
+    content_type = payload.get("content_type")
+    size = payload.get("size", 0)
+    if not isinstance(url, str) or not isinstance(content_type, str):
+        return HandlerResult(state="blocked", detail="fetch.evidence: invalid payload")
+    try:
+        size_value = int(size)
+    except (TypeError, ValueError):
+        return HandlerResult(state="blocked", detail="fetch.evidence: invalid size")
+    try:
+        validate_fetch(url, content_type, size_value)
+    except FetchRejected as exc:
+        return HandlerResult(state="blocked", detail=str(exc))
+    return HandlerResult(state="done", detail="validated; retrieval client is not enabled in this phase")
diff --git a/services/worker/tests/test_fetch_evidence.py b/services/worker/tests/test_fetch_evidence.py
new file mode 100644
index 0000000..d4b7923
--- /dev/null
+++ b/services/worker/tests/test_fetch_evidence.py
@@ -0,0 +1,95 @@
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
+
+
+@pytest.mark.parametrize("bad", [None, 123, [1], {"a": 1}, True])
+def test_non_string_url_is_blocked_not_raised(bad):
+    result = handle(None, None, {"url": bad, "content_type": "text/html", "size": 1})
+    assert result.state == "blocked"
+
+
+@pytest.mark.parametrize("bad", [None, 123, ["text/html"], True])
+def test_non_string_content_type_is_blocked_not_raised(bad):
+    result = handle(None, None, {"url": "https://example.com/x", "content_type": bad, "size": 1})
+    assert result.state == "blocked"
+
+
+@pytest.mark.parametrize(
+    "url",
+    [
+        "http://[::1]/x",
+        "https://[fe80::1]/x",
+        "http://[fc00::1]/x",
+        "http://[::ffff:10.0.0.1]/x",
+        "http:///x",
+    ],
+)
+def test_ipv6_and_empty_host_are_rejected(url):
+    with pytest.raises(FetchRejected):
+        validate_fetch(url, "text/html", 10)
+
+
+@pytest.mark.parametrize("url", ["http://[::1]/x", "http:///x"])
+def test_ipv6_and_empty_host_blocked_via_handle(url):
+    result = handle(None, None, {"url": url, "content_type": "text/html", "size": 1})
+    assert result.state == "blocked"

```
## lockfile stat (contents omitted)
```
```
