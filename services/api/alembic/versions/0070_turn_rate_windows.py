"""Workspace-scoped conversation-turn rate windows (Phase 3.4 admission).

One row per workspace per UTC minute; every member shares the ceiling. The turn
route increments the window atomically in a separate transaction before any turn
write, so a failed or rejected request cannot roll the counter back. Counters are
transient (no evidence), so downgrade simply drops them; forced RLS keeps one
workspace's counters invisible to another.
"""
from pathlib import Path
from runpy import run_path

from alembic import op
import sqlalchemy as sa

revision = '0070_turn_rate_windows'
down_revision = '0069_turn_reconciliations'
branch_labels = depends_on = None
TABLES = ('conversation_turn_rate_windows',)


def fences():
    prior = run_path(str(Path(__file__).with_name('0062_xverum_credits.py')))
    prior['fences'](revision)
    tables = (prior['TABLES']
        + run_path(str(Path(__file__).with_name('0063_xverum_dispatch.py')))['TABLES']
        + ('xverum_enrichments',)
        + run_path(str(Path(__file__).with_name('0065_sales_lifecycle.py')))['TABLES']
        + run_path(str(Path(__file__).with_name('0066_conversation_turns.py')))['TABLES']
        + run_path(str(Path(__file__).with_name('0068_conversation_turn_events.py')))['TABLES']
        + run_path(str(Path(__file__).with_name('0069_conversation_turn_reconciliations.py')))['TABLES']
        + TABLES)
    checks = ''.join(" AND EXISTS(SELECT 1 FROM pg_class WHERE oid=to_regclass('public." + table +
        "') AND relrowsecurity AND relforcerowsecurity)" for table in tables)
    op.execute("CREATE OR REPLACE FUNCTION public.buyeros_xverum_connections_ready() RETURNS boolean "
        "LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$ SELECT "
        "COALESCE((SELECT version_num='" + revision + "' FROM public.alembic_version),false)" + checks + " $$")


def upgrade():
    op.execute("""
    CREATE TABLE conversation_turn_rate_windows (
      workspace_id uuid NOT NULL,
      window_start timestamptz NOT NULL,
      hits integer NOT NULL CONSTRAINT ck_conversation_turn_rate_windows_positive_hits CHECK(hits > 0),
      PRIMARY KEY(workspace_id, window_start)
    );
    CREATE INDEX ix_conversation_turn_rate_windows_expiry
      ON conversation_turn_rate_windows(window_start);

    ALTER TABLE conversation_turn_rate_windows ENABLE ROW LEVEL SECURITY;
    ALTER TABLE conversation_turn_rate_windows FORCE ROW LEVEL SECURITY;
    CREATE POLICY tenant_isolation ON conversation_turn_rate_windows
      USING (workspace_id=NULLIF(current_setting('app.workspace_id',true),'')::uuid)
      WITH CHECK (workspace_id=NULLIF(current_setting('app.workspace_id',true),'')::uuid);
    REVOKE ALL ON conversation_turn_rate_windows FROM PUBLIC,buyeros_api,buyeros_worker;
    GRANT SELECT,INSERT,UPDATE ON conversation_turn_rate_windows TO buyeros_api;
    """)
    fences()


def downgrade():
    # Transient admission counters are not evidence; dropping them cannot lose
    # domain data. (The previous revisions' populated-table guards still apply
    # to their own evidence when the chain is unwound further.)
    op.execute('ALTER TABLE conversation_turn_rate_windows NO FORCE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE conversation_turn_rate_windows DISABLE ROW LEVEL SECURITY')
    op.execute('DROP TABLE conversation_turn_rate_windows')
    run_path(str(Path(__file__).with_name('0069_conversation_turn_reconciliations.py')))['fences']()
