"""row-level security and least-privilege runtime roles

Revision ID: 0002_rls_and_roles
Revises: 0001_initial
Create Date: 2026-09-15

Every tenant table gets RLS with a transaction-local tenant setting. Runtime
roles (buyeros_api, buyeros_worker) are NOBYPASSRLS and never own tables; the
migration-owner role is separate. A missing `app.workspace_id` yields no rows
(fail-closed) instead of leaking another tenant's data.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002_rls_and_roles"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_TABLES = ("memberships",)


def upgrade() -> None:
    op.execute("CREATE ROLE buyeros_api NOBYPASSRLS;")
    op.execute("CREATE ROLE buyeros_worker NOBYPASSRLS;")

    for table in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            "USING (workspace_id = current_setting('app.workspace_id')::uuid) "
            "WITH CHECK (workspace_id = current_setting('app.workspace_id')::uuid);"
        )
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO buyeros_api, buyeros_worker;")


def downgrade() -> None:
    for table in TENANT_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table};")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")
        op.execute(f"REVOKE ALL ON {table} FROM buyeros_api, buyeros_worker;")
    op.execute("DROP ROLE IF EXISTS buyeros_api;")
    op.execute("DROP ROLE IF EXISTS buyeros_worker;")
