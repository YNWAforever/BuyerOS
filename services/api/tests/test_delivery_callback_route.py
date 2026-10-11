"""C61-20 public callback ingress stays closed without a reviewed server endpoint."""
from fastapi.testclient import TestClient

from buyeros_api.api import deps
from buyeros_api.api.app import create_app


def test_delivery_callback_route_unselected_refuses_before_any_database(monkeypatch):
    def no_database(*args, **kwargs):
        raise AssertionError("unselected callback must not open a database")
    monkeypatch.setattr(deps, "get_engine", no_database)
    with TestClient(create_app()) as client:
        response = client.post("/v1/delivery-callbacks/resend/owned-endpoint",
                               content=b'{"workspace_id":"caller-cannot-select"}',
                               headers={"Authorization":"Bearer caller-cannot-activate",
                                        "svix-id":"evt_unselected"})
    assert response.status_code == 503, response.text
    assert response.json()["code"] == "PROVIDER_UNAVAILABLE"
import base64
import hashlib
import hmac
import importlib
import json
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import pytest

from buyeros_api.api.errors import ApiError
from buyeros_api.services.delivery_callbacks import DeliveryCallbackReceipt, DeliveryWebhookEndpoint

SECRET = 'whsec_' + base64.b64encode(b'owned-callback-route-fixture-key!').decode()


def route_module():
    return importlib.import_module('buyeros_api.api.routes.delivery_callbacks')


def reviewed_endpoint(**changes):
    values = dict(workspace_id=uuid.uuid4(), account_reference='owned-fake-account',
                  reviewed_contract_hash='b'*64, signing_secret=SECRET, reviewed=True,
                  valid_until=datetime.now(timezone.utc)+timedelta(hours=1))
    values.update(changes)
    return DeliveryWebhookEndpoint(**values)


def signed_body(*, stamp=None, secret=SECRET, event='email.sent'):
    event_id='evt_'+uuid.uuid4().hex
    stamp=str(int(time.time())) if stamp is None else str(stamp)
    raw=json.dumps(dict(type=event, created_at=datetime.now(timezone.utc).isoformat(),
                        data=dict(email_id=str(uuid.uuid4()), workspace_id=str(uuid.uuid4()),
                                  account_reference='caller-cannot-select')), separators=(',',':')).encode()
    signature=base64.b64encode(hmac.digest(base64.b64decode(secret[6:]),
                              event_id.encode()+b'.'+stamp.encode()+b'.'+raw, 'sha256')).decode()
    return raw, {'svix-id':event_id,'svix-timestamp':stamp,'svix-signature':'v1,'+signature}


def app_with_registry(registry):
    app=create_app()
    app.dependency_overrides[route_module().selected_delivery_webhook_registry]=lambda:registry
    return app


def test_delivery_callback_registry_copies_bindings_and_never_selects_client_account():
    module=route_module();endpoint=reviewed_endpoint();bindings={'owned-endpoint':endpoint}
    registry=module.DeliveryWebhookRegistry(bindings)
    bindings['owned-endpoint']=reviewed_endpoint()
    assert registry.resolve('owned-endpoint')==endpoint
    with pytest.raises(TypeError):registry.endpoints['owned-endpoint']=reviewed_endpoint()
    with pytest.raises(ApiError) as error:registry.resolve('caller-cannot-select')
    assert (error.value.status_code,error.value.code)==(404,'NOT_FOUND')
    assert SECRET not in repr(registry)


@pytest.mark.parametrize('fault',['unreviewed','expired','wrong-type'])
def test_delivery_callback_registry_refuses_unreviewed_or_expired_bindings(fault):
    module=route_module()
    endpoint=(reviewed_endpoint(reviewed=False) if fault=='unreviewed' else
              reviewed_endpoint(valid_until=datetime.now(timezone.utc)-timedelta(seconds=1))
              if fault=='expired' else object())
    with pytest.raises((ValueError,ApiError)):module.DeliveryWebhookRegistry({'owned-endpoint':endpoint})


def test_delivery_callback_route_preserves_raw_signed_bytes_and_server_scope(monkeypatch):
    module=route_module();endpoint=reviewed_endpoint();registry=module.DeliveryWebhookRegistry({'owned-endpoint':endpoint})
    raw,headers=signed_body();calls=[];engine=object();session=object()
    monkeypatch.setattr(deps,'get_engine',lambda:engine)
    @asynccontextmanager
    async def owned_transaction(actual_engine,workspace_id):
        assert actual_engine is engine and workspace_id==endpoint.workspace_id
        calls.append('begin');yield session;calls.append('commit')
    async def record(actual_session,actual_raw,actual_headers,*,endpoint):
        assert actual_session is session and actual_raw==raw and actual_headers==headers
        calls.append(endpoint.workspace_id)
        return DeliveryCallbackReceipt(uuid.uuid4(),uuid.uuid4(),'accepted',False)
    monkeypatch.setattr(module,'tenant_session',owned_transaction)
    monkeypatch.setattr(module,'record_resend_delivery_webhook',record)
    with TestClient(app_with_registry(registry)) as client:
        response=client.post('/v1/delivery-callbacks/resend/owned-endpoint?workspace_id=caller',
                             content=raw,headers=headers)
    assert response.status_code==200,response.text
    assert response.json()['data']['state']=='accepted' and response.json()['data']['replayed'] is False
    assert calls==['begin',endpoint.workspace_id,'commit']
    from tests.contract_validation import assert_contract_response
    assert_contract_response('DeliveryCallbackReceiptResponse',response.json())
    assert 'caller-cannot-select' not in response.text and SECRET not in response.text


@pytest.mark.parametrize('fault',['tampered','wrong-key','past','future'])
def test_delivery_callback_route_invalid_signature_never_opens_database(monkeypatch,fault):
    module=route_module();registry=module.DeliveryWebhookRegistry({'owned-endpoint':reviewed_endpoint()})
    # Fix verification time: a delayed future+301 request can enter the legal window.
    observed=int(time.time())
    real_verify=module.verify_delivery_webhook
    monkeypatch.setattr(module,'verify_delivery_webhook',lambda body,headers,*,secret:
                        real_verify(body,headers,secret=secret,now=observed))
    raw,headers=signed_body(stamp=observed+(-301 if fault=='past' else 301 if fault=='future' else 0),
                            secret='whsec_'+base64.b64encode(b'wrong-owned-fixture-signing-key!').decode() if fault=='wrong-key' else SECRET)
    if fault=='tampered':raw+=b' '
    def no_database():raise AssertionError('bad callback must not open database')
    monkeypatch.setattr(deps,'get_engine',no_database)
    with TestClient(app_with_registry(registry)) as client:
        response=client.post('/v1/delivery-callbacks/resend/owned-endpoint',content=raw,headers=headers)
    assert response.status_code==403,response.text
    assert response.json()['code']=='PERMISSION_DENIED'


@pytest.mark.parametrize('header',['svix-id','svix-timestamp','svix-signature'])
def test_delivery_callback_route_duplicate_signature_headers_never_open_database(monkeypatch,header):
    module=route_module();registry=module.DeliveryWebhookRegistry({'owned-endpoint':reviewed_endpoint()})
    raw,headers=signed_body()
    def no_database():raise AssertionError('ambiguous callback must not open database')
    monkeypatch.setattr(deps,'get_engine',no_database)
    with TestClient(app_with_registry(registry)) as client:
        response=client.post('/v1/delivery-callbacks/resend/owned-endpoint',content=raw,
                             headers=list(headers.items())+[(header,headers[header])])
    assert response.status_code==403,response.text


@pytest.mark.parametrize('fault',['oversized','unsupported-event','unknown-endpoint','invalid-endpoint'])
def test_delivery_callback_route_invalid_metadata_or_endpoint_never_opens_database(monkeypatch,fault):
    module=route_module();registry=module.DeliveryWebhookRegistry({'owned-endpoint':reviewed_endpoint()})
    raw,headers=signed_body(event='email.opened' if fault=='unsupported-event' else 'email.sent')
    if fault=='oversized':raw=b'x'*65537
    endpoint='unknown-endpoint' if fault=='unknown-endpoint' else 'bad.endpoint' if fault=='invalid-endpoint' else 'owned-endpoint'
    def no_database():raise AssertionError('invalid callback must not open database')
    monkeypatch.setattr(deps,'get_engine',no_database)
    with TestClient(app_with_registry(registry)) as client:
        response=client.post('/v1/delivery-callbacks/resend/'+endpoint,content=raw,headers=headers)
    assert response.status_code==(404 if fault=='unknown-endpoint' else 422),response.text
