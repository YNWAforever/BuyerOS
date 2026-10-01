"""Bounded subprocess boundary for untrusted PDF text extraction."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import replace

from buyeros_api.services.ingestion_service import ValidatedUpload, parse_candidate_facts

PARSER_TIMEOUT_SECONDS = 8
MAX_PARSER_OUTPUT_BYTES = 128 * 1024


class PdfParserTimeout(ValueError):
    pass


def parse_pdf_candidates(upload: ValidatedUpload) -> list[dict]:
    if upload.kind != "pdf" or upload.media_type != "application/pdf":
        raise ValueError("PDF upload required")
    # No object key, bearer token, cloud credential or inherited provider env is
    # passed to the parser. The child accepts only validated bytes on stdin.
    env = {"PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
    if sys.platform == "win32":
        env["SystemRoot"] = os.environ.get("SystemRoot", r"C:\Windows")
    with tempfile.TemporaryDirectory(prefix="buyeros-pdf-") as workdir:
        try:
            process = subprocess.run(
                [sys.executable, "-B", "-m", "buyeros_api.execution.pdf_parser_child"],
                input=upload.body, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=PARSER_TIMEOUT_SECONDS, check=False, cwd=workdir, env=env,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
        except subprocess.TimeoutExpired as exc:
            raise PdfParserTimeout("PDF parser timeout") from exc
    if process.returncode or len(process.stdout) > MAX_PARSER_OUTPUT_BYTES:
        raise ValueError("PDF parser rejected document")
    try:
        text = json.loads(process.stdout)["text"]
    except (ValueError, KeyError, TypeError) as exc:
        raise ValueError("PDF parser rejected document") from exc
    if not isinstance(text, str) or len(text.encode("utf-8")) > 100_000:
        raise ValueError("PDF extracted text too large")
    if re.search(r"<\s*[a-z][^>]*>", text, flags=re.IGNORECASE):
        raise ValueError("active HTML in PDF text")
    return parse_candidate_facts(replace(upload, kind="text", body=text.encode("utf-8")))
