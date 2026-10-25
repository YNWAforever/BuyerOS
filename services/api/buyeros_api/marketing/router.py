import hmac
import json
from uuid import UUID

import psycopg
from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from .model import LeadInput
from .service import IntakeError, issue_challenge, submit_lead
from .settings import load_settings

router = APIRouter(prefix="/marketing/leads", tags=["marketing"])


def response(body, status=200):
    return JSONResponse(body, status_code=status, headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


def guard(request):
    settings = load_settings()
    if settings is None:
        raise IntakeError("intake_unavailable", 503, True)
    origins = request.headers.getlist("origin")
    keys = request.headers.getlist("x-marketing-gateway-key")
    if (origins != [settings.public_origin] or len(keys) != 1
        or not hmac.compare_digest(keys[0].encode(), settings.gateway_key.encode())):
        raise IntakeError("forbidden", 403)
    return settings


def error_response(error):
    return response({"code": error.code, "retryable": error.retryable}, error.status)


@router.get("/challenge")
async def challenge(request: Request):
    try:
        settings = guard(request)
        result = await run_in_threadpool(issue_challenge, settings)
        return response(result)
    except IntakeError as error:
        return error_response(error)
    except psycopg.Error:
        return error_response(IntakeError("intake_unavailable", 503, True))


@router.post("")
async def submit(request: Request):
    try:
        settings = guard(request)
        if request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/json":
            raise IntakeError("invalid_request", 422)
        supplied_length = request.headers.get("content-length")
        if supplied_length and (not supplied_length.isdigit() or int(supplied_length) > 8192):
            raise IntakeError("invalid_request", 422)
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 8192:
                raise IntakeError("invalid_request", 422)
        key = str(UUID(request.headers.get("idempotency-key", "")))
        lead = LeadInput.model_validate(json.loads(body))
        if settings.synthetic and not lead.email.rsplit("@", 1)[1].endswith(".test"):
            raise IntakeError("invalid_request", 422)
        result, created = await run_in_threadpool(submit_lead, settings, lead, key)
        return response(result, 201 if created else 200)
    except IntakeError as error:
        return error_response(error)
    except (ValueError, ValidationError, UnicodeDecodeError):
        return error_response(IntakeError("invalid_request", 422))
    except psycopg.Error:
        return error_response(IntakeError("intake_unavailable", 503, True))


def create_marketing_app() -> FastAPI:
    app = FastAPI(title="BuyerOS public demo intake", docs_url=None, redoc_url=None)
    app.include_router(router)
    return app
