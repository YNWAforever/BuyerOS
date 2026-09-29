"""Private R2-compatible S3 object store; disabled until explicitly configured.

No browser credentials, public bucket URL, or presigned download is exposed.
Callers must authorize the workspace/document before reading any object.
"""
from __future__ import annotations

import asyncio
import re
import uuid
from datetime import datetime, timedelta, timezone

from botocore.config import Config

from buyeros_api.settings import get_settings

MAX_OBJECT_BYTES = 5 * 1024 * 1024


class StoreUnavailable(RuntimeError):
    pass


class R2PrivateStore:
    def __init__(self, workspace_id: uuid.UUID, bucket: str, client):
        self.workspace_id = workspace_id
        self.bucket = bucket
        self.client = client
        self.prefix = f"tenants/{workspace_id}/"

    def _checked_key(self, key: str) -> str:
        if (not isinstance(key, str) or not key.startswith(self.prefix)
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


def get_private_store(workspace_id: uuid.UUID) -> R2PrivateStore:
    settings = get_settings()
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
