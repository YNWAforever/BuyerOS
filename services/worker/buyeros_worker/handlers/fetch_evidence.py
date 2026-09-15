from urllib.parse import urlsplit

from buyeros_api.services.safe_fetch import is_blocked_host, normalize_url

from ..registry import HandlerResult, register

MAX_DECODED_BYTES = 2 * 1024 * 1024
ALLOWED_CONTENT_TYPES = frozenset({"text/html", "text/plain", "text/markdown", "application/xhtml+xml"})


class FetchRejected(Exception):
    pass


def _reject_if_blocked_host(host: str) -> None:
    try:
        blocked = is_blocked_host(host)
    except ValueError:
        return  # hostname; DNS/IP pinning happens at connection time
    if blocked:
        raise FetchRejected(f"blocked host {host}")


def validate_fetch(url: str, content_type: str, size: int) -> None:
    normalized = normalize_url(url)
    parsed = urlsplit(normalized)
    if parsed.scheme not in {"http", "https"}:
        raise FetchRejected(f"unsupported scheme {parsed.scheme}")
    _reject_if_blocked_host(parsed.hostname or "")
    if size > MAX_DECODED_BYTES:
        raise FetchRejected("decoded body exceeds 2 MiB")
    media_type = (content_type or "").split(";")[0].strip().lower()
    if media_type not in ALLOWED_CONTENT_TYPES:
        raise FetchRejected(f"content type {media_type} not allowed")


@register("fetch.evidence")
def handle(session, context, payload) -> HandlerResult:
    """Validate and (in the fetch client) retrieve permitted evidence.

    The live HTTP client is intentionally not wired here: it must run with
    DNS/IP pinning against the deployed egress policy. Validation is enforced
    now so an unsafe URL can never be dispatched.
    """
    try:
        validate_fetch(payload.get("url", ""), payload.get("content_type", ""), int(payload.get("size", 0)))
    except FetchRejected as exc:
        return HandlerResult(state="blocked", detail=str(exc))
    return HandlerResult(state="done", detail="validated; retrieval client is not enabled in this phase")
