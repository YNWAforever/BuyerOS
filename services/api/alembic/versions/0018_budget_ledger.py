"""Versioned UTC budget scopes, one operation hold and economic-event identity.

Revision ID: 0018_budget_ledger
Revises: 0017_settings_audit
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0018_budget_ledger"
down_revision: str | None = "0017_settings_audit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
UUID = postgresql.UUID(as_uuid=True)
MONEY = sa.Numeric(20, 6)
MONTH = "date_trunc('month', now() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC'"


def upgrade() -> None:
    bind = op.get_bind()
    # The old schema lacks a project/category identity and event evidence. Never
    # reinterpret a real legacy liability as a workspace-current-period amount.
    material = bind.execute(sa.text(
        "SELECT (SELECT count(*) FROM budget_accounts WHERE approved_limit <> 0 OR settled_spend <> 0) "
        "+ (SELECT count(*) FROM budget_reservations) + (SELECT count(*) FROM cost_events)"
    )).scalar_one()
    if material:
        raise RuntimeError("0018 preflight: legacy financial rows require a reviewed scope/period mapping")
    op.add_column("budget_accounts", sa.Column("scope_id", UUID, nullable=True))
    op.add_column("budget_accounts", sa.Column("category", sa.String(32), nullable=False, server_default="all"))
    op.add_column("budget_accounts", sa.Column("period_start", sa.DateTime(timezone=True), nullable=True))
    op.add_column("budget_accounts", sa.Column("period_end", sa.DateTime(timezone=True), nullable=True))
    op.add_column("budget_accounts", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("budget_accounts", sa.Column("frozen", sa.Boolean(), nullable=False, server_default=sa.false()))
    # Only zero-authority legacy accounts pass preflight; workspace selector is safe.
    op.execute("UPDATE budget_accounts SET scope_id=workspace_id, period_start=" + MONTH + ", period_end=(" + MONTH + " + interval '1 month')")
    op.alter_column("budget_accounts", "scope_id", nullable=False)
    op.alter_column("budget_accounts", "period_start", nullable=False)
    op.alter_column("budget_accounts", "period_end", nullable=False)
    op.drop_constraint("uq_budget_accounts_scope_period", "budget_accounts", type_="unique")
    op.create_unique_constraint("uq_budget_accounts_scope_identity_period", "budget_accounts",
                                ["workspace_id", "scope", "scope_id", "category", "currency", "period_start"])
    op.create_check_constraint("ck_budget_accounts_scope", "budget_accounts", "scope IN ('workspace','project','run','category')")
    op.create_check_constraint("ck_budget_accounts_period", "budget_accounts", "period_end > period_start")
    op.create_check_constraint("ck_budget_accounts_limit", "budget_accounts", "approved_limit >= 0")
    op.create_check_constraint("ck_budget_accounts_version", "budget_accounts", "version > 0")

    op.add_column("budget_reservations", sa.Column("operation_id", UUID, nullable=True))
    op.add_column("budget_reservations", sa.Column("price_version", sa.String(64), nullable=False, server_default="legacy-unverified"))
    op.add_column("budget_reservations", sa.Column("currency", sa.String(8), nullable=False, server_default="USD"))
    op.add_column("budget_reservations", sa.Column("origin_period_start", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE budget_reservations r SET operation_id=r.id, origin_period_start=a.period_start "
               "FROM budget_accounts a WHERE a.id=r.account_id AND a.workspace_id=r.workspace_id")
    op.alter_column("budget_reservations", "operation_id", nullable=False)
    op.alter_column("budget_reservations", "origin_period_start", nullable=False)
    op.create_unique_constraint("uq_budget_reservations_operation", "budget_reservations", ["workspace_id", "operation_id"])
    op.create_foreign_key("fk_budget_reservations_account", "budget_reservations", "budget_accounts",
                          ["workspace_id", "account_id"], ["workspace_id", "id"])
    op.create_check_constraint("ck_budget_reservations_bound", "budget_reservations",
                               "upper_bound > 0 AND remaining_hold >= 0 AND remaining_hold <= upper_bound")
    op.create_table(
        "budget_reservation_allocations",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("workspace_id", UUID, nullable=False),
        sa.Column("reservation_id", UUID, nullable=False),
        sa.Column("account_id", UUID, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("workspace_id", "id", name="uq_budget_reservation_allocations_workspace_id"),
        sa.UniqueConstraint("workspace_id", "reservation_id", "account_id", name="uq_budget_allocations_pair"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_budget_allocations_workspace"),
        sa.ForeignKeyConstraint(["workspace_id", "reservation_id"], ["budget_reservations.workspace_id", "budget_reservations.id"], name="fk_budget_allocations_reservation"),
        sa.ForeignKeyConstraint(["workspace_id", "account_id"], ["budget_accounts.workspace_id", "budget_accounts.id"], name="fk_budget_allocations_account"),
    )
    op.create_index("ix_budget_reservation_allocations_workspace_id", "budget_reservation_allocations", ["workspace_id"])
    op.execute("ALTER TABLE budget_reservation_allocations ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE budget_reservation_allocations FORCE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY tenant_isolation ON budget_reservation_allocations "
               "USING (workspace_id = current_setting('app.workspace_id')::uuid) "
               "WITH CHECK (workspace_id = current_setting('app.workspace_id')::uuid)")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON budget_reservation_allocations TO buyeros_api, buyeros_worker")
    op.execute("INSERT INTO budget_reservation_allocations(id,workspace_id,reservation_id,account_id) "
               "SELECT gen_random_uuid(),workspace_id,id,account_id FROM budget_reservations")

    op.add_column("cost_events", sa.Column("external_event_id", sa.String(200), nullable=True))
    op.add_column("cost_events", sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("cost_events", sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE cost_events SET occurred_at=created_at, recorded_at=created_at")
    op.create_index("uq_cost_events_external_event", "cost_events", ["workspace_id", "external_event_id"],
                    unique=True, postgresql_where=sa.text("external_event_id IS NOT NULL"))
    # Zero-limit accounts for historical projects: no implied spend authority.
    op.execute("INSERT INTO budget_accounts(id,workspace_id,scope,scope_id,category,currency,period,period_start,period_end,approved_limit,settled_spend) "
               "SELECT gen_random_uuid(),p.workspace_id,'workspace',p.workspace_id,'all','USD',to_char(" + MONTH + ", 'YYYY-MM')," + MONTH + ",(" + MONTH + " + interval '1 month'),0,0 "
               "FROM projects p ON CONFLICT DO NOTHING")
    op.execute("INSERT INTO budget_accounts(id,workspace_id,scope,scope_id,category,currency,period,period_start,period_end,approved_limit,settled_spend) "
               "SELECT gen_random_uuid(),p.workspace_id,'project',p.id,'all','USD',to_char(" + MONTH + ", 'YYYY-MM')," + MONTH + ",(" + MONTH + " + interval '1 month'),0,0 "
               "FROM projects p ON CONFLICT DO NOTHING")
    for category in ("discovery", "extraction", "assessment", "contact_lookup", "draft_generation"):
        op.execute("INSERT INTO budget_accounts(id,workspace_id,scope,scope_id,category,currency,period,period_start,period_end,approved_limit,settled_spend) "
                   "SELECT gen_random_uuid(),p.workspace_id,'category',p.id,'" + category + "','USD',to_char(" + MONTH + ", 'YYYY-MM')," + MONTH + ",(" + MONTH + " + interval '1 month'),0,0 "
                   "FROM projects p ON CONFLICT DO NOTHING")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.execute(sa.text("SELECT count(*) FROM budget_reservations")).scalar_one() or bind.execute(sa.text("SELECT count(*) FROM cost_events")).scalar_one():
        raise RuntimeError("0018 downgrade blocked: financial history must be retained")
    if bind.execute(sa.text("SELECT count(*) FROM budget_accounts WHERE approved_limit <> 0 OR settled_spend <> 0 OR version <> 1")).scalar_one():
        raise RuntimeError("0018 downgrade blocked: approved or spent budgets must be retained")
    op.drop_index("uq_cost_events_external_event", table_name="cost_events")
    op.drop_column("cost_events", "recorded_at")
    op.drop_column("cost_events", "occurred_at")
    op.drop_column("cost_events", "external_event_id")
    op.drop_table("budget_reservation_allocations")
    op.drop_constraint("ck_budget_reservations_bound", "budget_reservations", type_="check")
    op.drop_constraint("fk_budget_reservations_account", "budget_reservations", type_="foreignkey")
    op.drop_constraint("uq_budget_reservations_operation", "budget_reservations", type_="unique")
    op.drop_column("budget_reservations", "origin_period_start")
    op.drop_column("budget_reservations", "currency")
    op.drop_column("budget_reservations", "price_version")
    op.drop_column("budget_reservations", "operation_id")
    for name in ("ck_budget_accounts_version", "ck_budget_accounts_limit", "ck_budget_accounts_period", "ck_budget_accounts_scope"):
        op.drop_constraint(name, "budget_accounts", type_="check")
    op.drop_constraint("uq_budget_accounts_scope_identity_period", "budget_accounts", type_="unique")
    # Old uniqueness cannot represent several projects. Only empty provisioned rows may be removed.
    op.execute("DELETE FROM budget_accounts WHERE scope <> 'workspace'")
    op.create_unique_constraint("uq_budget_accounts_scope_period", "budget_accounts", ["workspace_id", "scope", "currency", "period"])
    for name in ("frozen", "version", "period_end", "period_start", "category", "scope_id"):
        op.drop_column("budget_accounts", name)
