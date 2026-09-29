"""Declared contact quote routes; preview never reserves or invokes a provider."""

import uuid

from fastapi import APIRouter, Depends, Header, Request, Response

from ...services.quote_service import cancel_quote, quote_data, quote_lookup, require_quote
from ...services.confirm_service import confirm_lookup
from ...services.audit_service import append_audit
from ..auth import Principal, get_principal
from ..deps import load_membership, permission_for_roles, tenant_scoped
from ..errors import ApiError, envelope
from ..idempotency import begin_idempotency, complete_idempotency, if_match_version
from ..schemas import ArchiveRequest, QuoteRequest, QuoteConfirmRequest

router = APIRouter(prefix="/v1/workspaces/{workspace_id}/projects/{project_id}/enrichment-quotes",
                   tags=["contact-quotes"])
detail_router = APIRouter(prefix="/v1/workspaces/{workspace_id}/enrichment-quotes",
                          tags=["contact-quotes"])


def selected_contact_quote_capability():
    """No live provider or tariff is selected; tests inject a verified fixture."""
    return None, "production"


@router.post("", status_code=201, name="quoteLookup")
async def quote_lookup_http(
    workspace_id: uuid.UUID, project_id: uuid.UUID, payload: QuoteRequest,
    request: Request, response: Response,
    principal: Principal = Depends(get_principal),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    selection=Depends(selected_contact_quote_capability),
):
    if not idempotency_key:
        raise ApiError(400, "INVALID_REQUEST", "Idempotency-Key header is required")
    async with tenant_scoped(workspace_id) as session:
        member = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(member["roles"], "quoteLookup"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        outcome = await begin_idempotency(
            session, workspace_id=workspace_id, actor_id=member["user_id"],
            operation_id="quoteLookup", key=idempotency_key,
            body=payload.model_dump(mode="json"),
            target={"workspace_id": str(workspace_id), "project_id": str(project_id)},
        )
        if outcome.replay and outcome.response is not None:
            # The idempotency record preserves identity, while expiry is time-dependent.
            quote = await require_quote(session, workspace_id, uuid.UUID(outcome.response["data"]["id"]))
            data = quote_data(quote)
        else:
            capability, environment = selection
            quote = await quote_lookup(
                session, member["user_id"], project_id, payload,
                workspace_id=workspace_id, capability=capability, environment=environment,
            )
            data = quote_data(quote)
            append_audit(session, workspace_id=workspace_id, actor_id=member["user_id"],
                         action="contact_quote.quoted", entity_type="contact_quote", entity_id=quote.id)
            complete_idempotency(outcome, str(quote.id), response={"http_status": 201, "data": data})
    response.headers["ETag"] = f'"{data["version"]}"'
    return envelope(data, request.state.request_id)


@detail_router.get("/{quote_id}", name="getLookupQuote")
async def get_lookup_quote(
    workspace_id: uuid.UUID, quote_id: uuid.UUID, request: Request, response: Response,
    principal: Principal = Depends(get_principal),
):
    async with tenant_scoped(workspace_id) as session:
        member = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(member["roles"], "getLookupQuote"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        quote = await require_quote(session, workspace_id, quote_id)
        if quote.actor_id != member["user_id"] and "workspace_admin" not in member["roles"]:
            raise ApiError(404, "NOT_FOUND", "quote not found")
        data = quote_data(quote)
    response.headers["ETag"] = f'"{data["version"]}"'
    return envelope(data, request.state.request_id)


@detail_router.post("/{quote_id}/cancel", name="cancelLookupQuote")
async def cancel_lookup_quote(
    workspace_id: uuid.UUID, quote_id: uuid.UUID, payload: ArchiveRequest, request: Request, response: Response,
    principal: Principal = Depends(get_principal),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    if_match: str | None = Header(default=None, alias="If-Match"),
):
    if not idempotency_key:
        raise ApiError(400, "INVALID_REQUEST", "Idempotency-Key header is required")
    version = if_match_version(if_match)
    async with tenant_scoped(workspace_id) as session:
        member = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(member["roles"], "cancelLookupQuote"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        outcome = await begin_idempotency(
            session, workspace_id=workspace_id, actor_id=member["user_id"],
            operation_id=f"cancelLookupQuote:{quote_id}", key=idempotency_key,
            body=payload.model_dump(), target={"quote_id": str(quote_id)}, precondition=if_match,
        )
        if outcome.replay and outcome.response is not None:
            data = outcome.response["data"]
        else:
            quote = await cancel_quote(session, workspace_id, quote_id, member["user_id"],
                                       expected_version=version)
            data = quote_data(quote)
            append_audit(session, workspace_id=workspace_id, actor_id=member["user_id"],
                         action="contact_quote.cancelled", entity_type="contact_quote",
                         entity_id=quote.id, reason=payload.reason)
            complete_idempotency(outcome, str(quote_id), response={"http_status": 200, "data": data})
    response.headers["ETag"] = f'"{data["version"]}"'
    return envelope(data, request.state.request_id)


@detail_router.post("/{quote_id}/confirm", status_code=202, name="confirmLookup")
async def confirm_lookup_http(
    workspace_id: uuid.UUID, quote_id: uuid.UUID, payload: QuoteConfirmRequest,
    request: Request, response: Response,
    principal: Principal = Depends(get_principal),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    selection=Depends(selected_contact_quote_capability),
):
    if not idempotency_key:
        raise ApiError(400, "INVALID_REQUEST", "Idempotency-Key header is required")
    async with tenant_scoped(workspace_id) as session:
        member = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(member["roles"], "confirmLookup"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        outcome = await begin_idempotency(
            session, workspace_id=workspace_id, actor_id=member["user_id"],
            operation_id=f"confirmLookup:{quote_id}", key=idempotency_key,
            body=payload.model_dump(mode="json"), target={"quote_id": str(quote_id)},
        )
        if outcome.replay and outcome.response is not None:
            data = outcome.response["data"]
        else:
            capability, environment = selection
            data = await confirm_lookup(session, member["user_id"], quote_id, payload,
                                        idempotency_key, workspace_id=workspace_id,
                                        capability=capability, environment=environment)
            complete_idempotency(outcome, data["id"], response={"http_status": 202, "data": data})
    response.headers["ETag"] = f'"{data["version"]}"'
    return envelope(data, request.state.request_id)
