"""Independent exact-revision delivery admission; no provider network side effect."""
import re
import uuid

from fastapi import APIRouter, Depends, Header, Request, Response

from ...services.delivery_admission import admit_delivery
from ...services.delivery_budget import DeliveryBudgetAuthorization
from ...services.delivery_reconciliation import reconcile_delivery_message
from ...settings import get_settings
from ..auth import Principal, get_principal
from ..deps import get_engine, load_membership, permission_for_roles, read_current_membership, tenant_scoped
from ..errors import ApiError, envelope
from ..idempotency import begin_idempotency, complete_idempotency
from ..schemas import DeliveryAdmissionRequest, DeliveryReconciliationRequest

router = APIRouter(prefix="/v1/workspaces/{workspace_id}", tags=["delivery"])


def selected_delivery_authorization(*, workspace_id: uuid.UUID, draft_id: uuid.UUID,
                                    actor_id: uuid.UUID) -> DeliveryBudgetAuthorization | None:
    # A reviewed server-owned registry must explicitly select this independent
    # scope. Neither a request field nor a feature flag selects an account/price.
    return None


@router.post("/drafts/{draft_id}/delivery-intents", status_code=202,
             operation_id="admitDraftDelivery")
async def admit_draft_delivery(workspace_id: uuid.UUID, draft_id: uuid.UUID,
                               payload: DeliveryAdmissionRequest, request: Request,
                               principal: Principal = Depends(get_principal),
                               idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")) -> dict:
    if not get_settings().delivery_admission_enabled:
        raise ApiError(403, "DELIVERY_DISABLED", "new delivery admission is disabled")
    # The shared API contract's minimum and the permanent delivery intent's
    # stricter bounded ASCII key both apply; invalid keys must not become500.
    if not idempotency_key or re.fullmatch(r"[A-Za-z0-9:_/-]{8,128}", idempotency_key) is None:
        raise ApiError(400, "INVALID_REQUEST", "bounded delivery Idempotency-Key is required")
    async with tenant_scoped(workspace_id) as session:
        member = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(member["roles"], "admitDraftDelivery"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        authorization = selected_delivery_authorization(
            workspace_id=workspace_id, draft_id=draft_id, actor_id=member["user_id"])
        if type(authorization) is not DeliveryBudgetAuthorization:
            raise ApiError(503, "PROVIDER_UNAVAILABLE", "reviewed delivery authority is unavailable")
        outcome = await begin_idempotency(session, workspace_id=workspace_id,
            actor_id=member["user_id"], operation_id="admitDraftDelivery", key=idempotency_key,
            body=payload.model_dump(mode="json"),
            target={"workspace_id": str(workspace_id), "draft_id": str(draft_id)})
        # Replays always re-enter the authoritative admission checks. Returning
        # a cached202 here would bypass current membership/approval/policy and
        # hide an original unknown/accepted state or rebind its immutable scope.
        admitted = await admit_delivery(session, authorization=authorization,
            environment="production", workspace_id=workspace_id, actor_id=member["user_id"],
            draft_id=draft_id, key=idempotency_key, **payload.model_dump())
        data = {"message_id": str(admitted.message_id), "state": admitted.state,
                "replayed": admitted.replayed}
        if not outcome.replay:
            complete_idempotency(outcome, str(admitted.message_id),
                response={"http_status": 202, "data": data})
    return envelope(data, request.state.request_id)


@router.post("/delivery-messages/{message_id}/reconciliation",
             operation_id="reconcileDeliveryMessage")
async def reconcile_message_delivery(workspace_id: uuid.UUID, message_id: uuid.UUID,
                                      request: Request, response: Response,
                                      payload: DeliveryReconciliationRequest | None = None,
                                      principal: Principal = Depends(get_principal)) -> dict:
    if not get_settings().reconciliation_enabled:
        raise ApiError(503, "CAPABILITY_DISABLED", "new reconciliation requests are disabled")
    async with tenant_scoped(workspace_id) as session:
        member = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(member["roles"], "reconcileDeliveryMessage"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
    # Canonical membership/rate transactions are closed before retained GET.
    # Only the server resolver can select original account/ref/contract authority.
    receipt = await reconcile_delivery_message(get_engine(), workspace_id=workspace_id,
                                              message_id=message_id)
    async with tenant_scoped(workspace_id) as session:
        # Persist a received original observation even if the initiating admin
        # loses access mid-GET; fresh authority still gates the HTTP response.
        # Do not charge a second rate slot after saving that independent receipt.
        member = await read_current_membership(session, principal=principal,
                                               workspace_id=workspace_id)
        if not permission_for_roles(member["roles"], "reconcileDeliveryMessage"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
    response.headers["Cache-Control"] = "private, no-store"
    return envelope({"message_id": str(receipt.message_id), "state": receipt.state,
                     "event_id": str(receipt.event_id) if receipt.event_id else None,
                     "replayed": receipt.replayed}, request.state.request_id)
