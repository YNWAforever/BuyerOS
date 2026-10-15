"""Release-only probe; this token grants no tenant read/write capability."""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ...services.release_binding import probe_authorized, read_runtime_binding, runtime_identity
from ...settings import get_settings
from ..errors import ApiError, error_body

router = APIRouter(tags=['internal-release'])


async def read_binding() -> dict:
    from ..deps import get_engine
    source, deployment = runtime_identity(get_settings())
    return await read_runtime_binding(get_engine(), source, deployment)


@router.get('/v1/internal/release-binding', include_in_schema=False)
async def release_binding(request: Request):
    try:
        settings = get_settings()
        values = request.headers.getlist('authorization')
        supplied = values[0][7:] if len(values) == 1 and values[0].startswith('Bearer ') else ''
        expected = settings.release_probe_token.get_secret_value() if settings.release_probe_token else ''
        if not probe_authorized(supplied, expected):
            raise ApiError(401, 'UNAUTHENTICATED', 'invalid release probe credential')
        runtime_identity(settings)
        payload = await read_binding()
        return JSONResponse(payload, headers={'Cache-Control': 'no-store'})
    except ApiError as error:
        return JSONResponse(error_body(request, code=error.code, message=error.message),
                            status_code=error.status_code, headers={'Cache-Control': 'no-store'})
    except Exception:
        return JSONResponse(error_body(request, code='RELEASE_BINDING_UNAVAILABLE', message='release binding unavailable'),
                            status_code=503, headers={'Cache-Control': 'no-store'})
