"""Explicit 501 handlers for contract operations outside the P9 slice.

Handlers are registered on the operations' **declared** contract path+method, so
no parallel or invented endpoint exists. Each still requires a principal, so the
surface fails closed (401) when auth is unconfigured, then returns 501 once
authenticated.
"""

from fastapi import APIRouter, Depends, Request

from .auth import Principal, get_principal
from .errors import ApiError

UNIMPLEMENTED_OPERATIONS: dict[str, tuple[str, str]] = {
    "startRun": ("post", "/v1/workspaces/{workspace_id}/projects/{project_id}/runs"),
    "getRun": ("get", "/v1/workspaces/{workspace_id}/runs/{run_id}"),
    "getRunEvents": ("get", "/v1/workspaces/{workspace_id}/runs/{run_id}/events"),
    "cancelRun": ("post", "/v1/workspaces/{workspace_id}/runs/{run_id}/cancel"),
    "retryRun": ("post", "/v1/workspaces/{workspace_id}/runs/{run_id}/retry"),
    "quoteLookup": ("post", "/v1/workspaces/{workspace_id}/projects/{project_id}/enrichment-quotes"),
    "confirmLookup": ("post", "/v1/workspaces/{workspace_id}/enrichment-quotes/{quote_id}/confirm"),
    "getEnrichmentJob": ("get", "/v1/workspaces/{workspace_id}/enrichment-jobs/{job_id}"),
    "cancelEnrichmentJob": ("post", "/v1/workspaces/{workspace_id}/enrichment-jobs/{job_id}/cancel"),
    "generateDraft": ("post", "/v1/workspaces/{workspace_id}/projects/{project_id}/drafts"),
    "editDraft": ("patch", "/v1/workspaces/{workspace_id}/drafts/{draft_id}"),
    "requestDraftReview": ("post", "/v1/workspaces/{workspace_id}/drafts/{draft_id}/review"),
    "approveDraft": ("post", "/v1/workspaces/{workspace_id}/drafts/{draft_id}/approvals"),
    "exportBuyers": ("post", "/v1/workspaces/{workspace_id}/projects/{project_id}/exports"),
    "downloadExport": ("get", "/v1/workspaces/{workspace_id}/exports/{export_id}/content"),
    "exportDraft": ("post", "/v1/workspaces/{workspace_id}/drafts/{draft_id}/exports"),
    "recordOutcome": ("post", "/v1/workspaces/{workspace_id}/projects/{project_id}/outcomes"),
    "correctOutcome": ("post", "/v1/workspaces/{workspace_id}/outcomes/{outcome_id}/corrections"),
    "getUsage": ("get", "/v1/workspaces/{workspace_id}/projects/{project_id}/usage"),
    "listBudgets": ("get", "/v1/workspaces/{workspace_id}/budgets"),
    "uploadOfferDocument": ("post", "/v1/workspaces/{workspace_id}/projects/{project_id}/offer-documents"),
    "ingestOfferUrl": ("post", "/v1/workspaces/{workspace_id}/projects/{project_id}/offer-ingestions"),
}

router = APIRouter(tags=["unimplemented"])


def _register(operation_id: str, method: str, path: str) -> None:
    async def handler(request: Request, principal: Principal = Depends(get_principal)) -> dict:
        raise ApiError(501, "NOT_IMPLEMENTED", f"{operation_id} is not implemented in this phase")

    handler.__name__ = f"not_implemented_{operation_id}"
    router.add_api_route(path, handler, methods=[method.upper()], name=operation_id)


for _operation_id, (_method, _path) in UNIMPLEMENTED_OPERATIONS.items():
    _register(_operation_id, _method, _path)
