"""A declared required field and its type must be enforced on real responses."""

from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID

import pytest
from jsonschema import ValidationError

from buyeros_api.api.routes.projects import _project_data
from contract_validation import assert_contract_response


def _project_response() -> dict:
    project = SimpleNamespace(
        id=UUID("11111111-1111-4111-8111-111111111111"),
        workspace_id=UUID("22222222-2222-4222-8222-222222222222"),
        version=1,
        offer_revision=1,
        created_at=datetime(2026, 9, 27, tzinfo=timezone.utc),
        updated_at=datetime(2026, 9, 27, tzinfo=timezone.utc),
        name="Pilot",
        company_name="Pilot Co",
        offer="Industrial pumps",
        website=None,
        markets=["US"],
        language_preferences=["en"],
        status="active",
        active_icp_version_id=None,
    )
    return _project_data(project)


def test_contract_required_fields():
    payload = _project_response()
    assert_contract_response("Project", payload)

    missing = deepcopy(payload)
    del missing["workspace_id"]
    with pytest.raises(ValidationError, match="required"):
        assert_contract_response("Project", missing)

    wrong_enum = deepcopy(payload)
    wrong_enum["status"] = "draft"
    with pytest.raises(ValidationError):
        assert_contract_response("Project", wrong_enum)

    wrong_type = deepcopy(payload)
    wrong_type["version"] = "1"
    with pytest.raises(ValidationError):
        assert_contract_response("Project", wrong_type)
