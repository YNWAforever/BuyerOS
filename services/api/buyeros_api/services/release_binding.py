"""Credential-safe, read-only identity for the API's actual database connection."""
import asyncio
import hashlib
import hmac
import ipaddress
import json
import os
import re
from urllib.parse import parse_qsl, unquote, urlsplit

from sqlalchemy import text


def database_target_sha256(database_url: str) -> str:
    parsed = urlsplit(database_url)
    if (parsed.scheme not in {'postgresql', 'postgresql+psycopg', 'postgresql+asyncpg'}
            or not parsed.hostname or parsed.fragment
            or any(key.lower() not in {'sslmode', 'sslrootcert', 'channel_binding', 'connect_timeout', 'application_name'}
                   for key, _ in parse_qsl(parsed.query, keep_blank_values=True))):
        raise ValueError('ambiguous database target')
    database = unquote(parsed.path.removeprefix('/'), errors='strict')
    host = parsed.hostname.lower().rstrip('.')
    try:
        host = ipaddress.ip_address(host).compressed
    except ValueError:
        if not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?', host):
            raise ValueError('invalid database endpoint') from None
    port = parsed.port if parsed.port is not None else 5432
    if not database or len(database.encode('utf-8')) > 63 or any(c in database for c in ('/', '\\', '\x00')) or not 1 <= port <= 65535:
        raise ValueError('invalid database target')
    raw = json.dumps({'database': database, 'host': host, 'port': port}, sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha256(raw).hexdigest()


def probe_authorized(supplied: str, expected: str) -> bool:
    if not expected or len(expected) < 32 or len(expected) > 512 or len(supplied) > 512:
        return False
    return hmac.compare_digest(supplied.encode('utf-8'), expected.encode('utf-8'))


def runtime_identity(settings) -> tuple[str, str]:
    source = settings.runtime_source_sha or ''
    deployment = settings.runtime_deployment_id or os.environ.get('VERCEL_DEPLOYMENT_ID', '')
    if not re.fullmatch(r'[0-9a-f]{40}', source) or not re.fullmatch(r'dpl_[A-Za-z0-9_-]+', deployment):
        raise ValueError('runtime identity unavailable')
    return source, deployment


async def read_runtime_binding(engine, source: str, deployment: str) -> dict:
    # The engine URL is the active API pool target, not a migration/owner setting.
    target = database_target_sha256(engine.url.render_as_string(hide_password=False))
    async with asyncio.timeout(8):
        async with engine.connect() as connection:
            async with connection.begin():
                await connection.execute(text('SET TRANSACTION READ ONLY'))
                await connection.execute(text("SET LOCAL statement_timeout = '3000ms'"))
                database = (await connection.execute(text('SELECT current_database()'))).scalar_one()
                heads = (await connection.execute(text('SELECT version_num FROM public.alembic_version LIMIT 2'))).scalars().all()
                if (database != engine.url.database or len(heads) != 1
                        or type(heads[0]) is not str or re.fullmatch(r'[A-Za-z0-9_]{1,128}', heads[0]) is None):
                    raise ValueError('runtime database metadata mismatch')
    return {'schema': 'buyeros.runtime-db-binding.v1', 'source_sha': source,
            'deployment_id': deployment, 'schema_head': heads[0], 'db_target_sha256': target}
