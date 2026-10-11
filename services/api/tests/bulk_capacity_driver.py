"""Owned bulk resource observations, without numerical or release acceptance."""
import importlib.util
import math
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("bulk_owned_rss_reader", ROOT / "services/worker/tests/worker_capacity_driver.py")
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)


def sample_api_resources(samples, at_seconds):
    # The current interpreter executes the API; avoid measuring its Windows launcher.
    pid = os.getpid()
    rss, method = reader._process_rss(pid)
    samples.append(dict(owner_pid=pid, pid=pid, parent_pid=None, depth=0,
                        at_seconds=at_seconds, rss_bytes=rss, method=method))


def captures_complete(captures):
    def finite(value):
        return type(value) in (int, float) and math.isfinite(value) and value >= 0

    if not isinstance(captures, list) or len(captures) != 3 or any(not isinstance(r, dict) for r in captures):
        return False
    if [r.get("count") for r in captures] != [50, 500, 10000]:
        return False
    for report in captures:
        count = report["count"]
        asynchronous = count > 100
        conflicts = 50 if asynchronous else 0
        if (report.get("completed") is not True or report.get("distinct_results") != count
            or report.get("updated") != count-conflicts or report.get("conflicts") != conflicts
            or report.get("fixture_only") is not True or report.get("live_verified") is not False
            or report.get("release_accepted") is not False or report.get("budget_adopted") is not False
            or not finite(report.get("duration_seconds"))):
            return False
        api_pid = report.get("api_pid")
        restart_pid = report.get("restart_pid")
        restart_owner = report.get("restart_owner_pid")
        if type(api_pid) is not int or api_pid <= 0:
            return False
        if asynchronous and (type(restart_pid) is not int or restart_pid <= 0 or restart_pid == api_pid
                             or type(restart_owner) is not int or restart_owner <= 0 or restart_owner == api_pid):
            return False
        if not asynchronous and (restart_pid is not None or restart_owner is not None):
            return False
        samples = report.get("memory_samples")
        if not isinstance(samples, list) or not samples:
            return False
        owners = {api_pid, restart_owner} if asynchronous else {api_pid}
        groups = {}
        for row in samples:
            if (not isinstance(row, dict) or row.get("owner_pid") not in owners
                or type(row.get("pid")) is not int or row["pid"] <= 0
                or type(row.get("rss_bytes")) is not int or row["rss_bytes"] <= 0
                or type(row.get("depth")) is not int or not 0 <= row["depth"] <= 4
                or not finite(row.get("at_seconds"))
                or row.get("method") not in {"linux_proc_status_VmRSS", "windows_GetProcessMemoryInfo_WorkingSetSize"}):
                return False
            groups.setdefault((row["owner_pid"], row["at_seconds"]), []).append(row)
        if len({row["method"] for row in samples}) != 1 or {row["owner_pid"] for row in samples} != owners:
            return False
        if [r["at_seconds"] for r in samples] != sorted(r["at_seconds"] for r in samples):
            return False
        if len([r for r in samples if r["pid"] == api_pid]) < 2:
            return False
        if asynchronous and len({r["at_seconds"] for r in samples
                                 if r["owner_pid"] == restart_owner and r["pid"] == restart_pid}) < 2:
            return False
        for (owner, _), rows in groups.items():
            indexed = {r["pid"]: r for r in rows}
            if len(rows) > 16 or len(indexed) != len(rows) or owner not in indexed:
                return False
            if indexed[owner].get("parent_pid") is not None or indexed[owner]["depth"] != 0:
                return False
            for row in rows:
                if row["pid"] == owner:
                    continue
                parent = indexed.get(row.get("parent_pid"))
                if parent is None or row["depth"] != parent["depth"] + 1:
                    return False
        snapshots = report.get("queue_snapshots")
        mode = "async_job_created_age" if asynchronous else "sync_no_queue"
        if report.get("queue_mode") != mode or not isinstance(snapshots, list):
            return False
        if not asynchronous:
            if snapshots:
                return False
            continue
        if len(snapshots) < 2:
            return False
        for row in snapshots:
            if (not isinstance(row, dict) or not finite(row.get("at_seconds"))
                or not finite(row.get("job_created_age_seconds"))
                or type(row.get("pending")) is not int or not 0 <= row["pending"] <= count
                or type(row.get("processed")) is not int or row["processed"] + row["pending"] != count
                or row.get("status") not in {"queued", "running", "completed"}):
                return False
        if [r["at_seconds"] for r in snapshots] != sorted(r["at_seconds"] for r in snapshots):
            return False
        if snapshots[0]["pending"] != count or snapshots[0]["processed"] != 0:
            return False
        if snapshots[-1]["pending"] != 0 or snapshots[-1]["status"] != "completed":
            return False
    return True
