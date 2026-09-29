"""Pinned-network policy for permitted, bounded document fetches (BO-012).

The fetch boundary accepts only a transport that pins the validated DNS answer
to its connection. Production transport and private storage are wired only after explicit configuration.
"""
from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import re
import zlib
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urlunsplit

MAX_DECODED_BYTES = 2_097_152
MAX_REDIRECTS = 3
MAX_TRANSFER_BYTES = 2_097_152
ALLOWED_MIME = frozenset({"text/html", "text/plain", "text/markdown", "application/xhtml+xml"})


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
    display_host = f"[{host}]" if ":" in host else host
    netloc = display_host if port in (None, default_port) else f"{display_host}:{port}"
    return urlunsplit((scheme, netloc, parts.path or "/", parts.query, ""))


def _safe_https_url(url: str) -> tuple[str, str] | None:
    if any(ord(char) < 32 or ord(char) == 127 for char in url):
        return None
    try:
        parts = urlsplit(url)
        if (parts.scheme.lower() != "https" or not parts.hostname
                or parts.username is not None or parts.password is not None
                or parts.port not in (None, 443)):
            return None
        host = parts.hostname.lower()
        try:
            literal = ipaddress.ip_address(host)
        except ValueError:
            literal = None
        if literal is not None and is_blocked_host(host):
            return None
    except ValueError:
        return None
    # Hostnames are resolved and checked at every hop. IP literals have
    # already passed the global-address check above.
    return normalize_url(url), host


def _decode_body(raw: bytes, encoding: str) -> bytes:
    if len(raw) > MAX_TRANSFER_BYTES:
        raise ValueError("transfer_limit")
    if not encoding or encoding == "identity":
        decoded = raw
    elif encoding in {"gzip", "deflate"}:
        decoder = zlib.decompressobj(16 + zlib.MAX_WBITS if encoding == "gzip" else zlib.MAX_WBITS)
        decoded = decoder.decompress(raw, MAX_DECODED_BYTES + 1)
        if not decoder.eof:
            raise ValueError("incomplete_or_oversize_body")
        decoded += decoder.flush(MAX_DECODED_BYTES + 1 - len(decoded))
    else:
        raise ValueError("unsupported_encoding")
    if len(decoded) > MAX_DECODED_BYTES:
        raise ValueError("decoded_limit")
    return decoded


class _PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hidden = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style", "noscript", "svg", "form"}:
            self.hidden += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg", "form"} and self.hidden:
            self.hidden -= 1

    def handle_data(self, data: str) -> None:
        if not self.hidden:
            self.parts.append(data)


def _sanitized_text(body: bytes, mime: str) -> bytes:
    text = body.decode("utf-8", errors="replace")
    if mime in {"text/html", "application/xhtml+xml"}:
        parser = _PlainText()
        parser.feed(text)
        text = " ".join(parser.parts)
    return " ".join(text.split()).encode("utf-8")[:MAX_DECODED_BYTES]


async def fetch_permitted_document(intent: dict, transport, object_store) -> dict:
    """Return honest retrieval status; never treat URL validation as success.

    A transport must perform each GET on the provided pinned IP, preserve the
    original HTTPS Host/SNI, and honor its byte and timeout limits. The current
    worker supplies the direct pinned transport only for an approved source.
    """
    if (not isinstance(intent, dict) or intent.get("permitted") is not True
            or not isinstance(intent.get("retention_seconds"), int)
            or isinstance(intent.get("retention_seconds"), bool)
            or not 0 < intent["retention_seconds"] <= 86400 * 30
            or transport is None or object_store is None
            or getattr(transport, "pinned_connections", False) is not True):
        return {"status": "blocked", "reason": "permission_or_transport_unavailable"}
    url = intent.get("url")
    if not isinstance(url, str) or len(url) > 2000:
        return {"status": "blocked", "reason": "invalid_url"}
    permitted_host = None
    try:
        async with asyncio.timeout(10):
            for hop in range(MAX_REDIRECTS + 1):
                checked = _safe_https_url(url)
                if checked is None:
                    return {"status": "blocked", "reason": "unsafe_target"}
                normalized, host = checked
                if permitted_host is None:
                    permitted_host = host
                elif host != permitted_host:
                    return {"status": "blocked", "reason": "redirect_source_not_permitted"}
                addresses = await transport.resolve(host)
                if not addresses or any(is_blocked_host(ip) for ip in addresses):
                    return {"status": "blocked", "reason": "unsafe_dns_answer"}
                status, headers, raw = await transport.get(
                    normalized, pinned_ip=addresses[0], timeout_seconds=10,
                    max_transfer_bytes=MAX_TRANSFER_BYTES,
                )
                if not isinstance(headers, dict) or not isinstance(raw, bytes):
                    return {"status": "quarantined", "reason": "invalid_response"}
                headers = {str(k).lower(): str(v) for k, v in headers.items()}
                if status in {301, 302, 303, 307, 308}:
                    if hop == MAX_REDIRECTS or not headers.get("location"):
                        return {"status": "blocked", "reason": "redirect_limit"}
                    url = urljoin(normalized, headers["location"])
                    continue
                if status != 200:
                    return {"status": "blocked", "reason": "http_status"}
                mime = headers.get("content-type", "").split(";", 1)[0].strip().lower()
                if mime not in ALLOWED_MIME:
                    return {"status": "quarantined", "reason": "unsupported_mime"}
                try:
                    decoded = _decode_body(raw, headers.get("content-encoding", "").lower().strip())
                except (ValueError, zlib.error):
                    return {"status": "quarantined", "reason": "body_limit_or_encoding"}
                sanitized = _sanitized_text(decoded, mime)
                if not sanitized:
                    return {"status": "quarantined", "reason": "empty_sanitized_content"}
                source_digest = hashlib.sha256(decoded).hexdigest()
                language_header = headers.get("content-language", "").split(",", 1)[0].strip()
                language = (language_header if re.fullmatch(r"[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8}){0,3}", language_header) else "und")
                digest = hashlib.sha256(sanitized).hexdigest()
                key = await object_store.put_private(
                    sanitized, digest=digest, retention_seconds=intent["retention_seconds"]
                )
                if not isinstance(key, str) or not key:
                    return {"status": "quarantined", "reason": "storage_failure"}
                return {
                    "status": "retrieved", "source_url": normalized, "digest": digest,
                    "source_digest": source_digest, "language": language,
                    "bytes": len(decoded), "object_key": key, "excerpt": sanitized[:4000].decode(),
                }
    except (TimeoutError, OSError, ValueError, zlib.error):
        return {"status": "blocked", "reason": "retrieval_failed"}
    return {"status": "blocked", "reason": "redirect_limit"}
