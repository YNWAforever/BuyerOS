"""Raw provider callback entrypoint; no tenant selector is accepted from HTTP."""

import re

from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from ..deps import get_engine
from ..errors import ApiError, envelope
from ...db.session import tenant_session
from ...services.callback import verify_raw_callback
from ...services.contact_result_service import apply_verified_result

router = APIRouter(prefix="/v1/provider-callbacks", tags=["provider callbacks"])


def selected_callback_verifier():
    """No named live vendor or raw signature protocol has been activated."""
    return None, "production"


@router.post("/{provider}", name="receiveProviderCallback")
async def receive_provider_callback(provider: str, request: Request,
                                    selection=Depends(selected_callback_verifier)):
    if re.fullmatch(r"[a-z0-9_-]{1,40}", provider) is None:
        raise ApiError(422, "INVALID_REQUEST", "invalid provider name")
    verifier, environment = selection
    event = verify_raw_callback(provider, await request.body(), dict(request.headers),
                                verifier=verifier, environment=environment)
    engine = get_engine()
    # This narrow SECURITY DEFINER resolver sees only reference-to-operation
    # identifiers. Runtime roles cannot SELECT the routing table directly.
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        async with session.begin():
            route = (await session.execute(text(
                "SELECT workspace_id, operation_id FROM resolve_provider_callback_route("
                ":provider, :account, :reference)"), {
                    "provider": provider,
                    "account": event["account_reference"],
                    "reference": event["operation_reference"],
                })).one_or_none()
    if route is None:
        raise ApiError(404, "NOT_FOUND", "provider operation not found")
    async with tenant_session(engine, route.workspace_id) as session:
        result = await apply_verified_result(
            session, workspace_id=route.workspace_id, operation_id=route.operation_id,
            provider=provider, account_reference=event["account_reference"],
            provider_ref=event["operation_reference"], event_id=event["event_id"],
            digest=event["digest"], state=event["state"],
            observed_cost=event["observed_cost"],
        )
    return envelope({"accepted": result["accepted"], "duplicate": result["duplicate"],
                     "request_id": request.state.request_id}, request.state.request_id)
