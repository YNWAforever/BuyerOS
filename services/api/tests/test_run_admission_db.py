"""T18 run admission and request boundary (disposable database for DB cases)."""

import pytest
from pydantic import ValidationError

from buyeros_api.api.schemas import RunCreate


LIMITS = {
    "query_rounds": 3,
    "max_queries_per_run": 12,
    "max_results": 300,
    "max_pages": 200,
    "max_page_bytes": 2097152,
    "max_duration_seconds": 1800,
    "max_model_tokens": 100000,
    "provider_concurrency": 4,
}


@pytest.mark.parametrize("field,over", [
    ("query_rounds", 4), ("max_queries_per_run", 13), ("max_results", 301),
    ("max_pages", 201), ("max_page_bytes", 2097153),
    ("max_duration_seconds", 1801), ("max_model_tokens", 100001),
    ("provider_concurrency", 5),
])
def test_run_request_rejects_each_limit_above_the_contract_ceiling(field, over):
    with pytest.raises(ValidationError):
        RunCreate.model_validate({
            "icp_version_id": "10000000-0000-4000-8000-000000000001",
            "target_companies": 100,
            "max_cost": {"amount": "1.000000", "currency": "USD"},
            "limits": {**LIMITS, field: over},
        })


def test_run_request_rejects_float_money_extra_fields_and_target_overflow():
    valid = {
        "icp_version_id": "10000000-0000-4000-8000-000000000001",
        "target_companies": 100,
        "max_cost": {"amount": "1.000000", "currency": "USD"},
        "limits": LIMITS,
    }
    assert RunCreate.model_validate(valid).limits.max_queries_per_run == 12
    for mutation in (
        {**valid, "target_companies": 101},
        {**valid, "max_cost": {"amount": 1.0, "currency": "USD"}},
        {**valid, "limits": {**LIMITS, "unknown": 1}},
    ):
        with pytest.raises(ValidationError):
            RunCreate.model_validate(mutation)


def test_run_money_rejects_database_precision_overflow():
    with pytest.raises(ValidationError):
        RunCreate.model_validate({
            "icp_version_id": "10000000-0000-4000-8000-000000000001",
            "target_companies": 1,
            "max_cost": {"amount": "100000000000000.000000", "currency": "USD"},
            "limits": LIMITS,
        })
