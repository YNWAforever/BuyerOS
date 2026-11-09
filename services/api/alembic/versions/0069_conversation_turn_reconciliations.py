"""Effective, evidence-keyed turn reconciliations (latest wins).

A reconcile attempt is recorded once per distinct persisted evidence digest for
a source turn. Equivalent attempts (same evidence) return the recorded
continuation without a new probe result or audit row; a later attempt that finds
new authoritative evidence creates the next resolution row and may transition
the source turn out of ``outcome_unknown`` exactly once.

Only the API role reads/appends these rows; no worker grants. Forced RLS.
Downgrade refuses while resolution evidence exists.
"""
from pathlib import Path
from runpy import run_path

from alembic import op
import sqlalchemy as sa

revision = '0069_turn_reconciliations'
down_revision = '0068_conversation_turn_events'
branch_labels = depends_on = None
TABLES = ('conversation_turn_reconciliations',)


def fences():
    prior = run_path(str(Path(__file__).with_name('0062_xverum_credits.py')))
    prior['fences'](revision)
    tables = (prior['TABLES']
        + run_path(str(Path(__file__).with_name('0063_xverum_dispatch.py')))['TABLES']
        + ('xverum_enrichments',)
        + run_path(str(Path(__file__).with_name('0065_sales_lifecycle.py')))['TABLES']
        + run_path(str(Path(__file__).with_name('0066_conversation_turns.py')))['TABLES']
        + run_path(str(Path(__file__).with_name('0068_conversation_turn_events.py')))['TABLES']
        + TABLES)
    checks = ''.join(" AND EXISTS(SELECT 1 FROM pg_class WHERE oid=to_regclass('public." + table +
        "') AND relrowsecurity AND relforcerowsecurity)" for table in tables)
    op.execute("CREATE OR REPLACE FUNCTION public.buyeros_xverum_connections_ready() RETURNS boolean "
        "LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$ SELECT "
        "COALESCE((SELECT version_num='" + revision + "' FROM public.alembic_version),false)" + checks + " $$")


def upgrade():
    op.execute("""
    CREATE TABLE conversation_turn_reconciliations (
      id uuid PRIMARY KEY, workspace_id uuid NOT NULL, project_id uuid NOT NULL,
      thread_id uuid NOT NULL, source_turn_id uuid NOT NULL,
      actor_id uuid NOT NULL REFERENCES users(id),
      evidence_digest varchar(64) NOT NULL CHECK(evidence_digest ~ '^[a-f0-9]{64}$'),
      evidence_seq integer NOT NULL CHECK(evidence_seq>0),
      outcome varchar(16) NOT NULL CHECK(outcome IN ('completed','failed','unknown')),
      code varchar(64) NOT NULL CHECK(code ~ '^[A-Z][A-Z0-9_]{2,63}$'),
      message varchar(500) NOT NULL CHECK(length(btrim(message))>0),
      continuation_turn_id uuid NOT NULL,
      created_at timestamptz NOT NULL DEFAULT now(),
      CONSTRAINT uq_conversation_turn_reconciliations_evidence
        UNIQUE(workspace_id,source_turn_id,evidence_digest),
      CONSTRAINT uq_conversation_turn_reconciliations_seq
        UNIQUE(workspace_id,source_turn_id,evidence_seq),
      CONSTRAINT fk_conversation_turn_reconciliations_source
        FOREIGN KEY(workspace_id,project_id,thread_id,source_turn_id)
        REFERENCES conversation_turns(workspace_id,project_id,thread_id,id) ON DELETE CASCADE,
      CONSTRAINT fk_conversation_turn_reconciliations_continuation
        FOREIGN KEY(workspace_id,project_id,thread_id,continuation_turn_id)
        REFERENCES conversation_turns(workspace_id,project_id,thread_id,id) ON DELETE CASCADE
    );
    CREATE INDEX ix_conversation_turn_reconciliations_source
      ON conversation_turn_reconciliations(workspace_id,source_turn_id,evidence_seq DESC);

    ALTER TABLE conversation_turn_reconciliations ENABLE ROW LEVEL SECURITY;
    ALTER TABLE conversation_turn_reconciliations FORCE ROW LEVEL SECURITY;
    CREATE POLICY tenant_isolation ON conversation_turn_reconciliations
      USING (workspace_id=NULLIF(current_setting('app.workspace_id',true),'')::uuid)
      WITH CHECK (workspace_id=NULLIF(current_setting('app.workspace_id',true),'')::uuid);
    REVOKE ALL ON conversation_turn_reconciliations FROM PUBLIC,buyeros_api,buyeros_worker;
    GRANT SELECT,INSERT ON conversation_turn_reconciliations TO buyeros_api;
    -- A resolution transitions the source turn out of outcome_unknown once.
    GRANT UPDATE(status,updated_at) ON conversation_turns TO buyeros_api;
    """)
    fences()


def downgrade():
    db = op.get_bind()
    op.execute('ALTER TABLE conversation_turn_reconciliations NO FORCE ROW LEVEL SECURITY')
    if db.execute(sa.text('SELECT EXISTS(SELECT 1 FROM conversation_turn_reconciliations)')).scalar_one():
        raise RuntimeError('0069 downgrade blocked: preserve turn reconciliation evidence')
    op.execute('ALTER TABLE conversation_turn_reconciliations NO ROW LEVEL SECURITY')
    op.execute('DROP TABLE conversation_turn_reconciliations')
    op.execute('REVOKE UPDATE(status,updated_at) ON conversation_turns FROM buyeros_api')
    run_path(str(Path(__file__).with_name('0068_conversation_turn_events.py')))['fences']()
