"""Native upload lifecycle against real PostgreSQL and HTTP authorization."""
import base64
import hashlib
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import psycopg
import pytest

from tests.pptx_fixtures import pptx_bytes
from tests.test_buyer_review_db import ADMIN, OPERATOR, VIEWER, PROJECT_A, PROJECT_B, WORKSPACE_A, WORKSPACE_B, _h, api
from tests.test_offer_document_routes_db import doc_api
from tests.test_postgres_private_storage_db import private_postgres

MIME = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
BASE = f'/v1/workspaces/{WORKSPACE_A}'
CHUNK = 2 * 1024 * 1024


@pytest.fixture
def native_api(doc_api, private_postgres, seeded):
    doc_api._transport.raise_server_exceptions = True
    yield doc_api
    with psycopg.connect(seeded, autocommit=True) as db:
        db.execute('DELETE FROM document_uploads WHERE workspace_id IN (%s,%s)', (WORKSPACE_A, WORKSPACE_B))
        db.execute("UPDATE projects SET status='active' WHERE id=%s", (PROJECT_A,))
        db.execute('UPDATE memberships SET active=true WHERE workspace_id=%s', (WORKSPACE_A,))


def start(client, body, *, key='native-start-001', name='native.pptx', subject=OPERATOR, **changes):
    payload = dict(filename=name, media_type=MIME, byte_length=len(body), source_sha256=hashlib.sha256(body).hexdigest())
    payload.update(changes)
    return client.post(f'{BASE}/projects/{PROJECT_A}/offer-document-uploads', headers=_h(subject=subject, key=key), json=payload)


def put(client, upload_id, index, body, *, digest=None, subject=OPERATOR):
    return client.put(f'{BASE}/offer-document-uploads/{upload_id}/chunks/{index}', content=body,
                      headers=_h(subject=subject, **{'Content-Type': 'application/octet-stream', 'X-Chunk-Sha256': digest or hashlib.sha256(body).hexdigest()}))


def staged(client, body, **kwargs):
    r = start(client, body, **kwargs)
    assert r.status_code == 201, r.text
    upload = r.json()['data']
    for i in range(upload['chunk_count']):
        part = put(client, upload['id'], i, body[i * CHUNK:(i+1) * CHUNK])
        assert part.status_code == 200, part.text
    return upload


def complete(client, upload, *, key='native-complete-001'):
    return client.post(f"{BASE}/offer-document-uploads/{upload['id']}/complete", headers=_h(key=key), json={})


def count(db, table):
    return db.execute(f'SELECT count(*) FROM {table} WHERE workspace_id=%s', (WORKSPACE_A,)).fetchone()[0]


def test_large_original_slides_and_unapproved_page_provenance(native_api, seeded):
    body = pptx_bytes(('Product: Alpha', 'literal <markup> 中文'), extra={'ppt/media/image.bin': b'x' * (4 * 1024 * 1024 + 1000)}, compression=zipfile.ZIP_STORED)
    upload = staged(native_api, body)
    assert upload['chunk_count'] == 3
    done = complete(native_api, upload)
    assert done.status_code == 202, done.text
    doc = done.json()['data']
    assert doc['status'] == 'ready' and doc['extraction_metadata']['slide_count'] == 2
    assert doc['fact_candidates'][0]['excerpt'] == 'Slide 1: Product: Alpha'
    assert doc['fact_candidates'][0]['approved'] is False
    url = f"{BASE}/offer-documents/{doc['id']}"
    slides = native_api.get(url + '/slides', headers=_h(subject=VIEWER)).json()['data']
    assert [(s['number'], s['text']) for s in slides['items']] == [(1, 'Product: Alpha'), (2, 'literal <markup> 中文')]
    original = []
    for i in range(3):
        r = native_api.get(url + f'/content-chunks/{i}', headers=_h(subject=VIEWER))
        assert r.status_code == 200 and len(r.content) < 4_500_000
        item = r.json()['data']
        part = base64.b64decode(item['body_base64'])
        assert hashlib.sha256(part).hexdigest() == item['chunk_sha256']
        original.append(part)
    assert b''.join(original) == body
    assert complete(native_api, upload).json()['data']['id'] == doc['id']
    assert native_api.get(f"{BASE}/offer-document-uploads/{upload['id']}", headers=_h()).json()['data']['document_id'] == doc['id']
    with psycopg.connect(seeded) as db:
        assert count(db, 'document_upload_chunks') == 0 and count(db, 'async_jobs') == 0
        assert db.execute('SELECT state FROM outbox_events WHERE intent_key=%s', (f"offer.parse:{doc['id']}",)).fetchone() == ('done',)


def test_missing_conflicting_and_replayed_segments(native_api):
    body = pptx_bytes()
    upload = start(native_api, body).json()['data']
    assert complete(native_api, upload).status_code == 409
    assert put(native_api, upload['id'], 0, body).status_code == 200
    assert put(native_api, upload['id'], 0, body).status_code == 200
    assert put(native_api, upload['id'], 0, b'x' * len(body)).status_code == 409
    assert put(native_api, upload['id'], 1, body).status_code == 400
    assert put(native_api, upload['id'], 0, body, digest='0' * 64).status_code == 400


def test_start_reconciliation_and_same_file_dedup(native_api, seeded):
    body = pptx_bytes()
    first = staged(native_api, body)
    assert start(native_api, body).json()['data']['id'] == first['id']
    assert start(native_api, body, key='native-other-tab').json()['data']['id'] == first['id']
    assert start(native_api, body, source_sha256='0' * 64).status_code == 409
    doc = complete(native_api, first).json()['data']
    other = start(native_api, body, key='native-after-complete').json()['data']
    assert other['status'] == 'completed' and other['document_id'] == doc['id']
    with psycopg.connect(seeded) as db:
        assert count(db, 'offer_documents') == 1 and count(db, 'private_document_objects') == 1


def test_current_actor_and_tenant_authority(native_api):
    body = pptx_bytes()
    assert start(native_api, body, subject=VIEWER).status_code == 403
    stage = staged(native_api, body)
    url = f"{BASE}/offer-document-uploads/{stage['id']}"
    assert native_api.get(url, headers=_h(subject=ADMIN)).status_code == 404
    assert native_api.get(url.replace(WORKSPACE_A, WORKSPACE_B), headers=_h()).status_code == 404
    assert put(native_api, stage['id'], 0, body, subject=VIEWER).status_code == 403
    foreign = f'{BASE}/projects/{PROJECT_B}/offer-document-uploads'
    manifest = dict(filename='native.pptx', media_type=MIME, byte_length=len(body), source_sha256=hashlib.sha256(body).hexdigest())
    assert native_api.post(foreign, json=manifest, headers=_h(key='native-foreign-project')).status_code == 404


def test_actor_quota_and_expiry_cleanup(native_api, seeded, monkeypatch):
    from buyeros_api.services import document_upload_service as service
    body = pptx_bytes()
    a = start(native_api, body, key='native-quota-a', name='a.pptx').json()['data']
    assert start(native_api, body, key='native-quota-b', name='b.pptx').status_code == 201
    assert start(native_api, body, key='native-quota-c', name='c.pptx').status_code == 429
    assert put(native_api, a['id'], 0, body).status_code == 200
    future = datetime.now(timezone.utc) + timedelta(hours=2)
    monkeypatch.setattr(service, '_now', lambda: future)
    assert native_api.get(f"{BASE}/offer-document-uploads/{a['id']}", headers=_h()).json()['data']['status'] == 'expired'
    with psycopg.connect(seeded) as db:
        assert count(db, 'document_upload_chunks') == 0


@pytest.mark.parametrize('changes', [{'byte_length': 20 * 1024 * 1024 + 1}, {'source_sha256': 'wrong'}, {'filename': '../evil.pptx'}, {'filename': 'macro.pptm'}, {'media_type': 'application/zip'}, {'byte_length': True}])
def test_manifest_bounds(native_api, changes):
    assert start(native_api, pptx_bytes(), **changes).status_code in (400, 422)


@pytest.mark.parametrize('kind', ['digest', 'invalid', 'timeout'])
def test_terminal_failure_erases_staging_without_ready_document(native_api, seeded, monkeypatch, kind):
    body = b'PK invalid' if kind == 'invalid' else pptx_bytes()
    if kind == 'digest':
        r = start(native_api, body, source_sha256='0' * 64)
        assert r.status_code == 201, r.text
        upload = r.json()['data']
        assert put(native_api, upload['id'], 0, body).status_code == 200
    else:
        upload = staged(native_api, body)
    if kind == 'timeout':
        from buyeros_api.services import document_upload_service as service
        from buyeros_api.execution.pptx_parser import PptxParserTimeout
        async def timeout(*args):
            raise PptxParserTimeout('deadline')
        monkeypatch.setattr(service, 'parse_document', timeout)
    result = complete(native_api, upload)
    assert result.status_code == 400, result.text
    state = native_api.get(f"{BASE}/offer-document-uploads/{upload['id']}", headers=_h()).json()['data']
    assert state['status'] == 'failed' and state['failure_code']
    with psycopg.connect(seeded) as db:
        assert count(db, 'offer_documents') == count(db, 'private_document_objects') == count(db, 'document_upload_chunks') == count(db, 'async_jobs') == 0


@pytest.mark.parametrize('change', ['revoke', 'archive'])
def test_authority_rechecked_after_parser(native_api, seeded, monkeypatch, change):
    from buyeros_api.services import document_upload_service as service
    upload = staged(native_api, pptx_bytes())
    original = service.parse_document
    async def changed(stage, body):
        result = await original(stage, body)
        with psycopg.connect(seeded, autocommit=True) as db:
            if change == 'revoke':
                db.execute('UPDATE memberships SET active=false WHERE workspace_id=%s AND user_id=%s', (WORKSPACE_A, uuid.uuid5(uuid.NAMESPACE_URL, OPERATOR)))
            else:
                db.execute("UPDATE projects SET status='archived' WHERE id=%s", (PROJECT_A,))
        return result
    monkeypatch.setattr(service, 'parse_document', changed)
    assert complete(native_api, upload).status_code == 404
    with psycopg.connect(seeded) as db:
        assert count(db, 'offer_documents') == count(db, 'private_document_objects') == 0


def test_completion_receipt_failure_rolls_back_and_original_operation_recovers(native_api, seeded, monkeypatch):
    from buyeros_api.api.routes import document_uploads as routes
    from buyeros_api.api.errors import ApiError
    stage = staged(native_api, pptx_bytes())
    original = routes.complete_idempotency
    def fail(*args, **kwargs):
        raise ApiError(503, 'PROVIDER_UNAVAILABLE', 'injected receipt failure')
    monkeypatch.setattr(routes, 'complete_idempotency', fail)
    assert complete(native_api, stage).status_code == 503
    with psycopg.connect(seeded) as db:
        assert count(db, 'offer_documents') == count(db, 'private_document_objects') == 0
        assert count(db, 'document_upload_chunks') == 1
    monkeypatch.setattr(routes, 'complete_idempotency', original)
    assert complete(native_api, stage).status_code == 202


def test_image_only_and_deleted_or_expired_sources(native_api, seeded):
    doc = complete(native_api, staged(native_api, pptx_bytes(('', '')))).json()['data']
    assert doc['extraction_metadata']['classification'] == 'image_only' and doc['fact_candidates'] == []
    url = f"{BASE}/offer-documents/{doc['id']}"
    with psycopg.connect(seeded, autocommit=True) as db:
        db.execute("UPDATE offer_documents SET retention_until=now()-interval '1 second' WHERE id=%s", (doc['id'],))
    assert native_api.get(url + '/slides', headers=_h()).status_code == 404
    assert native_api.get(url + '/content-chunks/0', headers=_h()).status_code == 404
    with psycopg.connect(seeded, autocommit=True) as db:
        db.execute("UPDATE offer_documents SET retention_until=now()+interval '1 day' WHERE id=%s", (doc['id'],))
    deleted = native_api.request('DELETE', url, json={'reason': 'obsolete'}, headers=_h(key='native-delete-001', **{'If-Match': '"1"'}))
    assert deleted.status_code == 202, deleted.text
    assert native_api.get(url + '/slides', headers=_h()).status_code == 404
    with psycopg.connect(seeded) as db:
        assert count(db, 'document_slides') == 0 and count(db, 'private_document_objects') == 0


def test_concurrent_completion_returns_one_committed_document(native_api, seeded):
    stage = staged(native_api, pptx_bytes())
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: complete(native_api, stage), range(2)))
    assert [r.status_code for r in results] == [202, 202]
    assert len({r.json()['data']['id'] for r in results}) == 1
    with psycopg.connect(seeded) as db:
        assert count(db, 'offer_documents') == count(db, 'private_document_objects') == 1
        assert count(db, 'document_upload_chunks') == 0


def test_concurrent_starts_cannot_bypass_actor_quota(native_api, seeded):
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(lambda i: start(native_api, pptx_bytes(), key=f'native-race-{i}', name=f'{i}.pptx'), range(3)))
    assert sorted(r.status_code for r in results) == [201, 201, 429]
    with psycopg.connect(seeded) as db:
        assert count(db, 'document_uploads') == 2


def test_workspace_quota_and_completion_key_target_binding(native_api, seeded):
    stage = staged(native_api, pptx_bytes())
    assert complete(native_api, stage).status_code == 202
    other = start(native_api, pptx_bytes(), key='native-second-receipt').json()['data']
    assert complete(native_api, other).status_code == 409
    # Real rows from distinct workspace actors exercise the aggregate bound.
    created = []
    with psycopg.connect(seeded, autocommit=True) as db:
        for i in range(4):
            user = uuid.uuid4()
            created.append(user)
            db.execute('INSERT INTO users(id,issuer,subject) VALUES (%s,%s,%s)', (user, 'https://fixture.invalid', f'quota-{user}'))
            for j in range(2):
                db.execute("INSERT INTO document_uploads(id,workspace_id,project_id,actor_user_id,filename,media_type,byte_length,source_sha256,chunk_size,chunk_count,status,expires_at) VALUES (%s,%s,%s,%s,%s,%s,1,%s,2097152,1,'uploading',now()+interval '1 hour')", (uuid.uuid4(), WORKSPACE_A, PROJECT_A, user, f'{i}-{j}.pptx', MIME, 'a' * 64))
    try:
        assert start(native_api, pptx_bytes(), key='native-workspace-full', name='new.pptx').status_code == 429
    finally:
        with psycopg.connect(seeded, autocommit=True) as db:
            db.execute('DELETE FROM document_uploads WHERE actor_user_id=ANY(%s)', (created,))
            db.execute('DELETE FROM users WHERE id=ANY(%s)', (created,))


def test_legacy_large_text_uses_same_bounded_lifecycle(native_api):
    body = b'Product: A\n' + b' ' * (4 * 1024 * 1024)
    stage = staged(native_api, body, name='large.txt', media_type='text/plain')
    doc = complete(native_api, stage).json()['data']
    assert doc['status'] == 'ready' and doc['fact_candidates'][0]['value'] == 'A'


def test_tampered_page_excerpt_is_rejected_by_profile_source_validator(native_api, seeded):
    import asyncio
    from buyeros_api.api.deps import tenant_scoped
    from buyeros_api.services.offer_document_refs import validate_offer_document_refs
    from buyeros_api.api.errors import ApiError
    from buyeros_api.api.schemas import OfferFact
    doc = complete(native_api, staged(native_api, pptx_bytes())).json()['data']
    fact = {**doc['fact_candidates'][0], 'excerpt': 'Slide 2: Product: Alpha'}
    async def validate():
        async with tenant_scoped(uuid.UUID(WORKSPACE_A)) as session:
            await validate_offer_document_refs(session, workspace_id=uuid.UUID(WORKSPACE_A), project_id=uuid.UUID(PROJECT_A),
                document_ids=[uuid.UUID(doc['id'])], facts=[OfferFact.model_validate(fact)])
    with pytest.raises(ApiError):
        asyncio.run(validate())


def test_expired_slide_cleanup_progresses_past_legacy_documents_without_slides(native_api, seeded):
    doc = complete(native_api, staged(native_api, pptx_bytes())).json()['data']
    with psycopg.connect(seeded, autocommit=True) as db:
        db.execute("UPDATE offer_documents SET retention_until=now()-interval '1 second' WHERE id=%s", (doc['id'],))
        for index in range(64):
            db.execute("INSERT INTO offer_documents(id,workspace_id,project_id,kind,filename,media_type,status,retention_until) VALUES (%s,%s,%s,'upload',%s,'text/plain','ready',now()-interval '1 day')", (uuid.uuid4(), WORKSPACE_A, PROJECT_A, f'expired-legacy-{index}.txt'))
    result = native_api.get(f'{BASE}/projects/{PROJECT_A}/offer-documents', headers=_h(subject=VIEWER))
    assert result.status_code == 200, result.text
    with psycopg.connect(seeded) as db:
        assert db.execute('SELECT count(*) FROM document_slides WHERE document_id=%s', (doc['id'],)).fetchone() == (0,)


def test_authorized_original_read_needs_only_one_pool_connection(native_api, seeded, monkeypatch):
    import asyncio
    from sqlalchemy.ext.asyncio import create_async_engine
    from buyeros_api.api import deps
    from tests.conftest import runtime_role_dsn
    doc = complete(native_api, staged(native_api, pptx_bytes())).json()['data']
    engine = create_async_engine(deps.async_database_url(runtime_role_dsn(seeded)), pool_size=1, max_overflow=0, pool_timeout=0.05)
    monkeypatch.setattr(deps, 'get_engine', lambda: engine)
    try:
        result = native_api.get(f"{BASE}/offer-documents/{doc['id']}/content-chunks/0", headers=_h(subject=VIEWER))
        assert result.status_code == 200, result.text
        assert hashlib.sha256(base64.b64decode(result.json()['data']['body_base64'])).hexdigest() == doc['sha256']
    finally:
        asyncio.run(engine.dispose())
