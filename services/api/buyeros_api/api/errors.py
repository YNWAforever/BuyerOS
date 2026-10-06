import json
import logging
import math
import os
import re
import uuid

from sqlalchemy.exc import DBAPIError, TimeoutError as PoolTimeout

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


def database_error_diagnostics(request: Request, exc: Exception) -> dict:
    """Allowlisted metadata only: never stringify errors, DSNs, binds or traces.

    Timings/schema/role are null unless supplied by a trusted backend component.
    They are observations, not inferred from a successful retry or an error name.
    """
    raw_id = getattr(request.state, "request_id", None)
    try:
        request_id = str(uuid.UUID(raw_id)) if isinstance(raw_id, str) else None
    except ValueError:
        request_id = None
    original = exc.orig if isinstance(exc, DBAPIError) else None
    raw_state = getattr(original, "sqlstate", None)
    sqlstate = raw_state if isinstance(raw_state, str) and re.fullmatch(r"[0-9A-Z]{5}", raw_state) else None
    classification = {
        "42P01": "missing_relation", "42501": "insufficient_privilege",
        "08001": "connection_failure", "08003": "connection_failure",
        "08006": "connection_failure", "57P01": "connection_failure",
    }.get(sqlstate, "unconfirmed")
    if isinstance(exc, PoolTimeout):
        classification = "pool_timeout"
    names = {"OperationalError", "ProgrammingError", "InterfaceError", "DBAPIError", "TimeoutError", "IntegrityError"}
    error_class = type(exc).__name__ if type(exc).__name__ in names else "UnexpectedError"
    context = getattr(request.state, "database_diagnostics", None)
    context = context if isinstance(context, dict) else {}
    wait = context.get("pool_wait_ms")
    try:
        wait = wait if type(wait) in (int, float) and math.isfinite(wait) and wait >= 0 else None
    except OverflowError:
        wait = None
    timeout = context.get("connection_timeout")
    timeout = timeout if type(timeout) is bool else None
    if timeout is True and isinstance(exc, TimeoutError):
        classification = "connection_timeout"
    schema = context.get("schema_head")
    schema = schema if isinstance(schema, str) and re.fullmatch(r"[0-9]{4}_[a-z_]+", schema) else None
    role = context.get("runtime_role")
    role = role if role in ("buyeros_api", "buyeros_worker") else None
    sha = os.environ.get("BUYEROS_SOURCE_SHA", os.environ.get("VERCEL_GIT_COMMIT_SHA"))
    sha = sha if isinstance(sha, str) and re.fullmatch(r"[0-9a-f]{40}", sha) else None
    return {"request_id": request_id, "error_class": error_class, "sqlstate": sqlstate,
            "classification": classification, "pool_wait_ms": wait, "connection_timeout": timeout,
            "schema_head": schema, "runtime_role": role, "source_sha": sha}


async def internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Unexpected failures retain the public envelope without disclosing internals."""
    diagnostic = database_error_diagnostics(request, exc)
    logging.getLogger(__name__).error(
        "unexpected_api_error request_id=%s type=%s diagnostics=%s",
        diagnostic["request_id"], diagnostic["error_class"],
        json.dumps(diagnostic, sort_keys=True, separators=(",", ":")),
        extra={"diagnostic": diagnostic},
    )
    return JSONResponse(
        status_code=500,
        content=error_body(request, code="INTERNAL_ERROR", message="request failed", retryable=True),
    )
