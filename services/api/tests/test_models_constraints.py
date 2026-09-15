from buyeros_api.db.models import Membership, User, Workspace


def test_membership_has_composite_unique_and_tenant_fk():
    table = Membership.__table__
    uniques = {
        tuple(sorted(column.name for column in constraint.columns))
        for constraint in table.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }
    assert ("id", "workspace_id") in uniques
    assert ("user_id", "workspace_id") in uniques

    fks = {fk.parent.name: fk.target_fullname for fk in table.foreign_keys}
    assert fks["workspace_id"] == "workspaces.id"
    assert fks["user_id"] == "users.id"


def test_membership_workspace_id_is_non_null():
    assert Membership.__table__.c.workspace_id.nullable is False


def test_user_is_unique_by_issuer_and_subject():
    table = User.__table__
    uniques = {
        tuple(sorted(column.name for column in constraint.columns))
        for constraint in table.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }
    assert ("issuer", "subject") in uniques


def test_workspace_table_name():
    assert Workspace.__tablename__ == "workspaces"
