"""T16 bounded PDF extraction from an untrusted upload."""
import hashlib

import pytest

from buyeros_api.services.ingestion_service import validate_upload


def _pdf(text: str) -> bytes:
    stream = f"BT /F1 12 Tf 50 250 Td ({text}) Tj ET".encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 300] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode() + obj + b"\nendobj\n")
    startxref = len(output)
    output.extend(f"xref\n0 6\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{startxref}\n%%EOF\n".encode())
    return bytes(output)


def test_pdf_text_is_extracted_as_unapproved_candidate_without_network():
    from buyeros_worker.pdf_parser import parse_pdf_candidates

    body = _pdf("Product: Sensor")
    upload = validate_upload("offer.pdf", "application/pdf", body, hashlib.sha256(body).hexdigest())
    facts = parse_pdf_candidates(upload)
    assert [(item["field"], item["value"], item["approved"]) for item in facts] == [
        ("product", "Sensor", False),
    ]


def test_pdf_parser_timeout_fails_closed(monkeypatch):
    from buyeros_worker import pdf_parser

    class Timeout:
        def __call__(self, *args, **kwargs):
            raise pdf_parser.subprocess.TimeoutExpired("parser", 1)

    monkeypatch.setattr(pdf_parser.subprocess, "run", Timeout())
    body = _pdf("Product: Sensor")
    upload = validate_upload("offer.pdf", "application/pdf", body, hashlib.sha256(body).hexdigest())
    with pytest.raises(ValueError, match="timeout"):
        pdf_parser.parse_pdf_candidates(upload)


def test_pdf_page_bomb_and_active_extracted_text_are_rejected():
    from io import BytesIO
    from pypdf import PdfWriter
    from buyeros_worker.pdf_parser import parse_pdf_candidates

    writer = PdfWriter()
    for _ in range(21):
        writer.add_blank_page(width=300, height=300)
    stream = BytesIO()
    writer.write(stream)
    body = stream.getvalue()
    upload = validate_upload("pages.pdf", "application/pdf", body, hashlib.sha256(body).hexdigest())
    with pytest.raises(ValueError, match="rejected"):
        parse_pdf_candidates(upload)

    body = _pdf("Product: <script>alert(1)</script>")
    upload = validate_upload("active.pdf", "application/pdf", body, hashlib.sha256(body).hexdigest())
    with pytest.raises(ValueError, match="active HTML"):
        parse_pdf_candidates(upload)
