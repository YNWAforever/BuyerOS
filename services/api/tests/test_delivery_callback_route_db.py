"""C61-20 real public callback transaction with restricted owned PG only."""
import uuid

import pytest

from tests.contract_validation import assert_contract_response
from tests.test_delivery_callbacks_db import endpoint, signed, snapshot, submitted
from tests.test_delivery_ledger_db import ledger_case


def installed(data):
    from buyeros_api.api.routes.delivery_callbacks import DeliveryWebhookRegistry, selected_delivery_webhook_registry
    auth=endpoint(data)
    data['client'].app.dependency_overrides[selected_delivery_webhook_registry]=lambda:DeliveryWebhookRegistry({'owned-endpoint':auth})
    return '/v1/delivery-callbacks/resend/owned-endpoint'


def test_delivery_public_callback_duplicate_and_late_sent_keep_original_hold(isolated_quote_case):
    with ledger_case(isolated_quote_case) as data:
        ref=submitted(data);path=installed(data);before=snapshot(data)
        raw,headers=signed(ref,'email.delivered')
        first=data['client'].post(path,content=raw,headers=headers)
        repeated=data['client'].post(path,content=raw,headers=headers)
        late_raw,late_headers=signed(ref,'email.sent')
        late=data['client'].post(path,content=late_raw,headers=late_headers)
        for response in [first,repeated,late]:
            assert response.status_code==200,response.text
            assert_contract_response('DeliveryCallbackReceiptResponse',response.json())
            assert response.json()['data']['state']=='delivered'
        assert first.json()['data']['replayed'] is False and repeated.json()['data']['replayed'] is True
        assert first.json()['data']['event_id']==repeated.json()['data']['event_id']
        after=snapshot(data)
        assert after['state']==('delivered',ref) and len(after['events'])==2
        for name in ['hold','cost','outbox']:assert after[name]==before[name]


@pytest.mark.parametrize('fault',['invalid-signature','foreign-reference'])
def test_delivery_public_callback_forged_or_unbound_reference_never_changes_ledger(isolated_quote_case,fault):
    with ledger_case(isolated_quote_case) as data:
        ref=submitted(data);path=installed(data);before=snapshot(data)
        raw,headers=signed(str(uuid.uuid4()) if fault=='foreign-reference' else ref)
        if fault=='invalid-signature':raw+=b' '
        response=data['client'].post(path,content=raw,headers=headers)
        assert response.status_code==(403 if fault=='invalid-signature' else 404),response.text
        assert snapshot(data)==before


def test_delivery_public_callback_bounce_is_atomic_retained_adverse_evidence(isolated_quote_case):
    from tests.test_lookup_quotes_db import WORKSPACE_A, REVIEWER, _h
    with ledger_case(isolated_quote_case) as data:
        ref=submitted(data);path=installed(data);before=snapshot(data);raw,headers=signed(ref,'email.bounced')
        first=data['client'].post(path,content=raw,headers=headers)
        repeated=data['client'].post(path,content=raw,headers=headers)
        assert first.status_code==repeated.status_code==200
        assert first.json()['data']['state']==repeated.json()['data']['state']=='bounced'
        after=snapshot(data);assert after['suppression']==before['suppression']+1 and len(after['events'])==1
        for name in ['hold','cost','outbox']:assert after[name]==before[name]
        response=data['client'].post(f"/v1/workspaces/{WORKSPACE_A}/drafts/{data['args']['draft_id']}/deliver",headers=_h(REVIEWER,key='public-callback-no-send'))
        assert response.status_code==403 and response.json()['code']=='DELIVERY_DISABLED'


def test_delivery_public_callback_transaction_abort_keeps_original_unknown(isolated_quote_case,monkeypatch):
    from buyeros_api.api.routes import delivery_callbacks as module
    with ledger_case(isolated_quote_case) as data:
        ref=submitted(data);path=installed(data);before=snapshot(data);raw,headers=signed(ref,'email.bounced')
        original=module.record_resend_delivery_webhook
        async def abort_after_writes(*args,**kwargs):
            await original(*args,**kwargs)
            raise RuntimeError('owned callback transaction abort')
        monkeypatch.setattr(module,'record_resend_delivery_webhook',abort_after_writes)
        response=data['client'].post(path,content=raw,headers=headers)
        assert response.status_code==500,response.text
        assert snapshot(data)==before
