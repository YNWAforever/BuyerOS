"""Fail-closed feasibility evidence, independent of deployment credentials."""
import importlib.util
import sys
from pathlib import Path

import pytest

PROBE = Path(__file__).resolve().parents[1] / "tools/probe_worker_runtime.py"


def probe_module():
    assert PROBE.is_file(), "CF00 native runtime probe has not been implemented"
    spec = importlib.util.spec_from_file_location("cloudflare_runtime_probe", PROBE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("dsn", [
    "postgresql://user:secret@db.neon.tech/buyeros_test_probe",
    "postgresql://user:secret@127.0.0.1/buyeros",
    "postgresql://user:secret@localhost/shared",
    "postgresql://user:secret@localhost/buyeros_test_probe?host=db.neon.tech",
    "postgresql://user:secret@localhost/buyeros_test_probe#production",
    "postgresql://user:secret@localhost/buyeros_test_probe/production",
])
def test_probe_rejects_shared_or_production_database(dsn):
    with pytest.raises(ValueError, match="owned disposable loopback"):
        probe_module().require_disposable_database(dsn)


def test_probe_accepts_only_explicit_disposable_loopback_database():
    probe_module().require_disposable_database(
        "postgresql://buyeros:test-only@127.0.0.1:5432/buyeros_test_cf00"
    )


def test_probe_requires_native_parser_and_checkpoint_proof():
    module = probe_module()
    required = module.LOCAL_REQUIRED_CHECKS
    assert {"native_imports", "pdf_native", "pdf_isolation", "pdf_timeout",
            "postgres_checkpoint", "postgres_role"} <= set(required)
    records = [{"check": key, "state": "verified", "details": {}} for key in required]
    report = module.RuntimeProbeReport("local", "a" * 40, records)
    assert report.local_feasible
    for missing in ("pdf_native", "postgres_checkpoint", "postgres_role"):
        partial = [dict(item, state="not_run") if item["check"] == missing else item
                   for item in records]
        assert not module.RuntimeProbeReport("local", "a" * 40, partial).local_feasible
    assert not report.hosted_feasible


def test_probe_cannot_claim_hosted_proof_from_local_records():
    module = probe_module()
    records = [{"check": key, "state": "verified", "details": {}}
               for key in module.LOCAL_REQUIRED_CHECKS + module.HOSTED_REQUIRED_CHECKS]
    assert not module.RuntimeProbeReport("local", "a" * 40, records).hosted_feasible
