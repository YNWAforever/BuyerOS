"""terminal outbox states, claim index and dispatcher workspace read

Revision ID: 0007_outbox_terminal_state
Revises: 0006_worker_leases
Create Date: 2026-09-15

Completing an outbox intent records a terminal ``done``/``failed`` state in the
same transaction as the work. The claim query only ever re-claims ``ready`` rows
or ``dispatched`` rows whose lease expired, so a terminal row is never re-run and
a duplicate broker delivery is a no-op. The index supports that predicate.

The dispatcher runs under row-level security and cannot read tenant tables
without a workspace context, so it enumerates tenants from ``workspaces`` (the
tenant root, not RLS-protected). That requires a read grant, added here.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0007_outbox_terminal_state"
down_revision: str | None = "0006_worker_leases"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_check_constraint(
        "state",
        "outbox_events",
        "state IN ('ready', 'dispatched', 'done', 'failed')",
    )
    op.create_index(
        "ix_outbox_events_state_lease_expires_at",
        "outbox_events",
        ["state", "lease_expires_at"],
    )
    op.execute("GRANT SELECT ON workspaces TO buyeros_api, buyeros_worker;")


def downgrade() -> None:
    op.execute("REVOKE SELECT ON workspaces FROM buyeros_api, buyeros_worker;")
    op.drop_index("ix_outbox_events_state_lease_expires_at", table_name="outbox_events")
    op.drop_constraint("ck_outbox_events_state", "outbox_events", type_="check")
