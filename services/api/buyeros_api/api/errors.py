import logging

from fastapi import Request
from fastapi.responses import JSONResponse


class ApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str, retryable: bool = False):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.retryable = retryable


def envelope(data, request_id: str) -> dict:
    return {"data": data, "request_id": request_id, "data_mode": "live"}


def error_body(request: Request, *, code: str, message: str, retryable: bool = False) -> dict:
    return {
        "code": code,
        "message": message,
        "request_id": getattr(request.state, "request_id", ""),
        "retryable": retryable,
    }


async def error_handler(request: Request, exc: ApiError) -> JSONResponse:
    response = JSONResponse(
        status_code=exc.status_code,
        content=error_body(request, code=exc.code, message=exc.message, retryable=exc.retryable),
    )
    if exc.code == "RATE_LIMITED":
        response.headers["Retry-After"] = "60"
    return response


async def validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Every non-2xx must use the contract envelope, not FastAPI's default `detail` shape."""
    return JSONResponse(
        status_code=422,
        content=error_body(request, code="INVALID_REQUEST", message="request validation failed"),
    )


async def http_error_handler(request: Request, exc: Exception) -> JSONResponse:
    from starlette.exceptions import HTTPException

    status_code = exc.status_code if isinstance(exc, HTTPException) else 500
    code = {404: "NOT_FOUND", 405: "NOT_FOUND", 400: "INVALID_REQUEST", 429: "RATE_LIMITED"}.get(
        status_code, "INTERNAL_ERROR" if status_code >= 500 else "INVALID_REQUEST"
    )
    return JSONResponse(status_code=status_code, content=error_body(request, code=code, message="request failed"))


async def internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Unexpected failures retain the public envelope without disclosing internals."""
    logging.getLogger(__name__).error(
        "unexpected_api_error request_id=%s type=%s",
        getattr(request.state, "request_id", ""), type(exc).__name__,
    )
    return JSONResponse(
        status_code=500,
        content=error_body(request, code="INTERNAL_ERROR", message="request failed", retryable=True),
    )
