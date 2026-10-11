"""Native retained-history route: no provider lookup or submission."""
import uuid
from pathlib import Path
import yaml
from fastapi.testclient import TestClient
from buyeros_api.api.app import create_app

PATH='/v1/workspaces/{workspace_id}/projects/{project_id}/drafts/{draft_id}/delivery-messages'

def test_retained_history_route_authenticates_before_any_history_read():
    path=PATH.format(workspace_id=uuid.uuid4(),project_id=uuid.uuid4(),draft_id=uuid.uuid4())
    with TestClient(create_app()) as client:
        response=client.get(path)
    assert response.status_code==401, response.text

def test_retained_history_contract_exposes_bounded_metadata_only():
    root=Path(__file__).resolve().parents[3]
    contract=yaml.safe_load((root/'docs/buyeros/contracts/openapi.proposed.yaml').read_bytes())
    assert PATH in contract['paths'], 'retained delivery history contract missing'
    op=contract['paths'][PATH]['get']
    assert op['operationId']=='listDraftDeliveryMessages'
    assert set(op['x-permitted-roles'])=={'viewer','operator','reviewer','workspace_admin'}
    schema=contract['components']['schemas']['DeliveryMessageMetadata']
    assert schema['additionalProperties'] is False
    assert not {'provider_ref','account_reference','intent_key','payload_digest','body','subject','recipient_email'} & set(schema['properties'])
    assert set(schema['properties']['state']['enum'])=={'prepared','submitting','unknown','accepted','delivered','bounced','complained','unsubscribed','failed','rejected'}
    assert contract['components']['schemas']['DeliveryMessagePage']['properties']['items']['maxItems']==100
