"""Real storage invariants: tenant keys, immutable chunks and safe downgrade."""
import asyncio
import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg
import pytest
from alembic import command
from alembic.config import Config

from tests.test_buyer_review_db import api, WORKSPACE_A, WORKSPACE_B, PROJECT_A
from tests.conftest import runtime_role_dsn


@pytest.fixture(autouse=True)
def staged_upload_cleanup(api, seeded):
    # This module creates stages without going through document completion.
    # Remove its own fixture records before the existing API fixture deletes users.
    yield
    with psycopg.connect(seeded, autocommit=True) as db:
        db.execute('DELETE FROM document_uploads WHERE workspace_id IN (%s,%s)', (WORKSPACE_A, WORKSPACE_B))


def session_row(db, *, workspace=WORKSPACE_A, project=PROJECT_A):
    actor = db.execute('SELECT user_id FROM memberships WHERE workspace_id=%s LIMIT 1', (WORKSPACE_A,)).fetchone()[0]
    ident = uuid.uuid4()
    db.execute("INSERT INTO document_uploads(id,workspace_id,project_id,actor_user_id,filename,media_type,byte_length,source_sha256,chunk_size,chunk_count,status,expires_at) VALUES (%s,%s,%s,%s,'source.pptx','application/vnd.openxmlformats-officedocument.presentationml.presentation',4,%s,2097152,1,'uploading',now()+interval '1 hour')", (ident, workspace, project, actor, hashlib.sha256(b'abcd').hexdigest()))
    return ident


def test_upload_chunk_composite_tenant_fk_and_force_rls(api, seeded):
    with psycopg.connect(seeded, autocommit=True) as db:
        ident = session_row(db)
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            db.execute('INSERT INTO document_upload_chunks(workspace_id,upload_id,chunk_index,body,sha256) VALUES (%s,%s,0,%s,%s)', (WORKSPACE_B, ident, b'abcd', hashlib.sha256(b'abcd').hexdigest()))
    with psycopg.connect(runtime_role_dsn(seeded)) as db:
        db.execute("SELECT set_config('app.workspace_id',%s,true)", (WORKSPACE_B,))
        assert db.execute('SELECT count(*) FROM document_uploads WHERE id=%s', (ident,)).fetchone() == (0,)
        for table in ('document_uploads', 'document_upload_chunks', 'document_slides'):
            assert db.execute('SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE relname=%s', (table,)).fetchone() == (True, True)


def test_chunk_database_digest_bounds_and_immutability(api, seeded):
    with psycopg.connect(seeded, autocommit=True) as db:
        ident = session_row(db)
        with pytest.raises(psycopg.errors.CheckViolation):
            db.execute('INSERT INTO document_upload_chunks(workspace_id,upload_id,chunk_index,body,sha256) VALUES (%s,%s,0,%s,%s)', (WORKSPACE_A, ident, b'abcd', '0'*64))
        body = b'x' * (2*1024*1024+1)
        with pytest.raises(psycopg.errors.CheckViolation):
            db.execute('INSERT INTO document_upload_chunks(workspace_id,upload_id,chunk_index,body,sha256) VALUES (%s,%s,0,%s,%s)', (WORKSPACE_A, ident, body, hashlib.sha256(body).hexdigest()))
        db.execute('INSERT INTO document_upload_chunks(workspace_id,upload_id,chunk_index,body,sha256) VALUES (%s,%s,0,%s,%s)', (WORKSPACE_A, ident, b'abcd', hashlib.sha256(b'abcd').hexdigest()))
        with pytest.raises(psycopg.errors.CheckViolation):
            db.execute("UPDATE document_upload_chunks SET body=%s,sha256=%s WHERE upload_id=%s", (b'efgh', hashlib.sha256(b'efgh').hexdigest(), ident))
        assert bytes(db.execute('SELECT body FROM document_upload_chunks WHERE upload_id=%s', (ident,)).fetchone()[0]) == b'abcd'
        with pytest.raises(psycopg.errors.CheckViolation):
            db.execute('UPDATE document_uploads SET byte_length=8 WHERE id=%s', (ident,))


def test_private_store_accepts_large_original_and_bounded_slices(api, seeded):
    from buyeros_api.services.object_store import PostgresPrivateStore
    from buyeros_api.api.deps import async_database_url
    from sqlalchemy.ext.asyncio import create_async_engine
    body = b'abcdef' * (1024*1024)
    async def exercise():
        engine = create_async_engine(async_database_url(runtime_role_dsn(seeded)))
        try:
            store = PostgresPrivateStore(uuid.UUID(WORKSPACE_A), engine)
            key = await store.put_private(body, digest=hashlib.sha256(body).hexdigest(), retention_seconds=60)
            assert await store.get_private_chunk(key, offset=2, length=4) == b'cdef'
            with pytest.raises(ValueError):
                await store.get_private_chunk(key, offset=0, length=2*1024*1024+1)
            with pytest.raises(ValueError):
                await store.get_private_chunk(key, offset=len(body), length=1)
            await store.delete_private(key)
        finally:
            await engine.dispose()
    asyncio.run(exercise())


def test_slide_text_cannot_link_document_in_foreign_project(api, seeded):
    ident = uuid.uuid4()
    with psycopg.connect(seeded, autocommit=True) as db:
        db.execute("INSERT INTO offer_documents(id,workspace_id,project_id,kind,filename,media_type,status,extraction_metadata) VALUES (%s,%s,%s,'upload','source.pptx','application/vnd.openxmlformats-officedocument.presentationml.presentation','ready','{}')", (ident, WORKSPACE_A, PROJECT_A))
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            db.execute("INSERT INTO document_slides(workspace_id,project_id,document_id,slide_number,text,classification) VALUES (%s,%s,%s,1,'literal','text')", (WORKSPACE_B, PROJECT_A, ident))


def test_populated_upload_downgrade_is_atomic_and_retains_force_rls(api, seeded, monkeypatch):
    from buyeros_api.settings import get_settings
    with psycopg.connect(seeded, autocommit=True) as db:
        session_row(db)
    monkeypatch.setenv('BUYEROS_DATABASE_URL', seeded)
    get_settings.cache_clear()
    root = Path(__file__).resolve().parents[1]
    cfg = Config(str(root/'alembic.ini'))
    cfg.set_main_option('script_location', str(root/'alembic'))
    with pytest.raises(RuntimeError, match='downgrade blocked'):
        command.downgrade(cfg, '0052_private_document_storage')
    with psycopg.connect(seeded) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone() == ('0057_conversation_model',)
        assert db.execute("SELECT relforcerowsecurity FROM pg_class WHERE relname='document_uploads'").fetchone() == (True,)
