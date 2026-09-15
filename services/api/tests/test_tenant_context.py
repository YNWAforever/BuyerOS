import asyncio
from pathlib import Path

import pytest

from buyeros_api.db.session import tenant_session


def test_tenant_session_rejects_missing_engine():
    with pytest.raises(ValueError):
        asyncio.run(_open(None, "00000000-0000-4000-8000-000000000001"))


def test_tenant_session_rejects_missing_workspace():
    with pytest.raises(ValueError):
        asyncio.run(_open(object(), None))


def test_tenant_session_uses_a_parameterisable_set_config():
    # `SET LOCAL ... = %s` is a syntax error; the function form accepts a bound
    # parameter. This is exercised end-to-end by the worker DB integration tests.
    text_source = (Path(__file__).resolve().parents[1] / "buyeros_api" / "db" / "session.py").read_text(
        encoding="utf-8"
    )
    assert "set_config('app.workspace_id'" in text_source
    assert "SET LOCAL app.workspace_id" not in text_source


async def _open(engine, workspace_id):
    async with tenant_session(engine, workspace_id):
        pass
