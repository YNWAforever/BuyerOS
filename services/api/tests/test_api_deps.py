from buyeros_api.api.deps import async_database_url, get_engine, permission_for_roles


def test_async_database_url_selects_the_psycopg_driver():
    assert async_database_url("postgresql://u:p@h:5432/db") == "postgresql+psycopg://u:p@h:5432/db"


def test_async_database_url_leaves_explicit_drivers_alone():
    assert async_database_url("postgresql+psycopg://u:p@h/db") == "postgresql+psycopg://u:p@h/db"


def test_get_engine_reuses_one_engine_per_dsn(monkeypatch):
    monkeypatch.setenv("BUYEROS_DATABASE_URL", "postgresql://u:p@localhost:5432/reuse")
    from buyeros_api.settings import get_settings

    get_settings.cache_clear()
    try:
        assert get_engine() is get_engine()
    finally:
        get_settings.cache_clear()


def test_viewer_cannot_write():
    assert permission_for_roles(["viewer"], "project.write") is False
    assert permission_for_roles(["viewer"], "project.read") is True


def test_workspace_admin_allows_everything():
    assert permission_for_roles(["workspace_admin"], "budget.write") is True


def test_unknown_role_denied():
    assert permission_for_roles(["ghost"], "project.read") is False


def test_operator_creates_projects_but_cannot_approve_icp():
    assert permission_for_roles(["operator"], "project.write") is True
    assert permission_for_roles(["operator"], "icp.approve") is False


def test_reviewer_approves_icp_but_cannot_create_projects():
    assert permission_for_roles(["reviewer"], "icp.approve") is True
    assert permission_for_roles(["reviewer"], "project.write") is False
