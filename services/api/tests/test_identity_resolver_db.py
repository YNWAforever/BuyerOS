"""C61-06 shared canonical resolver uses immutable issuer/subject only."""
import asyncio
import uuid
import psycopg
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from buyeros_api.api.auth import Principal
from tests.conftest import runtime_role_dsn


def test_identity_resolver_preserves_canonical_uuid_and_exact_issuer_subject(seeded):
    from buyeros_api.services.identity_resolver import resolve_user_id
    identity=uuid.uuid4()
    subject='c61-resolver-'+str(identity)
    with psycopg.connect(seeded,autocommit=True) as owner:
        owner.execute("INSERT INTO users(id,issuer,subject,display_name) VALUES (%s,'urn:c61:issuer',%s,'Same name')",(identity,subject))
    async def exercise():
        engine=create_async_engine(runtime_role_dsn(seeded).replace('postgresql://','postgresql+psycopg://',1))
        try:
            async with AsyncSession(engine) as session:
                assert await resolve_user_id(session,Principal('urn:c61:issuer',subject)) == identity
                assert await resolve_user_id(session,Principal('urn:c61:other',subject)) is None
                assert await resolve_user_id(session,Principal('urn:c61:issuer','Same name')) is None
        finally:
            await engine.dispose()
    try:
        asyncio.run(exercise())
        with psycopg.connect(seeded) as owner:
            assert owner.execute('SELECT id FROM users WHERE issuer=%s AND subject=%s',('urn:c61:issuer',subject)).fetchone()==(identity,)
    finally:
        with psycopg.connect(seeded,autocommit=True) as owner:owner.execute('DELETE FROM users WHERE id=%s',(identity,))


def test_identity_resolver_unknown_identity_does_not_create_user(seeded):
    from buyeros_api.services.identity_resolver import resolve_user_id
    async def exercise():
        engine=create_async_engine(runtime_role_dsn(seeded).replace('postgresql://','postgresql+psycopg://',1))
        try:
            async with AsyncSession(engine) as session:
                assert await resolve_user_id(session,Principal('urn:c61:none','missing')) is None
        finally:await engine.dispose()
    with psycopg.connect(seeded) as owner:before=owner.execute('SELECT count(*) FROM users').fetchone()[0]
    asyncio.run(exercise())
    with psycopg.connect(seeded) as owner:assert owner.execute('SELECT count(*) FROM users').fetchone()[0]==before
