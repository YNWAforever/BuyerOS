"""API-required evidence must not accept a seeded-only legacy capture."""
from tests.test_mixed_workload_tools import positive, validator


def test_api_admission_claim_without_http_receipts_is_refused():
    report=positive()
    report['api_admission_required']=True
    assert not validator(report)
