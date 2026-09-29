"""Cumulative logical-run ceilings, persisted on the locked SearchRun row."""

from datetime import datetime, timezone


class UsageExceeded(ValueError):
    pass


_CEILINGS = {
    "rounds": "query_rounds", "queries": "max_queries_per_run",
    "raw_results": "max_results", "pages": "max_pages",
    "model_tokens": "max_model_tokens", "in_flight": "provider_concurrency",
    "companies": None,
}


def advance_usage(run, increments: dict[str, int], *, at: datetime,
                  external: bool = False, page_bytes: int | None = None) -> dict[str, int]:
    """Apply one atomic claim; caller must hold a DB row lock until commit.

    A retry or new worker receives the stored counters and first dispatch time.
    Unknown usage dimensions and partial counter writes fail closed.
    """
    if at.tzinfo is None:
        raise ValueError("usage time must be timezone aware")
    if not isinstance(increments, dict) or not increments:
        raise ValueError("usage increment required")
    if any(name not in _CEILINGS or isinstance(delta, bool) or
           not isinstance(delta, int) or (delta < 0 and name != "in_flight")
           for name, delta in increments.items()):
        raise ValueError("invalid usage dimension or delta")
    if page_bytes is not None:
        if increments.get("pages") != 1:
            raise ValueError("each page byte observation requires one counted page attempt")
        if isinstance(page_bytes, bool) or not isinstance(page_bytes, int) or page_bytes < 0:
            raise ValueError("invalid page byte count")
        if page_bytes > run.limits["max_page_bytes"]:
            raise UsageExceeded("page byte ceiling exceeded")
    first = run.first_dispatch_at
    # The wall-clock cap prevents another dispatch. A prior provider may return
    # after the deadline, and its verified usage/result must still be recorded.
    dispatch_claim = external or any(increments.get(name, 0) > 0 for name in
                                     ("rounds", "queries", "pages", "in_flight"))
    if first is not None and dispatch_claim:
        elapsed = (at.astimezone(timezone.utc) - first.astimezone(timezone.utc)).total_seconds()
        if elapsed < 0 or elapsed > run.limits["max_duration_seconds"]:
            raise UsageExceeded("run duration ceiling exceeded")
    next_usage = dict(run.usage_counters or {})
    for name, delta in increments.items():
        current = next_usage.get(name, 0)
        if isinstance(current, bool) or not isinstance(current, int) or current < 0:
            raise ValueError("persisted run usage is invalid")
        ceiling_key = _CEILINGS[name]
        maximum = run.target_companies if ceiling_key is None else run.limits[ceiling_key]
        proposed = current + delta
        if proposed < 0 or proposed > maximum:
            raise UsageExceeded(f"{name} ceiling exceeded")
        next_usage[name] = proposed
    run.usage_counters = next_usage
    if external and first is None:
        run.first_dispatch_at = at
    return next_usage
