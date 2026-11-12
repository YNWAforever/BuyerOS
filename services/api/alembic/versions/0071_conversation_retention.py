"""Worker privileges for derived conversation retention (Phase 3.4).

The periodic sweeper prunes two derived structures: turn events (SSE replay
source) and expired per-minute rate windows. Both deletes run in the
transaction-local tenant context, so the same forced RLS policies that protect
reads also bound the sweep. This migration grants the worker role the minimum it
needs and nothing more:

* ``conversation_turn_events``: SELECT + DELETE. The service first selects the
  bounded id set, then deletes exactly those rows. The worker still cannot
  INSERT or UPDATE events; the API remains the only producer.
* ``conversation_turn_rate_windows``: DELETE only. The sweep deletes by
  ``window_start`` range and never reads or writes counters on the API path.

``api_rate_windows`` already grants the worker SELECT + DELETE (0033).

No table, column or user-content change: turns, parts, proposals and decisions
are never pruned by this migration's feature.
"""
from pathlib import Path
from runpy import run_path

from alembic import op

revision = '0071_conversation_retention'
down_revision = '0070_turn_rate_windows'
branch_labels = depends_on = None
TABLES = ()


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
        + run_path(str(Path(__file__).with_name('0070_turn_rate_windows.py')))['TABLES'])
    checks = ''.join(" AND EXISTS(SELECT 1 FROM pg_class WHERE oid=to_regclass('public." + table +
        "') AND relrowsecurity AND relforcerowsecurity)" for table in tables)
    op.execute("CREATE OR REPLACE FUNCTION public.buyeros_xverum_connections_ready() RETURNS boolean "
        "LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$ SELECT "
        "COALESCE((SELECT version_num='" + revision + "' FROM public.alembic_version),false)" + checks + " $$")


def upgrade():
    op.execute("GRANT SELECT,DELETE ON conversation_turn_events TO buyeros_worker")
    op.execute("GRANT DELETE ON conversation_turn_rate_windows TO buyeros_worker")
    fences()


def downgrade():
    op.execute("REVOKE ALL ON conversation_turn_events,conversation_turn_rate_windows FROM buyeros_worker")
    run_path(str(Path(__file__).with_name('0070_turn_rate_windows.py')))['fences']()
