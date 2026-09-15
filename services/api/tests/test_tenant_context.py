import asyncio

import pytest

from buyeros_api.db.session import tenant_session


def test_tenant_session_rejects_missing_engine():
    with pytest.raises(ValueError):
        asyncio.run(_open(None, "00000000-0000-4000-8000-000000000001"))


def test_tenant_session_rejects_missing_workspace():
    with pytest.raises(ValueError):
        asyncio.run(_open(object(), None))


async def _open(engine, workspace_id):
    async with tenant_session(engine, workspace_id):
        pass
