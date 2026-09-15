import uuid

from fastapi import FastAPI, Request

from .errors import ApiError, error_handler


def create_app() -> FastAPI:
    app = FastAPI(title="FIMMICK BuyerOS domain API", version="0.1.0")
    app.add_exception_handler(ApiError, error_handler)

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request.state.request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    return app


app = create_app()
