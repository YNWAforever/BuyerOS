"""T16: a validated URL is not evidence of retrieval or persistence."""
from buyeros_worker.handlers.fetch_evidence import handle


def test_validated_url_without_transport_or_store_is_not_completed():
    result = handle(
        None, None,
        {"url": "https://example.com/source", "content_type": "text/html", "size": 40},
    )
    assert result.state == "blocked"
    assert "retriev" in result.detail.lower() or "not configured" in result.detail.lower()
