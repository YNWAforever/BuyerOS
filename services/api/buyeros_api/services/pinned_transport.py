"""Direct HTTPS transport that connects only to a validated pinned IP.

This transport has no proxy, cookie jar, redirect following, or credentials.
The caller resolves and validates every address before passing pinned_ip.
"""
from __future__ import annotations

import asyncio
import ipaddress
import socket
import ssl
from urllib.parse import urlsplit


class PinnedHttpsTransport:
    pinned_connections = True

    async def resolve(self, host: str) -> list[str]:
        loop = asyncio.get_running_loop()
        answers = await loop.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        return list(dict.fromkeys(answer[4][0] for answer in answers))

    async def get(self, url: str, *, pinned_ip: str, timeout_seconds: float,
                  max_transfer_bytes: int) -> tuple[int, dict[str, str], bytes]:
        parts = urlsplit(url)
        if parts.scheme != "https" or not parts.hostname or parts.port not in (None, 443):
            raise ValueError("transport requires HTTPS on port 443")
        pinned = ipaddress.ip_address(pinned_ip)
        if not pinned.is_global:
            raise ValueError("transport requires a public pinned IP")
        host = parts.hostname
        path = parts.path or "/"
        if parts.query:
            path += "?" + parts.query
        if any(c in path for c in "\r\n"):
            raise ValueError("invalid request target")
        try:
            ascii_host = host.encode("idna").decode("ascii")
            path.encode("ascii")
        except UnicodeError as exc:
            raise ValueError("invalid ASCII request target") from exc
        host_header = f"[{ascii_host}]" if ":" in ascii_host else ascii_host
        reader = writer = None
        async with asyncio.timeout(timeout_seconds):
            try:
                reader, writer = await asyncio.open_connection(
                    host=pinned_ip, port=443, ssl=ssl.create_default_context(),
                    server_hostname=ascii_host,
                )
                writer.write((
                    f"GET {path} HTTP/1.1\r\nHost: {host_header}\r\n"
                    "Accept: text/html, text/plain, text/markdown\r\n"
                    "Accept-Encoding: gzip, deflate\r\nConnection: close\r\n\r\n"
                ).encode("ascii"))
                await writer.drain()
                head = await reader.readuntil(b"\r\n\r\n")
                if len(head) > 16_384:
                    raise ValueError("response headers too large")
                lines = head[:-4].split(b"\r\n")
                status_line = lines[0].decode("ascii", errors="strict").split(" ", 2)
                if len(status_line) < 2 or status_line[0] not in {"HTTP/1.1", "HTTP/1.0"}:
                    raise ValueError("invalid HTTP response")
                status = int(status_line[1])
                headers: dict[str, str] = {}
                for raw in lines[1:]:
                    name, separator, value = raw.partition(b":")
                    if not separator or not name or name.startswith(b" "):
                        raise ValueError("invalid response header")
                    key = name.decode("ascii", errors="strict").lower()
                    if key in headers:
                        raise ValueError("duplicate response header")
                    headers[key] = value.strip().decode("latin-1")
                if "transfer-encoding" in headers and "content-length" in headers:
                    raise ValueError("ambiguous response framing")
                if headers.get("transfer-encoding", "").lower() == "chunked":
                    body = await _read_chunked(reader, max_transfer_bytes)
                elif "transfer-encoding" in headers:
                    raise ValueError("unsupported transfer encoding")
                elif "content-length" in headers:
                    length = int(headers["content-length"])
                    if length < 0 or length > max_transfer_bytes:
                        raise ValueError("transfer limit")
                    body = await reader.readexactly(length)
                else:
                    chunks = bytearray()
                    while True:
                        chunk = await reader.read(min(65_536, max_transfer_bytes + 1 - len(chunks)))
                        if not chunk:
                            break
                        chunks.extend(chunk)
                        if len(chunks) > max_transfer_bytes:
                            raise ValueError("transfer limit")
                    body = bytes(chunks)
                return status, headers, body
            finally:
                if writer is not None:
                    writer.close()
                    await writer.wait_closed()


async def _read_chunked(reader: asyncio.StreamReader, limit: int) -> bytes:
    body = bytearray()
    while True:
        line = await reader.readline()
        if not line.endswith(b"\r\n") or len(line) > 128:
            raise ValueError("invalid chunk header")
        size = int(line[:-2].split(b";", 1)[0], 16)
        if size < 0 or size > limit - len(body):
            raise ValueError("transfer limit")
        if size == 0:
            trailer = await reader.readline()
            if trailer != b"\r\n":
                raise ValueError("trailers not supported")
            return bytes(body)
        body.extend(await reader.readexactly(size))
        if await reader.readexactly(2) != b"\r\n":
            raise ValueError("invalid chunk terminator")
