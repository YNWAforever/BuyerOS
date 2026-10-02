"""Resource-capped PDF parser process. No application configuration is imported."""
from __future__ import annotations

import io
import json
import os
import socket
import sys

MAX_INPUT = 5 * 1024 * 1024
MAX_PAGES = 20
MAX_PAGE_CONTENT = 2 * 1024 * 1024
MAX_TOTAL_CONTENT = 4 * 1024 * 1024
MAX_TEXT = 100_000


def _deny_network(*_args, **_kwargs):
    raise RuntimeError("network disabled in PDF parser")


def main() -> int:
    # Native Linux execution keeps hostile decompression inside a memory/CPU cap;
    # the parent also kills the process after a wall-clock deadline.
    if os.name == "posix":
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024,) * 2)
        resource.setrlimit(resource.RLIMIT_CPU, (6, 6))
        resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024,) * 2)
    socket.socket = _deny_network
    socket.create_connection = _deny_network
    body = sys.stdin.buffer.read(MAX_INPUT + 1)
    if not body.startswith(b"%PDF-") or len(body) > MAX_INPUT:
        return 2
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(body), strict=True,
                           root_object_recovery_limit=1000)
        if reader.is_encrypted or not 1 <= len(reader.pages) <= MAX_PAGES:
            return 2
        extracted = []
        content_size = 0
        text_size = 0
        for page in reader.pages:
            content = page.get_contents()
            if content is not None:
                size = len(content.get_data())
                content_size += size
                if size > MAX_PAGE_CONTENT or content_size > MAX_TOTAL_CONTENT:
                    return 2
            text = page.extract_text() or ""
            text_size += len(text.encode("utf-8"))
            if text_size > MAX_TEXT:
                return 2
            extracted.append(text)
        output = json.dumps({"text": "\n".join(extracted)}, ensure_ascii=False).encode("utf-8")
        if len(output) > 128 * 1024:
            return 2
        sys.stdout.buffer.write(output)
        return 0
    except Exception:
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
