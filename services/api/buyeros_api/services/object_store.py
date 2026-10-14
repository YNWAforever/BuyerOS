"""Explicit private R2 or Postgres document storage.

No browser credentials, public bucket URL, or presigned download is exposed.
Callers must authorize the workspace/document before reading any object.
"""
from __future__ import annotations

import asyncio
import hashlib
import re
import uuid
from datetime import datetime, timedelta, timezone

from botocore.config import Config

from buyeros_api.settings import get_settings

MAX_OBJECT_BYTES = 5 * 1024 * 1024
MAX_PRIVATE_OBJECT_BYTES = 20 * 1024 * 1024


class StoreUnavailable(RuntimeError):
    pass


class PostgresPrivateStore:
    """Durable bounded bytes using the caller's API or execution database role."""

    def __init__(self, workspace_id: uuid.UUID, engine=None):
        self.workspace_id = workspace_id
        self.engine = engine
        self.prefix = f"postgres/tenants/{workspace_id}/"

    def _checked_id(self, key: str) -> uuid.UUID:
        if not isinstance(key, str) or not key.startswith(self.prefix):
            raise ValueError("foreign or invalid private object key")
        suffix = key[len(self.prefix):]
        try:
            object_id = uuid.UUID(suffix)
        except (ValueError, AttributeError) as exc:
            raise ValueError("foreign or invalid private object key") from exc
        if str(object_id) != suffix:
            raise ValueError("foreign or invalid private object key")
        return object_id

    def _engine(self):
        if self.engine is not None:
            return self.engine
        from buyeros_api.api.deps import get_engine
        return get_engine()

    async def put_private(self, body: bytes, *, digest: str,
                          retention_seconds: int, session=None) -> str:
        from buyeros_api.db.private_objects import PrivateDocumentObject
        from buyeros_api.db.session import tenant_session

        if (not isinstance(body, bytes) or not body or len(body) > MAX_PRIVATE_OBJECT_BYTES
                or not isinstance(digest, str) or hashlib.sha256(body).hexdigest() != digest
                or type(retention_seconds) is not int or not 0 < retention_seconds <= 30 * 86400):
            raise ValueError("private object bounds or digest mismatch")
        object_id = uuid.uuid4()
        created = datetime.now(timezone.utc)
        row = PrivateDocumentObject(
            id=object_id, workspace_id=self.workspace_id, body=body, source_sha256=digest,
            created_at=created, retention_until=created + timedelta(seconds=retention_seconds),
        )
        if session is not None:
            session.add(row)
            await session.flush()
        else:
            async with tenant_session(self._engine(), self.workspace_id) as owned_session:
                owned_session.add(row)
        return self.prefix + str(object_id)

    async def get_private(self, key: str) -> bytes:
        from sqlalchemy import func, select
        from buyeros_api.db.private_objects import PrivateDocumentObject
        from buyeros_api.db.session import tenant_session

        object_id = self._checked_id(key)
        async with tenant_session(self._engine(), self.workspace_id, read_only=True) as session:
            row = (await session.execute(select(
                PrivateDocumentObject.body, PrivateDocumentObject.source_sha256,
            ).where(PrivateDocumentObject.workspace_id == self.workspace_id,
                    PrivateDocumentObject.id == object_id,
                    PrivateDocumentObject.retention_until > func.now()))).first()
        if row is None:
            raise ValueError("private object missing or expired")
        body, digest = bytes(row[0]), row[1]
        if not body or len(body) > MAX_PRIVATE_OBJECT_BYTES or hashlib.sha256(body).hexdigest() != digest:
            raise ValueError("private object bounds or digest mismatch")
        return body

    async def get_private_chunk(self, key: str, *, offset: int, length: int,
                                expected_sha256: str | None = None) -> bytes:
        from sqlalchemy import func, select
        from buyeros_api.db.private_objects import PrivateDocumentObject
        from buyeros_api.db.session import tenant_session

        object_id = self._checked_id(key)
        if type(offset) is not int or offset < 0 or type(length) is not int or not 1 <= length <= 2 * 1024 * 1024:
            raise ValueError('invalid private slice bounds')
        async with tenant_session(self._engine(), self.workspace_id, read_only=True) as session:
            row = (await session.execute(select(
                func.substring(PrivateDocumentObject.body, offset + 1, length),
                PrivateDocumentObject.source_sha256, func.octet_length(PrivateDocumentObject.body),
            ).where(PrivateDocumentObject.workspace_id == self.workspace_id,
                    PrivateDocumentObject.id == object_id,
                    PrivateDocumentObject.retention_until > func.now()))).first()
        if (row is None or not 1 <= row[2] <= MAX_PRIVATE_OBJECT_BYTES
                or offset >= row[2] or expected_sha256 is not None and row[1] != expected_sha256):
            raise ValueError('private object missing, expired or mismatched')
        body = bytes(row[0])
        if len(body) != min(length, row[2] - offset):
            raise ValueError('private slice length mismatch')
        return body

    async def delete_private(self, key: str, *, session=None) -> None:
        from sqlalchemy import delete
        from buyeros_api.db.private_objects import PrivateDocumentObject
        from buyeros_api.db.session import tenant_session

        object_id = self._checked_id(key)
        statement = delete(PrivateDocumentObject).where(
            PrivateDocumentObject.workspace_id == self.workspace_id,
            PrivateDocumentObject.id == object_id,
        )
        if session is not None:
            await session.execute(statement)
        else:
            async with tenant_session(self._engine(), self.workspace_id) as owned_session:
                await owned_session.execute(statement)


async def purge_due_tenant_private_objects(session, workspace_id, *, now=None, limit=100) -> int:
    """Bounded expiry cleanup inside an already-authorized tenant transaction."""
    from sqlalchemy import delete, select
    from buyeros_api.db.private_objects import PrivateDocumentObject

    if not 1 <= limit <= 100:
        raise ValueError("private object cleanup requires a bounded limit")
    now = now or datetime.now(timezone.utc)
    object_ids = (await session.execute(select(PrivateDocumentObject.id).where(
        PrivateDocumentObject.workspace_id == workspace_id,
        PrivateDocumentObject.retention_until <= now,
    ).order_by(PrivateDocumentObject.retention_until, PrivateDocumentObject.id)
      .limit(limit))).scalars().all()
    if not object_ids:
        return 0
    removed = (await session.execute(delete(PrivateDocumentObject).where(
        PrivateDocumentObject.workspace_id == workspace_id,
        PrivateDocumentObject.id.in_(object_ids),
    ).returning(PrivateDocumentObject.id))).scalars().all()
    return len(removed)


async def purge_expired_private_objects(engine, *, now: datetime, runtime_epoch: int,
                                       limit: int = 100) -> int:
    """One native maintenance unit; tenant-scoped, epoch-fenced, and byte-free."""
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from buyeros_api.db.models import Workspace
    from buyeros_api.db.session import tenant_session
    from buyeros_api.services.worker_execution import control_row

    if not 1 <= limit <= 100:
        raise ValueError("private object cleanup requires a bounded limit")
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        workspaces = (await session.execute(select(Workspace.id).order_by(Workspace.id))).scalars().all()
    erased = 0
    for workspace_id in workspaces:
        if erased >= limit:
            break
        async with tenant_session(engine, workspace_id) as session:
            control = await control_row(session, lock=True)
            if (not control.enabled or control.backend != "cloudflare"
                    or control.epoch != runtime_epoch or not get_settings().cloudflare_execution_enabled):
                break
            erased += await purge_due_tenant_private_objects(
                session, workspace_id, now=now, limit=limit - erased,
            )
    return erased


class R2PrivateStore:
    def __init__(self, workspace_id: uuid.UUID, bucket: str, client):
        self.workspace_id = workspace_id
        self.bucket = bucket
        self.client = client
        self.prefix = f"r2/tenants/{workspace_id}/"
        self.legacy_prefix = f"tenants/{workspace_id}/"

    def _checked_key(self, key: str) -> str:
        if (not isinstance(key, str) or not key.startswith((self.prefix, self.legacy_prefix))
                or ".." in key or "://" in key or len(key) > 500):
            raise ValueError("foreign or invalid private object key")
        return key

    async def put_private(self, body: bytes, *, digest: str,
                          retention_seconds: int) -> str:
        if (not isinstance(body, bytes) or not body or len(body) > MAX_OBJECT_BYTES
                or not re.fullmatch(r"[a-f0-9]{64}", digest)
                or not 0 < retention_seconds <= 30 * 86400):
            raise ValueError("private object bounds")
        key = self.prefix + str(uuid.uuid4())
        until = datetime.now(timezone.utc) + timedelta(seconds=retention_seconds)
        await asyncio.to_thread(
            self.client.put_object, Bucket=self.bucket, Key=key, Body=body,
            ContentType="application/octet-stream",
            Metadata={"source-sha256": digest, "retention-until": until.isoformat()},
        )
        return key

    async def get_private(self, key: str) -> bytes:
        key = self._checked_key(key)
        def read():
            response = self.client.get_object(Bucket=self.bucket, Key=key)
            stream = response["Body"]
            try:
                body = stream.read(MAX_OBJECT_BYTES + 1)
            finally:
                stream.close()
            if len(body) > MAX_OBJECT_BYTES:
                raise ValueError("private object size limit")
            return body
        return await asyncio.to_thread(read)

    async def delete_private(self, key: str) -> None:
        await asyncio.to_thread(
            self.client.delete_object, Bucket=self.bucket, Key=self._checked_key(key)
        )


def get_private_store(workspace_id: uuid.UUID, *, engine=None, object_key: str | None = None):
    settings = get_settings()
    backend = settings.private_object_backend
    if object_key is not None:
        if object_key.startswith("postgres/tenants/"):
            backend = "postgres"
        elif object_key.startswith(("r2/tenants/", "tenants/")):
            backend = "r2"
        else:
            raise ValueError("foreign or invalid private object key")
    if backend == "postgres":
        return PostgresPrivateStore(workspace_id, engine=engine)
    if not settings.r2_enabled:
        raise StoreUnavailable("private object storage is disabled")
    values = (
        settings.r2_account_id, settings.r2_bucket,
        settings.r2_access_key_id, settings.r2_secret_access_key,
    )
    if not all(values):
        raise StoreUnavailable("private object storage is unconfigured")
    account, bucket, access, secret = values
    if not re.fullmatch(r"[a-fA-F0-9]{32}", account):
        raise StoreUnavailable("invalid private object account configuration")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,61}[a-z0-9]", bucket):
        raise StoreUnavailable("invalid private object bucket configuration")
    jurisdiction = settings.r2_jurisdiction
    if jurisdiction not in {None, "eu", "us", "fedramp"}:
        raise StoreUnavailable("unsupported R2 jurisdiction")
    endpoint = f"https://{account}.{jurisdiction + '.' if jurisdiction else ''}r2.cloudflarestorage.com"
    import boto3

    client = boto3.client(
        "s3", endpoint_url=endpoint, region_name="auto",
        aws_access_key_id=access, aws_secret_access_key=secret,
        config=Config(connect_timeout=5, read_timeout=10,
                      retries={"max_attempts": 0}, s3={"addressing_style": "path"}),
    )
    return R2PrivateStore(workspace_id, bucket, client)
