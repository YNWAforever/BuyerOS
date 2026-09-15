from buyeros_api.api.deps import permission_for_roles


def test_viewer_cannot_write():
    assert permission_for_roles(["viewer"], "project.write") is False
    assert permission_for_roles(["viewer"], "project.read") is True


def test_workspace_admin_allows_everything():
    assert permission_for_roles(["workspace_admin"], "budget.write") is True


def test_unknown_role_denied():
    assert permission_for_roles(["ghost"], "project.read") is False
