# Task 6 Report: SSRF-safe `fetch.evidence` handler

**Status:** DONE

**Commit:** `cf1f57bc5936f22addf04173766b76fa52b51ef0` (local, branch `p8-worker-dispatcher`)
`feat(worker): SSRF-safe fetch.evidence validation handler`

## Files
- Create: `services/worker/buyeros_worker/handlers/fetch_evidence.py`
- Create: `services/worker/tests/test_fetch_evidence.py`
- Modify: `services/worker/buyeros_worker/handlers/__init__.py` (required extra change to resolve review finding)

## TDD sequence
1. Wrote `tests/test_fetch_evidence.py` verbatim from the brief (6 tests: blocked host, private host, oversized body, disallowed content type, valid public HTML, handler registered).
2. Ran `uv run pytest tests/test_fetch_evidence.py -v` → FAIL, `ModuleNotFoundError: No module named 'buyeros_worker.handlers.fetch_evidence'`.
3. Wrote `fetch_evidence.py` with the brief's constants, `FetchRejected`, `_reject_if_blocked_host`, `validate_fetch`, and the `@register("fetch.evidence")` `handle` function. Updated `handlers/__init__.py` to import its submodules so package import registers handlers.
4. Ran `uv run pytest tests/test_fetch_evidence.py -v` → **6 passed**, 1 warning.

## Extra required change
`services/worker/buyeros_worker/handlers/__init__.py` now reads:
```python
"""Worker handlers. Importing this package registers its handlers."""
from . import capability_blocked, fetch_evidence  # noqa: F401
```
This resolves the review finding that importing the `handlers` package did not register submodules. Minimal one-line import change.

## Deviation from brief (deliberate)
The brief's literal implementation inlined the block decision via `ip_address` inside `_reject_if_blocked_host`. Per the task instruction to reuse `buyeros_api.services.safe_fetch.is_blocked_host`, the helper now calls `is_blocked_host(host)` and returns on `ValueError` (hostname) as before. Semantics are identical; behavior verified by the same tests. `normalize_url` is imported and used unchanged.

## Verification
- `uv run pytest tests/test_fetch_evidence.py -v` → **6 passed**, 1 warning.
- Full worker suite `uv run pytest -q` → **18 passed**, 1 warning (pre-existing pytest-asyncio deprecation).

## Constraints honored
- Only the three allowed files touched (`fetch_evidence.py`, `handlers/__init__.py`, `test_fetch_evidence.py`).
- Handler performs **no network request**: `handle` validates only and returns `HandlerResult(state="done", detail="validated; retrieval client is not enabled in this phase")` or `state="blocked"` on `FetchRejected`.
- No change to `services/api` or any other worker file/test.
- Local commit only; no push/merge/rebase.

## Concerns
- Known Task 4 Minor persists: registering into module-global `HANDLERS` leaks between test modules. Now partially mitigated: importing `buyeros_worker.handlers` registers all handlers deterministically.
- `validate_fetch` only blocks literal IP-literal hosts (`is_blocked_host` is applied to a parsed IP). Hostnames are accepted and rely on connection-time DNS/IP pinning, as documented in the handler docstring. This is intended for this phase (no live client).
- `normalize_url` raises `ValueError` (not `FetchRejected`) for a URL with a malformed port (e.g. `http://host:abc/x`), which would escape `handle`'s `except FetchRejected`; the task's tests do not cover that path and the dispatcher payload contract is expected to supply well-formed URLs.

---

## Follow-up fix: fail closed on malformed fetch URLs

**Status:** DONE

**Commit:** `ba2d48d9de8cd54b6fcbb7df7cea5d8abfdb94b7` (local, branch `p8-worker-dispatcher`)
`fix(worker): fail closed on malformed fetch URLs`

### Change
- `validate_fetch`: wrapped `normalize_url(url)` in `try/except ValueError` and re-raised as `FetchRejected(f"malformed url: {url}")`. Existing checks/behaviour for valid URLs unchanged. This closes the previously documented concern where a malformed port escaped `handle`'s `except FetchRejected`.
- `handle`: unchanged �X still catches only `FetchRejected` and returns `HandlerResult(state="blocked", detail=str(exc))`. No broadening to arbitrary exceptions.
- Tests added: `test_malformed_url_is_rejected_not_raised` and `test_handler_blocks_malformed_url` (asserts `state == "blocked"` and no raise).

### Files touched
- `services/worker/buyeros_worker/handlers/fetch_evidence.py`
- `services/worker/tests/test_fetch_evidence.py`

### Commands & output
- `uv run pytest -q` (from `services/worker`) �� `20 passed, 1 warning in 0.25s` (pre-existing pytest-asyncio `get_event_loop_policy` deprecation).
- `git commit -m "fix(worker): fail closed on malformed fetch URLs"` �� `[p8-worker-dispatcher ba2d48d] 2 files changed, 15 insertions(+), 1 deletion(-)`.

 ### Concerns
 - None new. The Task 4 module-global `HANDLERS` leakage note still stands. Only the two allowed files were staged/committed (repo had unrelated dirty files left untouched).

---

## Follow-up fix: make fetch.evidence payload handling fail closed

**Status:** DONE

**Commit:** `ca3a23dfb22973f114a99d5553a1301d5d040374` (local, branch `p8-worker-dispatcher`)
`fix(worker): make fetch.evidence payload handling fail closed`

### Change
- `handle`: added `if not isinstance(payload, dict): return HandlerResult(state="blocked", detail="fetch.evidence: invalid payload")`.
- `handle`: coerce size in `try/except (TypeError, ValueError)` -> `HandlerResult(state="blocked", detail="fetch.evidence: invalid size")`; `url`/`content_type` read via `.get(..., "")`.
- `handle`: still catches only `FetchRejected` (returns `blocked` with `str(exc)`); no blanket `Exception` caught.
- `validate_fetch`: size check now `if size < 0 or size > MAX_DECODED_BYTES:` raising `FetchRejected("decoded body size out of range")`.
- Tests added: `test_non_numeric_size_is_blocked_not_raised`, `test_none_payload_is_blocked_not_raised`, `test_negative_size_is_rejected`.

### Files touched
- `services/worker/buyeros_worker/handlers/fetch_evidence.py`
- `services/worker/tests/test_fetch_evidence.py`

### Commands & output
- `uv run pytest -q` (from `services/worker`) -> `23 passed, 1 warning in 0.28s` (pre-existing pytest-asyncio `get_event_loop_policy` deprecation).
- `git commit -m "fix(worker): make fetch.evidence payload handling fail closed"` -> `[p8-worker-dispatcher ca3a23d] 2 files changed, 24 insertions(+), 3 deletions(-)`.

### Concerns
- None new. Only the two allowed files were staged/committed (repo had unrelated dirty/untracked files left untouched).

---

## Follow-up fix: fail closed on non-string fetch payload fields

**Status:** DONE

**Commit:** `5d2d0beb028f1fd8b5b54b3fc3fd360ed108f67f` (local, branch `p8-worker-dispatcher`)
`fix(worker): fail closed on non-string fetch payload fields`

### Change
- `handle`: reads `url = payload.get("url")`, `content_type = payload.get("content_type")`, `size = payload.get("size", 0)`; rejects with `HandlerResult(state="blocked", detail="fetch.evidence: invalid payload")` when `payload` is not a dict or when `url`/`content_type` is not a `str`, before any use.
- `handle`: `size` coerced via `try: size_value = int(size) except (TypeError, ValueError): return HandlerResult(state="blocked", detail="fetch.evidence: invalid size")`; then `validate_fetch(url, content_type, size_value)` inside `try/except FetchRejected` -> `blocked` with `str(exc)`.
- No blanket `except Exception`; `validate_fetch` remains total for declared `(str, str, int)` inputs.
- Tests added: `test_non_string_url_is_blocked_not_raised` and `test_non_string_content_type_is_blocked_not_raised` (parametrized).

### Proof (previously-raising inputs now `blocked`)
`handle(None, None, {"url": None, "content_type": "text/html", "size": 1})` -> `blocked`; `{"url": 123}` -> `blocked`; `{"url": [1]}` -> `blocked`; `{"url": {"a": 1}}` -> `blocked`; `{"url": True}` -> `blocked`; `{"content_type": 123}` -> `blocked` (all returned `blocked`, none raised).

### Commands & output
- `uv run pytest -q` (from `services/worker`) -> `32 passed, 1 warning in 0.34s` (pre-existing pytest-asyncio `get_event_loop_policy` deprecation).
- `git commit -m "fix(worker): fail closed on non-string fetch payload fields"` -> `[p8-worker-dispatcher 5d2d0be] 2 files changed, 19 insertions(+), 2 deletions(-)`.

### Concerns
- None new. Only the two allowed files staged/committed; repo had unrelated dirty/untracked files left untouched.

---

## Corrective fix: block IPv6-literal and empty-host fetch URLs (HIGH SSRF)

**Status:** DONE

**Commit:** `5b5d38404e08c2c6f2be1e26e86c33ef68f7c707` (local, branch `p8-worker-dispatcher`)
`fix(worker): block IPv6-literal and empty-host fetch URLs`

### Root cause
`validate_fetch` parsed the host from `normalize_url(url)`. `normalize_url` (in `services/api/buyeros_api/services/safe_fetch.py`) drops IPv6 brackets (`parts.hostname` -> raw `::1`), so the rebuilt netloc was no longer bracketed and re-parsing yielded `None` (for `::1`, `::ffff:10.0.0.1`) or a truncated host (`fe80`, `fc00`), while `http:///x` produced an empty host. The blocked-host predicate therefore never saw the real IP literal and validation returned `done`.

Verified pre-fix: `normalize_url("http://[::1]/x")` -> `'http://::1/x'` -> `Hostname=None`; `normalize_url("http://[fc00::1]/x")` -> `'http://fc00::1/x'` -> `Hostname='fc00'`; all five URLs returned `state == "done"`.

### Change (only `fetch_evidence.py`)
- Host is now derived from the ORIGINAL url: `parts = urlsplit(url)`; `host = parts.hostname` (unwraps IPv6 brackets).
- Empty/missing host rejected: `if not host: raise FetchRejected("missing host")`.
- `_reject_if_blocked_host(host)` unchanged; it still calls `is_blocked_host` -> `ipaddress.ip_address`, so IPv6 and IPv4-mapped literals are evaluated. `ip_address("::ffff:10.0.0.1").is_global` is `False`, so it is rejected.
- Scheme check now uses `parts.scheme` from the original url.
- `normalize_url(url)` is still called (result discarded) solely to preserve the existing malformed-port / malformed-URL fail-closed behaviour.
- All other behaviour unchanged: size range, content-type allowlist, `FetchRejected` for malformed URLs, and `handle` returning `blocked` with no network call.

### Proof table (each URL now `blocked`)

| URL | Pre-fix `handle` state | Post-fix `handle` state | Post-fix detail |
|---|---|---|---|
| `http://[::1]/x` | done | **blocked** | `blocked host ::1` |
| `https://[fe80::1]/x` | done | **blocked** | `blocked host fe80::1` |
| `http://[fc00::1]/x` | done | **blocked** | `blocked host fc00::1` |
| `http://[::ffff:10.0.0.1]/x` | done | **blocked** | `blocked host ::ffff:10.0.0.1` |
| `http:///x` | done | **blocked** | `missing host` |

`validate_fetch` for each of the five URLs now raises `FetchRejected` (new parametrized test `test_ipv6_and_empty_host_are_rejected`); `handle` returns `blocked` for `http://[::1]/x` and `http:///x` (`test_ipv6_and_empty_host_blocked_via_handle`).

### Files touched
- `services/worker/buyeros_worker/handlers/fetch_evidence.py`
- `services/worker/tests/test_fetch_evidence.py`

### Commands & output
- `uv run pytest -q` (from `services/worker`) -> `39 passed, 1 warning in 0.33s` (pre-existing pytest-asyncio `get_event_loop_policy` deprecation).
- `git commit -m "fix(worker): block IPv6-literal and empty-host fetch URLs"` -> `[p8-worker-dispatcher 5b5d384] 2 files changed, 29 insertions(+), 5 deletions(-)`.

### Concerns (for final review; NOT fixed here)
- `buyeros_api/services/safe_fetch.py:normalize_url` drops IPv6 brackets (`host = (parts.hostname or "").lower()`, then `urlunsplit` without re-bracketing). Any other consumer that re-parses its output can mis-handle IPv6 literals. Fixing it belongs in `services/api` and was out of scope for this task.
- Hostnames are still accepted and rely on connection-time DNS/IP pinning (documented behaviour; no live fetch client in this phase).
