"""Restore domain write preconditions after the hosting HTTP transport boundary."""
from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from .errors import ApiError, error_handler
from .idempotency import if_match_version


class WritePreconditionMiddleware:
    """Keep post-write ETags from being interpreted as HTTP request conditions.

    The application carrier has exactly the same strong-version syntax and is
    converted before route authorization, row locks, and idempotency hashing.
    Standard If-Match remains available to direct API clients.
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (scope["type"] == "http" and scope["method"] in {"POST", "PUT", "PATCH", "DELETE"}
                and scope["path"].startswith("/v1/")):
            headers = scope["headers"]
            carriers = [value for name, value in headers if name.lower() == b"x-buyeros-if-match"]
            if carriers:
                try:
                    if len(carriers) != 1 or any(name.lower() == b"if-match" for name, _ in headers):
                        raise ApiError(400, "INVALID_REQUEST", "provide one write precondition header")
                    if_match_version(carriers[0].decode("latin-1"))
                except ApiError as error:
                    response = await error_handler(Request(scope), error)
                    await response(scope, receive, send)
                    return
                scope = {**scope, "headers": [
                    (name, value) for name, value in headers if name.lower() != b"x-buyeros-if-match"
                ] + [(b"if-match", carriers[0])]}
        await self.app(scope, receive, send)
