"""Conservative, deterministic company identity hints (T17).

A host is never sufficient to merge legal entities. Only the same nonempty,
normalized registry identifier permits an automatic tenant-local merge.
"""
from __future__ import annotations

from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

_TRACKING = {"gclid", "fbclid", "msclkid", "mc_cid", "mc_eid"}


def _host(url_or_host: str) -> str:
    if not isinstance(url_or_host, str) or not url_or_host or len(url_or_host) > 2000:
        raise ValueError("invalid host")
    parsed = urlsplit(url_or_host if "://" in url_or_host else "//" + url_or_host)
    if parsed.username or parsed.password or not parsed.hostname:
        raise ValueError("invalid host")
    try:
        host = parsed.hostname.rstrip(".").encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise ValueError("invalid IDNA host") from exc
    if not host or len(host) > 255 or ".." in host:
        raise ValueError("invalid host")
    return host


def registrable_hint(url_or_host: str) -> str:
    """Stable host hint, not an eTLD+1 claim or an identity decision."""
    host = _host(url_or_host)
    return host[4:] if host.startswith("www.") else host


def canonical_key(url: str) -> str:
    return registrable_hint(url)


def normalize_source_url(url: str) -> str:
    if not isinstance(url, str) or len(url) > 2000:
        raise ValueError("invalid source URL")
    parsed = urlsplit(url)
    if parsed.scheme.lower() != "https" or parsed.username or parsed.password:
        raise ValueError("HTTPS source URL required")
    host = _host(url)
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("invalid source port") from exc
    if port not in (None, 443):
        raise ValueError("unsupported source port")
    query = sorted((name, value) for name, value in parse_qsl(parsed.query, keep_blank_values=True)
                   if not name.lower().startswith("utm_") and name.lower() not in _TRACKING)
    path = quote(parsed.path or "/", safe="/%:@!$&'()*+,;=-._~")
    normalized = urlunsplit(("https", host, path, urlencode(query), ""))
    if len(normalized) > 2000:
        raise ValueError("source URL too long")
    return normalized


def normalized_registry_id(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("invalid registry ID")
    normalized = " ".join(value.strip().upper().split())
    if not normalized or len(normalized) > 128:
        raise ValueError("invalid registry ID")
    return normalized


def is_auto_merge_allowed(a: dict, b: dict) -> bool:
    left = normalized_registry_id(a.get("registry_id"))
    right = normalized_registry_id(b.get("registry_id"))
    return left is not None and left == right
