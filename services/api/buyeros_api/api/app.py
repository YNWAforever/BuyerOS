import uuid

from fastapi import FastAPI, Request

from .errors import ApiError, error_handler
from .routes.buyers import router as buyers_router
from .routes.health import router as health_router
from .routes.icp import router as icp_router
from .routes.projects import router as projects_router
from .routes.workspaces import router as workspaces_router
from .unimplemented import router as unimplemented_router


def create_app() -> FastAPI:
    app = FastAPI(title="FIMMICK BuyerOS domain API", version="0.1.0")
    app.add_exception_handler(ApiError, error_handler)
    app.include_router(health_router)
    app.include_router(workspaces_router)
    app.include_router(projects_router)
    app.include_router(icp_router)
    app.include_router(buyers_router)
    app.include_router(unimplemented_router)

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request.state.request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    return app


app = create_app()
