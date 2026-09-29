"""Bounded, untrusted offer-upload validation and candidate extraction (T16).

The API may quarantine validated bytes; this module never approves facts or
executes embedded content. PDF extraction needs the isolated parser job.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
_ALLOWED = {
    ".pdf": ("application/pdf", "pdf"),
    ".txt": ("text/plain", "text"),
    ".md": ("text/markdown", "markdown"),
}
_PDF_ACTIVE = (b"/javascript", b"/openaction", b"/embeddedfile", b"/launch", b"/aa")
_FIELDS = {"product": "product", "value proposition": "value_proposition"}


@dataclass(frozen=True)
class ValidatedUpload:
    filename: str
    media_type: str
    kind: str
    sha256: str
    size: int
    status: str
    body: bytes


def validate_upload(filename: str, media_type: str, body: bytes,
                    declared_sha256: str) -> ValidatedUpload:
    if not isinstance(filename, str) or not filename or len(filename) > 255:
        raise ValueError("invalid filename")
    if "/" in filename or "\\" in filename or "\x00" in filename or filename in {".", ".."}:
        raise ValueError("invalid filename")
    suffix = next((ext for ext in _ALLOWED if filename.lower().endswith(ext)), None)
    if suffix is None or not isinstance(media_type, str):
        raise ValueError("unsupported upload format")
    expected_mime, kind = _ALLOWED[suffix]
    if media_type.split(";", 1)[0].strip().lower() != expected_mime:
        raise ValueError("media type does not match filename")
    if not isinstance(body, bytes) or not body or len(body) > MAX_UPLOAD_BYTES:
        raise ValueError("upload size out of range")
    if body.startswith((b"PK\x03\x04", b"MZ", b"\x7fELF")):
        raise ValueError("archive or executable content")
    if not isinstance(declared_sha256, str) or not re.fullmatch(r"[a-f0-9]{64}", declared_sha256):
        raise ValueError("invalid declared digest")
    digest = hashlib.sha256(body).hexdigest()
    if digest != declared_sha256:
        raise ValueError("digest mismatch")
    if kind == "pdf":
        lower = body.lower()
        if (not body.startswith(b"%PDF-") or b"%%EOF" not in body[-1024:]
                or any(marker in lower for marker in _PDF_ACTIVE)):
            raise ValueError("invalid or active PDF")
    else:
        try:
            text = body.decode("utf-8", errors="strict")
        except UnicodeError as exc:
            raise ValueError("text upload must be UTF-8") from exc
        if "\x00" in text or re.search(r"<\s*[a-z][^>]*>", text, flags=re.IGNORECASE):
            raise ValueError("active HTML content is not accepted as offer text")
    return ValidatedUpload(filename, expected_mime, kind, digest, len(body), "quarantined", body)


def parse_candidate_facts(upload: ValidatedUpload) -> list[dict]:
    """Extract literal labeled text only; every value awaits human review."""
    if upload.kind == "pdf":
        return []
    facts: list[dict] = []
    for line in upload.body.decode("utf-8").splitlines():
        label, separator, value = line.partition(":")
        field = _FIELDS.get(label.strip().casefold())
        value = value.strip()
        if separator and field and value and len(value) <= 1000:
            facts.append({
                "field": field, "value": value, "approved": False,
                "source_digest": upload.sha256,
            })
    return facts[:20]
