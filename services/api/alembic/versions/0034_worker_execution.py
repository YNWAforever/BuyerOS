"""Add disabled runtime selector, fenced step receipts and machine replay guard.

Revision ID: 0034_worker_execution
Revises: 0033_api_rate_windows
"""
from alembic import op
import sqlalchemy as sa

revision = "0034_worker_execution"
down_revision = "0033_api_rate_windows"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE worker_runtime_control (
        singleton INTEGER PRIMARY KEY CHECK(singleton=1),
        backend VARCHAR(16) NOT NULL DEFAULT 'celery' CHECK(backend IN ('celery','cloudflare')),
        enabled BOOLEAN NOT NULL DEFAULT false,
        epoch BIGINT NOT NULL DEFAULT 1 CHECK(epoch BETWEEN 1 AND 9007199254740991),
        cursor UUID, active_owner UUID, active_until TIMESTAMPTZ,
        CHECK((active_owner IS NULL) = (active_until IS NULL)))""")
    op.execute("INSERT INTO worker_runtime_control(singleton) VALUES(1)")
    op.execute("""CREATE FUNCTION enforce_worker_runtime_epoch() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN
        IF NEW.epoch < OLD.epoch OR ((NEW.backend<>OLD.backend OR NEW.enabled<>OLD.enabled)
             AND NEW.epoch<=OLD.epoch) THEN
            RAISE EXCEPTION 'runtime selector changes require a newer epoch';
        END IF; RETURN NEW; END $$""")
    op.execute("CREATE TRIGGER worker_runtime_epoch BEFORE UPDATE ON worker_runtime_control "
               "FOR EACH ROW EXECUTE FUNCTION enforce_worker_runtime_epoch()")
    op.execute("""CREATE TABLE worker_bridge_nonces (
        key_id VARCHAR(64) NOT NULL, nonce UUID NOT NULL, expires_at TIMESTAMPTZ NOT NULL,
        PRIMARY KEY(key_id,nonce))""")
    op.execute("CREATE INDEX ix_worker_bridge_nonces_expiry ON worker_bridge_nonces(expires_at)")
    op.execute("""CREATE TABLE worker_steps (
        id UUID PRIMARY KEY, workspace_id UUID NOT NULL, outbox_id UUID NOT NULL,
        generation BIGINT NOT NULL CHECK(generation BETWEEN 1 AND 9007199254740991),
        step_key VARCHAR(64) NOT NULL, runtime_epoch BIGINT NOT NULL,
        owner UUID NOT NULL, expires_at TIMESTAMPTZ NOT NULL,
        state VARCHAR(16) NOT NULL CHECK(state IN ('running','done','blocked','reconcile')),
        outcome JSONB, attempts INTEGER NOT NULL DEFAULT 1 CHECK(attempts BETWEEN 1 AND 512),
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE(workspace_id,id), UNIQUE(workspace_id,outbox_id,generation,step_key),
        FOREIGN KEY(workspace_id,outbox_id) REFERENCES outbox_events(workspace_id,id),
        FOREIGN KEY(workspace_id) REFERENCES workspaces(id))""")
    op.execute("CREATE INDEX ix_worker_steps_workspace_id ON worker_steps(workspace_id)")
    op.execute("ALTER TABLE worker_steps ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE worker_steps FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY tenant_isolation ON worker_steps
        USING(workspace_id=current_setting('app.workspace_id',true)::uuid)
        WITH CHECK(workspace_id=current_setting('app.workspace_id',true)::uuid)""")
    op.add_column("outbox_events", sa.Column("runtime_backend", sa.String(16), nullable=False, server_default="celery"))
    op.add_column("outbox_events", sa.Column("runtime_epoch", sa.BigInteger(), nullable=False, server_default="1"))
    op.create_check_constraint("ck_outbox_events_runtime_backend", "outbox_events", "runtime_backend IN ('celery','cloudflare')")
    op.create_check_constraint("ck_outbox_events_runtime_epoch", "outbox_events", "runtime_epoch BETWEEN 1 AND 9007199254740991")
    op.execute("GRANT SELECT ON worker_runtime_control TO buyeros_worker")
    op.execute("GRANT UPDATE(cursor,active_owner,active_until) ON worker_runtime_control TO buyeros_worker")
    op.execute("GRANT SELECT,INSERT,UPDATE,DELETE ON worker_steps,worker_bridge_nonces TO buyeros_worker")


def downgrade() -> None:
    bind = op.get_bind()
    for predicate in (
        "EXISTS(SELECT 1 FROM worker_steps)", "EXISTS(SELECT 1 FROM worker_bridge_nonces)",
        "EXISTS(SELECT 1 FROM outbox_events WHERE runtime_backend<>'celery' OR runtime_epoch<>1)",
        "EXISTS(SELECT 1 FROM worker_runtime_control WHERE enabled OR backend<>'celery' OR epoch<>1 OR active_owner IS NOT NULL)",
    ):
        if bind.execute(sa.text("SELECT " + predicate)).scalar_one():
            raise RuntimeError("0034 downgrade blocked: retained execution/replay/fencing state; pause and roll forward")
    op.drop_constraint("ck_outbox_events_runtime_epoch", "outbox_events", type_="check")
    op.drop_constraint("ck_outbox_events_runtime_backend", "outbox_events", type_="check")
    op.drop_column("outbox_events", "runtime_epoch")
    op.drop_column("outbox_events", "runtime_backend")
    op.execute("DROP TABLE worker_steps")
    op.execute("DROP TABLE worker_bridge_nonces")
    op.execute("DROP TABLE worker_runtime_control")
    op.execute("DROP FUNCTION enforce_worker_runtime_epoch()")
