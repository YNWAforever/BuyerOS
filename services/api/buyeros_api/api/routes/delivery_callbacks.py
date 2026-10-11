"""Unselected signed delivery ingress; server endpoint binding is sole authority."""
import re
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from types import MappingProxyType

from fastapi import APIRouter, Depends, Request

from .. import deps
from ..errors import ApiError, envelope
from ...db.session import tenant_session
from ...providers.delivery import verify_delivery_webhook
from ...services.delivery_callbacks import (
    DeliveryWebhookEndpoint, _event_metadata, _require_endpoint,
    record_resend_delivery_webhook,
)

router = APIRouter(prefix="/v1/delivery-callbacks/resend", tags=["delivery callbacks"])
MAX_RAW_BODY_BYTES = 65536
SIGNATURE_HEADERS = ("svix-id", "svix-timestamp", "svix-signature")


def _endpoint_key(value):
    if not isinstance(value, str) or re.fullmatch(r"[a-z0-9_-]{1,64}", value) is None:
        raise ApiError(422, "INVALID_REQUEST", "invalid delivery endpoint reference")
    return value


@dataclass(frozen=True, repr=False)
class DeliveryWebhookRegistry:
    """Private reviewed retained endpoints, never deserialize request/config JSON.

    A snapshot copies both the map and frozen endpoint fields. No environment
    variable, user JWT, query, body or account header installs this registry.
    Retained callbacks do not renew new-send permissions or release liability.
    """
    endpoints: Mapping[str, DeliveryWebhookEndpoint] = field(repr=False)

    def __post_init__(self):
        if not isinstance(self.endpoints, Mapping):
            raise ValueError("server-owned delivery endpoint bindings required")
        copied = {}
        for key, endpoint in self.endpoints.items():
            _endpoint_key(key)
            if type(endpoint) is not DeliveryWebhookEndpoint:
                raise ValueError("server-owned delivery endpoint binding required")
            frozen = replace(endpoint)
            _require_endpoint(frozen)
            copied[key] = frozen
        object.__setattr__(self, "endpoints", MappingProxyType(copied))

    def resolve(self, endpoint_id):
        key = _endpoint_key(endpoint_id)
        endpoint = self.endpoints.get(key)
        if endpoint is None:
            raise ApiError(404, "NOT_FOUND", "delivery endpoint not found")
        endpoint.__post_init__()
        _require_endpoint(endpoint)
        return endpoint


def selected_delivery_webhook_registry() -> DeliveryWebhookRegistry | None:
    """Actual reviewed provider/account/endpoint selection remains closed."""
    return None


@router.post("/{endpoint_id}", name="receiveDeliveryCallback")
async def receive_delivery_callback(endpoint_id: str, request: Request,
                                    registry=Depends(selected_delivery_webhook_registry)):
    _endpoint_key(endpoint_id)
    if type(registry) is not DeliveryWebhookRegistry:
        raise ApiError(503, "PROVIDER_UNAVAILABLE", "retained delivery endpoint registry unavailable")
    endpoint = registry.resolve(endpoint_id)
    raw = bytearray()
    async for chunk in request.stream():
        if len(raw)+len(chunk) > MAX_RAW_BODY_BYTES:
            raise ApiError(422, "INVALID_REQUEST", "bounded raw delivery callback required")
        raw.extend(chunk)
    # Duplicate signature headers are ambiguous, even if one value verifies.
    if any(len(request.headers.getlist(name)) != 1 for name in SIGNATURE_HEADERS):
        raise ApiError(403, "PERMISSION_DENIED", "invalid delivery webhook")
    headers = {name: request.headers[name] for name in SIGNATURE_HEADERS}
    body = bytes(raw)
    try:
        verified = verify_delivery_webhook(body, headers, secret=endpoint.signing_secret)
    except ValueError:
        raise ApiError(403, "PERMISSION_DENIED", "invalid delivery webhook") from None
    _event_metadata(verified.raw_body)
    _require_endpoint(endpoint)
    # Raw bytes are authenticated before any tenant DB access. The durable
    # service verifies again inside its atomic, RLS-bound transaction; no caller
    # field supplies workspace/account/reference authority or a send permission.
    async with tenant_session(deps.get_engine(), endpoint.workspace_id) as session:
        receipt = await record_resend_delivery_webhook(session, body, headers, endpoint=endpoint)
    return envelope({"message_id": str(receipt.message_id), "event_id": str(receipt.event_id),
                     "state": receipt.state, "replayed": receipt.replayed}, request.state.request_id)
