"""Evidence refusal controls; fixtures below are not performance measurements."""
import copy
import importlib.util
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


def load(path, name):
    assert path.is_file(), "owned bulk resource measurement tooling missing"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("variable", ["DATABASE_URL", "BUYEROS_DATABASE_URL", "BUYEROS_TEST_DATABASE_URL", "BUYEROS_WORKER_DATABASE_URL"])
def test_bulk_capacity_refuses_inherited_database_before_start(monkeypatch, tmp_path, variable):
    tool = load(ROOT / "scripts/benchmark-bulk-capacity.py", "bulk_wrapper")
    for key in tool.DATABASE_VARIABLES:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv(variable, "postgresql://not-used.invalid/shared")
    monkeypatch.setattr(sys, "argv", ["bulk", "--output-dir", str(tmp_path / "fresh")])
    monkeypatch.setattr(tool.subprocess, "run", lambda *a, **k: pytest.fail("must reject before child"))
    with pytest.raises(SystemExit) as denied:
        tool.main()
    assert denied.value.code == 2


def test_bulk_capacity_preserves_existing_evidence(monkeypatch, tmp_path):
    tool = load(ROOT / "scripts/benchmark-bulk-capacity.py", "bulk_wrapper")
    for key in tool.DATABASE_VARIABLES:
        monkeypatch.delenv(key, raising=False)
    folder = tmp_path / "retained"
    folder.mkdir()
    evidence = folder / "original.json"
    evidence.write_bytes(b"historical")
    monkeypatch.setattr(sys, "argv", ["bulk", "--output-dir", str(folder)])
    monkeypatch.setattr(tool.subprocess, "run", lambda *a, **k: pytest.fail("must preserve before child"))
    with pytest.raises(SystemExit) as denied:
        tool.main()
    assert denied.value.code == 2 and evidence.read_bytes() == b"historical"


def valid_captures():
    captures = []
    for count in [50, 500, 10000]:
        asynchronous = count > 100
        conflicts = 50 if asynchronous else 0
        samples = [dict(owner_pid=100, pid=100, parent_pid=None, depth=0, at_seconds=at,
                        rss_bytes=8192, method="linux_proc_status_VmRSS") for at in [0., 1.]]
        if asynchronous:
            samples.insert(1, dict(owner_pid=200, pid=200, parent_pid=None, depth=0,
                                   at_seconds=.5, rss_bytes=4096, method="linux_proc_status_VmRSS"))
            samples.insert(2, dict(owner_pid=200, pid=200, parent_pid=None, depth=0,
                                   at_seconds=.6, rss_bytes=8192, method="linux_proc_status_VmRSS"))
        captures.append(dict(count=count, updated=count-conflicts, conflicts=conflicts,
            distinct_results=count, completed=True, api_pid=100,
            restart_pid=200 if asynchronous else None, restart_owner_pid=200 if asynchronous else None,
            memory_samples=samples, queue_mode="async_job_created_age" if asynchronous else "sync_no_queue",
            queue_snapshots=[dict(at_seconds=at, pending=pending, processed=count-pending,
                                  job_created_age_seconds=at, status=status)
                             for at, pending, status in [(0., count, "queued"), (1., 0, "completed")]] if asynchronous else [],
            duration_seconds=1., fixture_only=True, live_verified=False, release_accepted=False,
            budget_adopted=False))
    return captures


@pytest.mark.parametrize("defect", ["missing-size", "duplicate-size", "missing-memory", "unowned-pid", "zero-rss", "missing-restart", "single-restart-sample", "missing-queue", "missing-row", "nan-age", "negative-age", "false-live"])
def test_bulk_capacity_refuses_partial_or_invalid_measurements(defect):
    driver = load(Path(__file__).with_name("bulk_capacity_driver.py"), "bulk_driver")
    reports = copy.deepcopy(valid_captures())
    if defect == "missing-size": reports.pop()
    if defect == "duplicate-size": reports[-1] = copy.deepcopy(reports[1])
    if defect == "missing-memory": reports[0]["memory_samples"] = []
    if defect == "unowned-pid": reports[0]["memory_samples"][0]["pid"] = 999
    if defect == "zero-rss": reports[0]["memory_samples"][0]["rss_bytes"] = 0
    if defect == "missing-restart": reports[1]["memory_samples"] = [r for r in reports[1]["memory_samples"] if r["pid"] != 200]
    if defect == "single-restart-sample": reports[1]["memory_samples"].pop(2)
    if defect == "missing-queue": reports[1]["queue_snapshots"] = []
    if defect == "missing-row": reports[-1]["queue_snapshots"][0]["pending"] -= 1
    if defect == "nan-age": reports[1]["queue_snapshots"][0]["job_created_age_seconds"] = float("nan")
    if defect == "negative-age": reports[1]["queue_snapshots"][0]["job_created_age_seconds"] = -1
    if defect == "false-live": reports[0]["live_verified"] = True
    assert driver.captures_complete(reports) is False


def test_bulk_capacity_accepts_complete_units_without_adopting_budget():
    driver = load(Path(__file__).with_name("bulk_capacity_driver.py"), "bulk_driver")
    reports = valid_captures()
    assert driver.captures_complete(reports) is True
    assert all(r["budget_adopted"] is False and r["release_accepted"] is False for r in reports)


def test_bulk_resource_sampler_reads_actual_current_interpreter():
    driver = load(Path(__file__).with_name("bulk_capacity_driver.py"), "bulk_driver")
    samples = []
    driver.sample_api_resources(samples, .25)
    assert len(samples) == 1 and samples[0]["pid"] == os.getpid()
    assert samples[0]["owner_pid"] == os.getpid() and samples[0]["rss_bytes"] > 0
    assert samples[0]["at_seconds"] == .25
