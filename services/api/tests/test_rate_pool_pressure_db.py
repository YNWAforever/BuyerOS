"""Rate admission must not deadlock a saturated tenant connection pool."""
import asyncio

from sqlalchemy.ext.asyncio import create_async_engine

from tests.conftest import runtime_role_dsn
from tests.test_api_projects_db import WORKSPACE_A, OPERATOR, _h, api as project_api


def test_rate_admission_keeps_tenant_pool_slot_available(project_api, seeded, monkeypatch):
    from buyeros_api.api import deps

    engine = create_async_engine(
        deps.async_database_url(runtime_role_dsn(seeded)),
        pool_size=1, max_overflow=0, pool_timeout=0.25,
    )
    monkeypatch.setattr(deps, "get_engine", lambda: engine)
    try:
        response = project_api.get(f"/v1/workspaces/{WORKSPACE_A}/projects", headers=_h(OPERATOR))
        assert response.status_code == 200, response.text
    finally:
        asyncio.run(engine.dispose())
