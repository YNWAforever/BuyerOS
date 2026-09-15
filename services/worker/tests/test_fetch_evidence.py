import pytest

from buyeros_worker.handlers.fetch_evidence import (
    MAX_DECODED_BYTES,
    FetchRejected,
    handle,
    validate_fetch,
)
from buyeros_worker.registry import get_handler


def test_blocked_host_is_rejected():
    with pytest.raises(FetchRejected):
        validate_fetch("http://127.0.0.1/x", "text/html", 10)


def test_private_host_is_rejected():
    with pytest.raises(FetchRejected):
        validate_fetch("http://10.0.0.1/x", "text/html", 10)


def test_oversized_body_is_rejected():
    with pytest.raises(FetchRejected):
        validate_fetch("https://example.com/x", "text/html", MAX_DECODED_BYTES + 1)


def test_disallowed_content_type_is_rejected():
    with pytest.raises(FetchRejected):
        validate_fetch("https://example.com/x", "application/octet-stream", 10)


def test_valid_public_html_passes():
    validate_fetch("https://example.com/x", "text/html; charset=utf-8", 100)


def test_handler_is_registered():
    assert get_handler("fetch.evidence") is not None


def test_malformed_url_is_rejected_not_raised():
    with pytest.raises(FetchRejected):
        validate_fetch("https://example.com:notaport/x", "text/html", 10)


def test_handler_blocks_malformed_url():
    result = handle(None, None, {"url": "https://example.com:notaport/x", "content_type": "text/html", "size": 1})
    assert result.state == "blocked"
