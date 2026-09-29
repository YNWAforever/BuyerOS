"""T16 security contracts for pinned fetch and unapproved upload facts."""
import asyncio
import gzip
import hashlib

import pytest

from buyeros_api.services.safe_fetch import fetch_permitted_document


class MemoryStore:
    def __init__(self):
        self.saved = []

    async def put_private(self, body, *, digest, retention_seconds):
        self.saved.append((body, digest, retention_seconds))
        return "private:test-object"


class FixtureTransport:
    pinned_connections = True

    def __init__(self, *, addresses=None, responses=None):
        self.addresses = addresses or {"example.com": ["93.184.216.34"]}
        self.responses = responses or [
            (200, {"content-type": "text/html"}, b"<h1>Verified offer</h1><script>send secrets</script>")
        ]
        self.calls = []

    async def resolve(self, host):
        return self.addresses.get(host, ["93.184.216.34"])

    async def get(self, url, *, pinned_ip, timeout_seconds, max_transfer_bytes):
        self.calls.append((url, pinned_ip))
        return self.responses.pop(0)


INTENT = {"url": "https://example.com/offer", "permitted": True, "retention_seconds": 3600}


def run(transport, store=None, intent=None):
    return asyncio.run(fetch_permitted_document(
        intent or INTENT, transport, store if store is not None else MemoryStore()
    ))


@pytest.mark.parametrize("url", [
    "http://example.com/offer", "https://127.0.0.1/a", "https://[::1]/a",
    "https://169.254.169.254/latest/meta-data",
    "https://user:password@example.com/a", "https://example.com:8443/a",
])
def test_unsafe_targets_block_before_network(url):
    transport = FixtureTransport()
    assert run(transport, intent={**INTENT, "url": url})["status"] == "blocked"
    assert transport.calls == []


def test_mixed_dns_answers_block_before_network():
    transport = FixtureTransport(addresses={"example.com": ["93.184.216.34", "10.0.0.1"]})
    assert run(transport)["status"] == "blocked"
    assert transport.calls == []


def test_every_redirect_host_is_resolved_and_pinned():
    transport = FixtureTransport(
        addresses={"example.com": ["93.184.216.34"], "next.example": ["169.254.169.254"]},
        responses=[(302, {"location": "https://next.example/private"}, b"")],
    )
    assert run(transport)["status"] == "blocked"
    assert len(transport.calls) == 1


def test_gzip_bomb_and_wrong_mime_are_not_stored():
    bomb = gzip.compress(b"x" * 2_097_153)
    for response in [
        (200, {"content-type": "text/html", "content-encoding": "gzip"}, bomb),
        (200, {"content-type": "application/pdf"}, b"%PDF-1.7"),
    ]:
        store = MemoryStore()
        assert run(FixtureTransport(responses=[response]), store)["status"] == "quarantined"
        assert store.saved == []


def test_retrieval_persists_private_sanitized_text_and_digest():
    store = MemoryStore()
    result = run(FixtureTransport(), store)
    assert result["status"] == "retrieved"
    assert result["object_key"] == "private:test-object"
    assert result["bytes"] > 0 and len(result["digest"]) == 64
    assert len(store.saved) == 1
    assert b"Verified offer" in store.saved[0][0]
    assert b"send secrets" not in store.saved[0][0]


def test_unpermitted_or_unpinned_transport_cannot_fetch():
    transport = FixtureTransport()
    assert run(transport, intent={**INTENT, "permitted": False})["status"] == "blocked"
    transport.pinned_connections = False
    assert run(transport)["status"] == "blocked"
    assert transport.calls == []


def test_pinned_transport_uses_checked_ip_with_original_tls_name(monkeypatch):
    from buyeros_api.services.pinned_transport import PinnedHttpsTransport

    seen = {}
    class Reader:
        async def readuntil(self, delimiter):
            return b"HTTP/1.1 200 OK\r\nContent-Length: 5\r\nContent-Type: text/plain\r\n\r\n"
        async def readexactly(self, length):
            assert length == 5
            return b"hello"
    class Writer:
        def write(self, data):
            seen["request"] = data
        async def drain(self):
            pass
        def close(self):
            pass
        async def wait_closed(self):
            pass
    async def connect(**kwargs):
        seen.update(kwargs)
        return Reader(), Writer()
    monkeypatch.setattr(asyncio, "open_connection", connect)
    status, headers, body = asyncio.run(PinnedHttpsTransport().get(
        "https://example.com/a?b=1", pinned_ip="93.184.216.34",
        timeout_seconds=2, max_transfer_bytes=100,
    ))
    assert (status, headers["content-type"], body) == (200, "text/plain", b"hello")
    assert seen["host"] == "93.184.216.34"
    assert seen["server_hostname"] == "example.com"
    assert b"Host: example.com\r\n" in seen["request"]


def test_pinned_transport_reads_to_eof_with_bounded_unknown_length(monkeypatch):
    from buyeros_api.services.pinned_transport import PinnedHttpsTransport

    class Reader:
        def __init__(self):
            self.chunks = [b"hello", b"world", b""]
        async def readuntil(self, delimiter):
            return b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\n"
        async def read(self, limit):
            return self.chunks.pop(0)
    class Writer:
        def write(self, data):
            pass
        async def drain(self):
            pass
        def close(self):
            pass
        async def wait_closed(self):
            pass
    async def connect(**kwargs):
        return Reader(), Writer()
    monkeypatch.setattr(asyncio, "open_connection", connect)
    _, _, body = asyncio.run(PinnedHttpsTransport().get(
        "https://example.com/a", pinned_ip="93.184.216.34",
        timeout_seconds=2, max_transfer_bytes=20,
    ))
    assert body == b"helloworld"


def test_transport_rejects_direct_private_ip_before_socket(monkeypatch):
    from buyeros_api.services.pinned_transport import PinnedHttpsTransport

    async def unexpected(**kwargs):
        raise AssertionError("private socket opened")
    monkeypatch.setattr(asyncio, "open_connection", unexpected)
    with pytest.raises(ValueError, match="public pinned IP"):
        asyncio.run(PinnedHttpsTransport().get(
            "https://example.com/a", pinned_ip="169.254.169.254",
            timeout_seconds=2, max_transfer_bytes=20,
        ))


def test_url_controls_block_before_dns_or_socket():
    transport = FixtureTransport()
    assert run(transport, intent={**INTENT, "url": "https://example.com/offer\r\nHost: localhost"})["status"] == "blocked"
    assert transport.calls == []


def test_upload_rejects_spoofed_format_archive_and_oversize():
    from buyeros_api.services.ingestion_service import validate_upload

    invalid = [
        ("offer.pdf", "application/pdf", b"not a pdf"),
        ("offer.txt", "text/plain", b"PK\x03\x04archive"),
        ("offer.md", "text/markdown", b"<script>send secrets</script>"),
        ("offer.txt", "text/plain", b"x" * (5 * 1024 * 1024 + 1)),
    ]
    for filename, media_type, body in invalid:
        with pytest.raises(ValueError):
            validate_upload(filename, media_type, body, hashlib.sha256(body).hexdigest())


def test_upload_digest_and_unicode_text_yield_unapproved_candidate_facts():
    from buyeros_api.services.ingestion_service import parse_candidate_facts, validate_upload

    body = "Product: \u5de5\u696d\u611f\u6e2c\u5668\nValue proposition: better process monitoring\n".encode()
    digest = hashlib.sha256(body).hexdigest()
    validated = validate_upload("offer.md", "text/markdown", body, digest)
    assert validated.sha256 == digest and validated.kind == "markdown"
    candidates = parse_candidate_facts(validated)
    assert {row["field"] for row in candidates} == {"product", "value_proposition"}
    assert all(row["approved"] is False and row["source_digest"] == digest for row in candidates)
    with pytest.raises(ValueError, match="digest"):
        validate_upload("offer.md", "text/markdown", body, "0" * 64)


def test_pdf_magic_is_quarantined_until_bounded_parser_runs():
    from buyeros_api.services.ingestion_service import validate_upload

    body = b"%PDF-1.7\n1 0 obj << /Type /Catalog >> endobj\n%%EOF"
    item = validate_upload("offer.pdf", "application/pdf", body, hashlib.sha256(body).hexdigest())
    assert item.kind == "pdf"
    assert item.status == "quarantined"


def test_offer_document_schema_enforces_tenant_visibility(seeded):
    import psycopg

    from buyeros_api.db.ingestion import OfferDocument
    from tests.conftest import API_ROLE, API_ROLE_PASSWORD

    WS_A = "11111111-1111-4111-8111-111111111111"
    WS_B = "22222222-2222-4222-8222-222222222222"
    PROJECT_A = "a0000000-0000-4000-8000-000000000001"
    assert OfferDocument.__tablename__ == "offer_documents"
    row_id = "f0000000-0000-4000-8000-000000000016"
    with psycopg.connect(seeded, autocommit=True) as owner:
        owner.execute("DELETE FROM offer_documents WHERE id=%s", (row_id,))
        owner.execute(
            "INSERT INTO offer_documents"
            "(id,workspace_id,project_id,kind,filename,media_type,sha256,status,version)"
            " VALUES (%s,%s,%s,'upload','offer.txt','text/plain',%s,'quarantined',1)",
            (row_id, WS_A, PROJECT_A, "a" * 64),
        )
    role_dsn = seeded.replace("buyeros:buyeros", f"{API_ROLE}:{API_ROLE_PASSWORD}", 1)
    try:
        with psycopg.connect(role_dsn) as viewer:
            viewer.execute("SELECT set_config('app.workspace_id', %s, true)", (WS_B,))
            assert viewer.execute("SELECT count(*) FROM offer_documents WHERE id=%s",
                                  (row_id,)).fetchone()[0] == 0
        with psycopg.connect(role_dsn) as viewer:
            viewer.execute("SELECT set_config('app.workspace_id', %s, true)", (WS_A,))
            assert viewer.execute("SELECT count(*) FROM offer_documents WHERE id=%s",
                                  (row_id,)).fetchone()[0] == 1
    finally:
        with psycopg.connect(seeded, autocommit=True) as owner:
            owner.execute("DELETE FROM offer_documents WHERE id=%s", (row_id,))


def test_r2_store_disabled_without_explicit_activation():
    import uuid
    from buyeros_api.services.object_store import StoreUnavailable, get_private_store

    with pytest.raises(StoreUnavailable, match="disabled"):
        get_private_store(uuid.uuid4())


def test_private_object_keys_are_workspace_bound_without_network():
    import io
    import uuid
    from buyeros_api.services.object_store import R2PrivateStore

    calls = []
    class FakeS3:
        def put_object(self, **kwargs):
            calls.append(("put", kwargs))
        def get_object(self, **kwargs):
            calls.append(("get", kwargs))
            return {"Body": io.BytesIO(b"document")}
        def delete_object(self, **kwargs):
            calls.append(("delete", kwargs))
    ws_a, ws_b = uuid.uuid4(), uuid.uuid4()
    client = FakeS3()
    store_a = R2PrivateStore(ws_a, "private-test", client)
    store_b = R2PrivateStore(ws_b, "private-test", client)
    async def exercise():
        key = await store_a.put_private(
            b"document", digest=hashlib.sha256(b"document").hexdigest(),
            retention_seconds=3600,
        )
        assert key.startswith(f"tenants/{ws_a}/")
        assert await store_a.get_private(key) == b"document"
        with pytest.raises(ValueError, match="foreign"):
            await store_b.get_private(key)
        with pytest.raises(ValueError, match="foreign"):
            await store_b.delete_private(key)
        await store_a.delete_private(key)
    asyncio.run(exercise())
    assert [kind for kind, _ in calls] == ["put", "get", "delete"]


def test_unapproved_redirect_origin_never_receives_request():
    transport = FixtureTransport(
        addresses={"example.com": ["93.184.216.34"], "other.example": ["93.184.216.35"]},
        responses=[
            (302, {"location": "https://other.example/secret"}, b""),
            (200, {"content-type": "text/plain"}, b"secret"),
        ],
    )
    assert run(transport)["status"] == "blocked"
    assert transport.calls == [("https://example.com/offer", "93.184.216.34")]
