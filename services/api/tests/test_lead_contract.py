from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from buyeros_api.api.app import create_app

BASE = "/v1/workspaces/{workspace_id}/projects/{project_id}"
OPERATIONS = {
    ("get", BASE + "/buyers/{buyer_id}/lead-evidence"): "listLeadEvidence",
    ("post", BASE + "/lead-intents"): "prepareLeadIntent",
    ("get", BASE + "/lead-intents"): "listLeadIntents",
    ("get", BASE + "/lead-intents/{intent_id}"): "getLeadIntent",
    ("post", BASE + "/lead-intents/{intent_id}/apply"): "applyLeadIntent",
    ("post", BASE + "/lead-intents/{intent_id}/acknowledgements"): "acknowledgeLeadIntent",
    ("post", BASE + "/lead-intents/{intent_id}/cancel"): "cancelLeadIntent",
}


def test_lead_api_operations_exist_and_enforce_auth_before_data_access():
    contract = yaml.safe_load(Path("../../docs/buyeros/contracts/openapi.proposed.yaml").read_text(encoding="utf-8"))
    app = create_app()
    published = app.openapi()["paths"]
    with TestClient(app, raise_server_exceptions=False) as api:
        for (method, path), operation in OPERATIONS.items():
            assert path in published and method in published[path]
            assert published[path][method]["operationId"] == operation
            assert contract["paths"][path][method]["operationId"] == operation
            actual = path.replace("{workspace_id}", "11111111-1111-4111-8111-111111111111")
            actual = actual.replace("{project_id}", "a0000000-0000-4000-8000-000000000001")
            actual = actual.replace("{buyer_id}", "33333333-3333-4333-8333-333333333333")
            actual = actual.replace("{intent_id}", "44444444-4444-4444-8444-444444444444")
            assert api.request(method, actual, json={}).status_code == 401
