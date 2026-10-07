import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from starlette.middleware.cors import CORSMiddleware

from .errors import ApiError, error_body, error_handler, http_error_handler, internal_error_handler, validation_error_handler
from .routes.audit import router as audit_router
from .routes.buyers import router as buyers_router
from .routes.budgets import router as budgets_router
from .routes.buyer_management import router as buyer_management_router
from .routes.bulk_manifests import router as bulk_manifests_router
from .routes.documents import router as documents_router
from .routes.drafts import router as drafts_router
from .routes.exports import router as exports_router
from .routes.enrichment import router as enrichment_router
from .routes.health import router as health_router
from .routes.icp import router as icp_router
from .routes.jobs import router as jobs_router
from .routes.work_queue import router as work_queue_router
from .routes.memberships import router as memberships_router
from .routes.outcomes import router as outcomes_router
from .routes.projects import router as projects_router
from .routes.policy import router as policy_router
from .routes.provider_callbacks import router as provider_callbacks_router
from .routes.reviews import router as reviews_router
from .routes.quotes import detail_router as quote_detail_router, router as quotes_router
from .routes.runs import detail_router as run_detail_router, router as runs_router
from .routes.settings import router as settings_router
from .routes.workspaces import router as workspaces_router
from .routes.usage import router as usage_router
from .routes.worker_internal import router as worker_internal_router
from .unimplemented import router as unimplemented_router
from buyeros_api.settings import get_settings


@asynccontextmanager
async def _lifespan(app: FastAPI):
    try:
        yield
    finally:
        from .deps import dispose_engines

        await dispose_engines()


def create_app() -> FastAPI:
    app = FastAPI(title="FIMMICK BuyerOS domain API", version="0.1.0", lifespan=_lifespan)
    app.add_exception_handler(ApiError, error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(HTTPException, http_error_handler)
    app.add_exception_handler(Exception, internal_error_handler)
    app.include_router(health_router)
    app.include_router(settings_router)
    app.include_router(memberships_router)
    app.include_router(audit_router)
    app.include_router(workspaces_router)
    app.include_router(projects_router)
    app.include_router(budgets_router)
    app.include_router(icp_router)
    app.include_router(buyers_router)
    app.include_router(buyer_management_router)
    app.include_router(bulk_manifests_router)
    app.include_router(documents_router)
    app.include_router(drafts_router)
    app.include_router(exports_router)
    app.include_router(outcomes_router)
    app.include_router(usage_router)
    app.include_router(enrichment_router)
    app.include_router(policy_router)
    app.include_router(provider_callbacks_router)
    app.include_router(jobs_router)
    app.include_router(work_queue_router)
    app.include_router(reviews_router)
    app.include_router(runs_router)
    app.include_router(run_detail_router)
    app.include_router(quotes_router)
    app.include_router(quote_detail_router)
    app.include_router(unimplemented_router)
    app.include_router(worker_internal_router)

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        from ..services.audit_service import request_correlation

        supplied = request.headers.get("X-Request-ID")
        try:
            request.state.request_id = str(uuid.UUID(supplied)) if supplied else str(uuid.uuid4())
        except ValueError:
            request.state.request_id = str(uuid.uuid4())
        from ..services.api_rate_limit import classify_request, request_rate_bucket
        marker = request_correlation.set(request.state.request_id)
        bucket_marker = request_rate_bucket.set(classify_request(request.method, request.url.path))
        try:
            if (request.method == "GET" and request.url.path.startswith("/v1/")
                    and not get_settings().live_read_enabled):
                response = JSONResponse(
                    status_code=503,
                    content=error_body(request, code="READ_DISABLED",
                                       message="live reads are temporarily disabled",
                                       retryable=True),
                )
            else:
                response = await call_next(request)
        finally:
            request_rate_bucket.reset(bucket_marker)
            request_correlation.reset(marker)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origins,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "If-Match", "X-Request-ID", "Last-Event-ID"],
        expose_headers=["X-Request-ID", "ETag"],
        allow_credentials=False,
        max_age=600,
    )
    return app


app = create_app()
