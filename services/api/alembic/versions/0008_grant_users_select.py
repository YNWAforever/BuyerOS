"""grant SELECT on users to the API role

Revision ID: 0008_grant_users_select
Revises: 0007_outbox_terminal_state
Create Date: 2026-09-16

The API resolves an actor by reading `users` (never writing it), but no earlier
migration granted the NOBYPASSRLS runtime roles access to that table, so every
authenticated route failed with `permission denied for table users`. This is a
privilege grant only: no table, column, index or row is touched, and `users`
stays non-RLS to match `workspaces`.

Only `buyeros_api` is granted. The worker never reads `users` (no `users` access
anywhere in `services/worker/buyeros_worker`), so - unlike the `workspaces`
grant - granting it to `buyeros_worker` would be an unnecessary privilege
expansion.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0008_grant_users_select"
down_revision: str | None = "0007_outbox_terminal_state"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("GRANT SELECT ON users TO buyeros_api;")


def downgrade() -> None:
    op.execute("REVOKE SELECT ON users FROM buyeros_api;")
