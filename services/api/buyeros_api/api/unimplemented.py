"""Explicit 501 handlers for contract operations outside the implemented slice.

Handlers are registered on the operations' **declared** contract path+method, so
no parallel or invented endpoint exists. The registry covers every contract
operation not yet implemented (verified against the spec by
``tests/test_api_buyers.py``). Each still requires a principal, so the surface
fails closed (401) when auth is unconfigured, then returns 501 once
authenticated.
"""

from fastapi import APIRouter, Depends, Request

from .auth import Principal, get_principal
from .errors import ApiError

UNIMPLEMENTED_OPERATIONS: dict[str, tuple[str, str]] = {
}

router = APIRouter(tags=["unimplemented"])


def _register(operation_id: str, method: str, path: str) -> None:
    async def handler(request: Request, principal: Principal = Depends(get_principal)) -> dict:
        raise ApiError(501, "NOT_IMPLEMENTED", f"{operation_id} is not implemented in this phase")

    handler.__name__ = f"not_implemented_{operation_id}"
    router.add_api_route(path, handler, methods=[method.upper()], name=operation_id)


for _operation_id, (_method, _path) in UNIMPLEMENTED_OPERATIONS.items():
    _register(_operation_id, _method, _path)