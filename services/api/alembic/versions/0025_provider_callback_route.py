"""Narrow, non-PII callback routing index for verified vendor references.

Revision ID: 0025_provider_callback_route
Revises: 0024_contact_job_execution

Only SECURITY DEFINER functions can access this cross-tenant index. Tenant
tables keep FORCE RLS; a callback never chooses its own workspace selector.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0025_provider_callback_route"
down_revision: str | None = "0024_contact_job_execution"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE provider_callback_routes (
          provider varchar(64) NOT NULL,
          account_reference varchar(128) NOT NULL,
          provider_ref varchar(255) NOT NULL,
          workspace_id uuid NOT NULL,
          operation_id uuid NOT NULL,
          PRIMARY KEY (provider, account_reference, provider_ref),
          UNIQUE (workspace_id, operation_id),
          CONSTRAINT fk_provider_callback_routes_operation
            FOREIGN KEY (workspace_id, operation_id)
            REFERENCES provider_operations(workspace_id, id) ON DELETE RESTRICT
        )
    """)
    op.execute("""
        CREATE FUNCTION register_provider_callback_route(p_workspace uuid, p_operation uuid)
        RETURNS void LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = public, pg_temp AS $$
        DECLARE op_record record;
        BEGIN
          IF current_setting('app.workspace_id', true) IS NULL OR
             current_setting('app.workspace_id', true)::uuid <> p_workspace THEN
            RAISE EXCEPTION 'tenant context required';
          END IF;
          SELECT provider_name, account_reference, provider_ref INTO op_record
            FROM provider_operations WHERE workspace_id = p_workspace AND id = p_operation;
          IF NOT FOUND OR op_record.provider_name IS NULL OR
             op_record.account_reference IS NULL OR op_record.provider_ref IS NULL THEN
            RAISE EXCEPTION 'persisted provider reference required';
          END IF;
          INSERT INTO provider_callback_routes(provider, account_reference, provider_ref,
                                               workspace_id, operation_id)
            VALUES (op_record.provider_name, op_record.account_reference, op_record.provider_ref,
                    p_workspace, p_operation)
            ON CONFLICT (provider, account_reference, provider_ref) DO NOTHING;
          IF NOT EXISTS (
            SELECT 1 FROM provider_callback_routes WHERE provider = op_record.provider_name
              AND account_reference = op_record.account_reference
              AND provider_ref = op_record.provider_ref
              AND workspace_id = p_workspace AND operation_id = p_operation
          ) THEN
            RAISE EXCEPTION 'provider reference collision';
          END IF;
        END $$
    """)
    op.execute("""
        CREATE FUNCTION resolve_provider_callback_route(p_provider text, p_account text, p_ref text)
        RETURNS TABLE(workspace_id uuid, operation_id uuid)
        LANGUAGE sql SECURITY DEFINER SET search_path = public, pg_temp AS $$
          SELECT r.workspace_id, r.operation_id FROM provider_callback_routes r
          WHERE r.provider = p_provider AND r.account_reference = p_account
            AND r.provider_ref = p_ref
        $$
    """)
    op.execute("REVOKE ALL ON FUNCTION register_provider_callback_route(uuid, uuid) FROM PUBLIC")
    op.execute("REVOKE ALL ON FUNCTION resolve_provider_callback_route(text, text, text) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION register_provider_callback_route(uuid, uuid) TO buyeros_worker")
    op.execute("GRANT EXECUTE ON FUNCTION resolve_provider_callback_route(text, text, text) TO buyeros_api")


def downgrade() -> None:
    retained = op.get_bind().execute(sa.text("SELECT EXISTS(SELECT 1 FROM provider_callback_routes LIMIT 1)"))
    if retained.scalar_one():
        raise RuntimeError("0025 downgrade blocked: retained callback routes")
    op.execute("DROP FUNCTION resolve_provider_callback_route(text, text, text)")
    op.execute("DROP FUNCTION register_provider_callback_route(uuid, uuid)")
    op.execute("DROP TABLE provider_callback_routes")
