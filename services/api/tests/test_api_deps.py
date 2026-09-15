from buyeros_api.api.deps import (
    async_database_url,
    get_engine,
    permitted_roles,
    permission_for_roles,
)


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
    assert permission_for_roles(["viewer"], "createProject") is False
    assert permission_for_roles(["viewer"], "listProjects") is True


def test_workspace_admin_allows_everything():
    assert permission_for_roles(["workspace_admin"], "approveICPVersion") is True


def test_unknown_role_denied():
    assert permission_for_roles(["ghost"], "listProjects") is False


def test_unknown_operation_denies_everyone_without_the_admin_wildcard():
    assert permitted_roles("noSuchOperation") == frozenset()
    assert permission_for_roles(["operator"], "noSuchOperation") is False


def test_operator_creates_projects_but_cannot_approve_icp():
    assert permission_for_roles(["operator"], "createProject") is True
    assert permission_for_roles(["operator"], "approveICPVersion") is False


def test_reviewer_updates_and_approves_but_cannot_create():
    assert permission_for_roles(["reviewer"], "approveICPVersion") is True
    assert permission_for_roles(["reviewer"], "updateProject") is True
    assert permission_for_roles(["reviewer"], "createProject") is False


def test_admins_without_contract_read_grants_are_denied_reads():
    assert permission_for_roles(["policy_admin"], "listProjects") is False
    assert permission_for_roles(["budget_admin"], "listBuyers") is False


def test_operation_roles_are_verbatim_from_the_contract():
    assert permitted_roles("createProject") == frozenset({"operator", "workspace_admin"})
    assert permitted_roles("updateProject") == frozenset({"operator", "reviewer", "workspace_admin"})
    assert permitted_roles("saveICPVersion") == frozenset({"operator", "workspace_admin"})
    assert permitted_roles("approveICPVersion") == frozenset({"reviewer", "workspace_admin"})
    assert permitted_roles("getReadiness") == frozenset({"workspace_admin"})
    assert permitted_roles("listBuyers") == frozenset({"viewer", "operator", "reviewer", "workspace_admin"})
