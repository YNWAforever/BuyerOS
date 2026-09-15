"""Explicit 501 handlers for contract operations outside the P9 slice.

Handlers are registered on the operations' **declared** contract path+method, so
no parallel or invented endpoint exists. The registry covers every contract
operation P9 does not implement (verified against the spec by
``tests/test_api_buyers.py``). Each still requires a principal, so the surface
fails closed (401) when auth is unconfigured, then returns 501 once
authenticated.
"""

from fastapi import APIRouter, Depends, Request

from .auth import Principal, get_principal
from .errors import ApiError

UNIMPLEMENTED_OPERATIONS: dict[str, tuple[str, str]] = {
    "approveDraft": ("post", "/v1/workspaces/{workspace_id}/drafts/{draft_id}/approvals"),
    "archiveProject": ("delete", "/v1/workspaces/{workspace_id}/projects/{project_id}"),
    "cancelEnrichmentJob": ("post", "/v1/workspaces/{workspace_id}/enrichment-jobs/{job_id}/cancel"),
    "cancelLookupQuote": ("post", "/v1/workspaces/{workspace_id}/enrichment-quotes/{quote_id}/cancel"),
    "cancelRun": ("post", "/v1/workspaces/{workspace_id}/runs/{run_id}/cancel"),
    "changeListMemberships": ("post", "/v1/workspaces/{workspace_id}/lists/{list_id}/memberships"),
    "confirmLookup": ("post", "/v1/workspaces/{workspace_id}/enrichment-quotes/{quote_id}/confirm"),
    "correctOutcome": ("post", "/v1/workspaces/{workspace_id}/outcomes/{outcome_id}/corrections"),
    "createBuyerList": ("post", "/v1/workspaces/{workspace_id}/projects/{project_id}/lists"),
    "createBuyerSnapshot": ("post", "/v1/workspaces/{workspace_id}/projects/{project_id}/buyer-snapshots"),
    "createSuppression": ("post", "/v1/workspaces/{workspace_id}/suppressions"),
    "deleteOfferDocument": ("delete", "/v1/workspaces/{workspace_id}/offer-documents/{document_id}"),
    "disabledDeliveryBoundary": ("post", "/v1/workspaces/{workspace_id}/drafts/{draft_id}/deliver"),
    "downloadExport": ("get", "/v1/workspaces/{workspace_id}/exports/{export_id}/content"),
    "editDraft": ("patch", "/v1/workspaces/{workspace_id}/drafts/{draft_id}"),
    "exportBuyers": ("post", "/v1/workspaces/{workspace_id}/projects/{project_id}/exports"),
    "exportDraft": ("post", "/v1/workspaces/{workspace_id}/drafts/{draft_id}/exports"),
    "generateDraft": ("post", "/v1/workspaces/{workspace_id}/projects/{project_id}/drafts"),
    "getAsyncJob": ("get", "/v1/workspaces/{workspace_id}/jobs/{job_id}"),
    "getBuyerList": ("get", "/v1/workspaces/{workspace_id}/lists/{list_id}"),
    "getDraft": ("get", "/v1/workspaces/{workspace_id}/drafts/{draft_id}"),
    "getEnrichmentJob": ("get", "/v1/workspaces/{workspace_id}/enrichment-jobs/{job_id}"),
    "getEvidence": ("get", "/v1/workspaces/{workspace_id}/evidence/{evidence_id}"),
    "getExport": ("get", "/v1/workspaces/{workspace_id}/exports/{export_id}"),
    "getLookupQuote": ("get", "/v1/workspaces/{workspace_id}/enrichment-quotes/{quote_id}"),
    "getOfferDocument": ("get", "/v1/workspaces/{workspace_id}/offer-documents/{document_id}"),
    "getPreferences": ("get", "/v1/workspaces/{workspace_id}/preferences"),
    "getRun": ("get", "/v1/workspaces/{workspace_id}/runs/{run_id}"),
    "getRunEvents": ("get", "/v1/workspaces/{workspace_id}/runs/{run_id}/events"),
    "getUsage": ("get", "/v1/workspaces/{workspace_id}/projects/{project_id}/usage"),
    "ingestOfferUrl": ("post", "/v1/workspaces/{workspace_id}/projects/{project_id}/offer-ingestions"),
    "listAuditEvents": ("get", "/v1/workspaces/{workspace_id}/audit-events"),
    "listBudgets": ("get", "/v1/workspaces/{workspace_id}/budgets"),
    "listBuyerEvidence": ("get", "/v1/workspaces/{workspace_id}/buyers/{buyer_id}/evidence"),
    "listBuyerLists": ("get", "/v1/workspaces/{workspace_id}/projects/{project_id}/lists"),
    "listDrafts": ("get", "/v1/workspaces/{workspace_id}/projects/{project_id}/drafts"),
    "listFilterPresets": ("get", "/v1/workspaces/{workspace_id}/projects/{project_id}/filter-presets"),
    "listOutcomes": ("get", "/v1/workspaces/{workspace_id}/projects/{project_id}/outcomes"),
    "listPolicyDecisions": ("get", "/v1/workspaces/{workspace_id}/policy-decisions"),
    "listRuns": ("get", "/v1/workspaces/{workspace_id}/projects/{project_id}/runs"),
    "listSuppressions": ("get", "/v1/workspaces/{workspace_id}/suppressions"),
    "quoteLookup": ("post", "/v1/workspaces/{workspace_id}/projects/{project_id}/enrichment-quotes"),
    "receiveProviderCallback": ("post", "/v1/provider-callbacks/{provider}"),
    "reconcileEnrichmentJob": ("post", "/v1/workspaces/{workspace_id}/enrichment-jobs/{job_id}/reconcile"),
    "recordOutcome": ("post", "/v1/workspaces/{workspace_id}/projects/{project_id}/outcomes"),
    "recordPolicyDecision": ("post", "/v1/workspaces/{workspace_id}/policy-decisions"),
    "removeSuppression": ("post", "/v1/workspaces/{workspace_id}/suppressions/{suppression_id}/remove"),
    "renameBuyerList": ("patch", "/v1/workspaces/{workspace_id}/lists/{list_id}"),
    "requestDraftReview": ("post", "/v1/workspaces/{workspace_id}/drafts/{draft_id}/review"),
    "retryRun": ("post", "/v1/workspaces/{workspace_id}/runs/{run_id}/retry"),
    "reviewBuyers": ("post", "/v1/workspaces/{workspace_id}/projects/{project_id}/buyer-reviews"),
    "saveFilterPreset": ("post", "/v1/workspaces/{workspace_id}/projects/{project_id}/filter-presets"),
    "startRun": ("post", "/v1/workspaces/{workspace_id}/projects/{project_id}/runs"),
    "updateBudget": ("patch", "/v1/workspaces/{workspace_id}/budgets/{budget_id}"),
    "updateBuyer": ("patch", "/v1/workspaces/{workspace_id}/buyers/{buyer_id}"),
    "updatePreferences": ("patch", "/v1/workspaces/{workspace_id}/preferences"),
    "updateProject": ("patch", "/v1/workspaces/{workspace_id}/projects/{project_id}"),
    "uploadOfferDocument": ("post", "/v1/workspaces/{workspace_id}/projects/{project_id}/offer-documents"),
}

router = APIRouter(tags=["unimplemented"])


def _register(operation_id: str, method: str, path: str) -> None:
    async def handler(request: Request, principal: Principal = Depends(get_principal)) -> dict:
        raise ApiError(501, "NOT_IMPLEMENTED", f"{operation_id} is not implemented in this phase")

    handler.__name__ = f"not_implemented_{operation_id}"
    router.add_api_route(path, handler, methods=[method.upper()], name=operation_id)


for _operation_id, (_method, _path) in UNIMPLEMENTED_OPERATIONS.items():
    _register(_operation_id, _method, _path)