"""Transaction-local tenant context (BO-005).

Every domain query runs inside a transaction that first sets
``app.workspace_id`` with ``SET LOCAL``. RLS policies read that setting, so a
missing context causes no rows to be visible (fail-closed) rather than leaking
another tenant's data. The setting is transaction-local, so it never survives a
pooled connection being reused by a different request.
"""

import contextlib
import uuid
from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker


@contextlib.asynccontextmanager
async def tenant_session(engine: AsyncEngine | None, workspace_id: uuid.UUID | None) -> AsyncIterator[AsyncSession]:
    if engine is None or workspace_id is None:
        raise ValueError("tenant context requires an engine and a workspace_id")
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        async with session.begin():
            await session.execute(text("SET LOCAL app.workspace_id = :ws"), {"ws": str(workspace_id)})
            yield session
