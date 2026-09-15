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


def test_non_numeric_size_is_blocked_not_raised():
    result = handle(None, None, {"url": "https://example.com/x", "content_type": "text/html", "size": "abc"})
    assert result.state == "blocked"


def test_none_payload_is_blocked_not_raised():
    result = handle(None, None, None)
    assert result.state == "blocked"


def test_negative_size_is_rejected():
    with pytest.raises(FetchRejected):
        validate_fetch("https://example.com/x", "text/html", -1)


@pytest.mark.parametrize("bad", [None, 123, [1], {"a": 1}, True])
def test_non_string_url_is_blocked_not_raised(bad):
    result = handle(None, None, {"url": bad, "content_type": "text/html", "size": 1})
    assert result.state == "blocked"


@pytest.mark.parametrize("bad", [None, 123, ["text/html"], True])
def test_non_string_content_type_is_blocked_not_raised(bad):
    result = handle(None, None, {"url": "https://example.com/x", "content_type": bad, "size": 1})
    assert result.state == "blocked"


@pytest.mark.parametrize(
    "url",
    [
        "http://[::1]/x",
        "https://[fe80::1]/x",
        "http://[fc00::1]/x",
        "http://[::ffff:10.0.0.1]/x",
        "http:///x",
    ],
)
def test_ipv6_and_empty_host_are_rejected(url):
    with pytest.raises(FetchRejected):
        validate_fetch(url, "text/html", 10)


@pytest.mark.parametrize("url", ["http://[::1]/x", "http:///x"])
def test_ipv6_and_empty_host_blocked_via_handle(url):
    result = handle(None, None, {"url": url, "content_type": "text/html", "size": 1})
    assert result.state == "blocked"
