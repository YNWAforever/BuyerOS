import pytest

from buyeros_api.services.query_plan import UnsupportedDialect, TooManyQueries, validate_plan


def test_rejects_unsupported_dialect():
    with pytest.raises(UnsupportedDialect):
        validate_plan({"queries": [{"query": "x", "language": "zz"}], "rationale_summary": ""})


def test_enforces_total_query_cap():
    plan = {"queries": [{"query": f"q{i}", "language": "de"} for i in range(13)], "rationale_summary": ""}
    with pytest.raises(TooManyQueries):
        validate_plan(plan)


def test_accepts_valid_plan():
    plan = validate_plan({"queries": [{"query": "sensor distributor", "language": "de"}], "rationale_summary": "r"})
    assert plan.queries[0]["language"] == "de"


def test_accepts_empty_plan():
    assert validate_plan({"queries": [], "rationale_summary": ""}).queries == []
