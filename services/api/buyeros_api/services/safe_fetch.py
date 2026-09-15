"""SSRF-safe host/URL policy for permitted web fetch (BO-012)."""

import ipaddress
from urllib.parse import urlsplit, urlunsplit


def is_blocked_host(ip: str) -> bool:
    addr = ipaddress.ip_address(ip)
    return (
        not addr.is_global
        or addr.is_multicast
        or addr.is_unspecified
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_private
    )


def normalize_url(url: str) -> str:
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower()
    port = parts.port
    default_port = 80 if scheme == "http" else 443
    netloc = host if port in (None, default_port) else f"{host}:{port}"
    return urlunsplit((scheme, netloc, parts.path or "/", parts.query, ""))
