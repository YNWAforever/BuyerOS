"""Project connections and staged integer credit liability, separate from USD."""
from alembic import op
import sqlalchemy as sa

revision = '0062_xverum_credits'
down_revision = '0061_sales_outputs'
branch_labels = depends_on = None
TABLES = ('xverum_connections','xverum_project_assignments','xverum_credit_accounts',
          'xverum_credit_limits','xverum_tariffs','xverum_quotes','xverum_credit_reservations',
          'xverum_receipts','xverum_credit_settlements')


def fences(head):
    for name in ('search_receipts_writable','model_receipts_writable','contact_receipts_writable','xverum_connections_ready'):
        installed = ''
        if name=='xverum_connections_ready' and head==revision:
            installed = ''.join(f" AND EXISTS(SELECT 1 FROM pg_class WHERE oid=to_regclass('public.{table}') AND relrowsecurity AND relforcerowsecurity)" for table in TABLES)
        op.execute(f"CREATE OR REPLACE FUNCTION public.buyeros_{name}() RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$ SELECT COALESCE((SELECT version_num='{head}' FROM public.alembic_version),false){installed} $$")
        op.execute(f'REVOKE ALL ON FUNCTION public.buyeros_{name}() FROM PUBLIC')
        op.execute(f'GRANT EXECUTE ON FUNCTION public.buyeros_{name}() TO buyeros_api,buyeros_worker')


def upgrade():
    common = 'id uuid PRIMARY KEY, workspace_id uuid NOT NULL REFERENCES workspaces(id), created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(), UNIQUE(workspace_id,id),'
    op.execute(f'''
    CREATE TABLE xverum_connections ({common}
        generation integer NOT NULL CHECK(generation>0), version integer NOT NULL CHECK(version>0),
        account_ref varchar(240) NOT NULL CHECK(length(account_ref)>0), tariff_version varchar(240) NOT NULL,
        secret_ref uuid NOT NULL, configured_by uuid NOT NULL REFERENCES users(id),
        status varchar(32) NOT NULL CHECK(status IN ('configuration_required','connected','expired','disconnected')));
    CREATE TABLE xverum_project_assignments ({common}
        connection_id uuid NOT NULL, project_id uuid NOT NULL, UNIQUE(workspace_id,project_id),
        FOREIGN KEY(workspace_id,connection_id) REFERENCES xverum_connections(workspace_id,id),
        FOREIGN KEY(workspace_id,project_id) REFERENCES projects(workspace_id,id));
    CREATE INDEX ix_xverum_assignment_connection ON xverum_project_assignments(workspace_id,connection_id);
    CREATE TABLE xverum_credit_accounts ({common}
        account_ref varchar(240) NOT NULL, credit_limit integer NOT NULL CHECK(credit_limit>=0),
        UNIQUE(workspace_id,account_ref));
    ALTER TABLE xverum_connections ADD CONSTRAINT fk_xverum_connection_account
        FOREIGN KEY(workspace_id,account_ref) REFERENCES xverum_credit_accounts(workspace_id,account_ref);
    CREATE TABLE xverum_credit_limits ({common}
        project_id uuid, credit_limit integer NOT NULL CHECK(credit_limit>=0),
        UNIQUE NULLS NOT DISTINCT(workspace_id,project_id),
        FOREIGN KEY(workspace_id,project_id) REFERENCES projects(workspace_id,id));
    CREATE TABLE xverum_tariffs ({common}
        account_id uuid NOT NULL, version varchar(240) NOT NULL CHECK(length(version)>0),
        usd_per_credit numeric(20,6) NOT NULL CHECK(usd_per_credit>0),
        UNIQUE(workspace_id,account_id,version),
        FOREIGN KEY(workspace_id,account_id) REFERENCES xverum_credit_accounts(workspace_id,id));
    CREATE TABLE xverum_quotes ({common}
        project_id uuid NOT NULL, actor_id uuid NOT NULL REFERENCES users(id), buyer_id uuid NOT NULL,
        connection_id uuid NOT NULL, account_id uuid NOT NULL, tariff_version varchar(240) NOT NULL,
        source_receipt_id uuid, source_digest varchar(64),
        CHECK((source_receipt_id IS NULL AND source_digest IS NULL) OR (source_receipt_id IS NOT NULL AND source_digest ~ '^[a-f0-9]{{64}}$')),
        buyer_version integer NOT NULL CHECK(buyer_version>0), connection_generation integer NOT NULL CHECK(connection_generation>0),
        expires_at timestamptz NOT NULL, fingerprint varchar(64) NOT NULL CHECK(fingerprint ~ '^[a-f0-9]{{64}}$'),
        payload jsonb NOT NULL CHECK(jsonb_typeof(payload)='object' AND octet_length(payload::text)<=8192),
        UNIQUE(workspace_id,project_id,id),
        FOREIGN KEY(workspace_id,project_id,buyer_id) REFERENCES project_buyers(workspace_id,project_id,id),
        FOREIGN KEY(workspace_id,connection_id) REFERENCES xverum_connections(workspace_id,id),
        FOREIGN KEY(workspace_id,account_id,tariff_version) REFERENCES xverum_tariffs(workspace_id,account_id,version));
    CREATE TABLE xverum_credit_reservations ({common}
        project_id uuid NOT NULL, account_id uuid NOT NULL, quote_id uuid NOT NULL, operation_id uuid NOT NULL,
        max_credits integer NOT NULL CHECK(max_credits>0), held_credits integer NOT NULL CHECK(held_credits>=0 AND held_credits<=max_credits),
        usd_reservation_id uuid NOT NULL,
        FOREIGN KEY(workspace_id,usd_reservation_id) REFERENCES budget_reservations(workspace_id,id),
        UNIQUE(workspace_id,quote_id), UNIQUE(workspace_id,operation_id), UNIQUE(workspace_id,project_id,id),
        FOREIGN KEY(workspace_id,account_id) REFERENCES xverum_credit_accounts(workspace_id,id),
        FOREIGN KEY(workspace_id,project_id,quote_id) REFERENCES xverum_quotes(workspace_id,project_id,id));
    CREATE TABLE xverum_receipts ({common}
        project_id uuid NOT NULL, actor_id uuid NOT NULL REFERENCES users(id), reservation_id uuid NOT NULL,
        version integer NOT NULL DEFAULT 1 CHECK(version>0),
        outbox_id uuid, claim_id uuid, claimed_at timestamptz,
        UNIQUE(workspace_id,outbox_id),
        FOREIGN KEY(workspace_id,outbox_id) REFERENCES outbox_events(workspace_id,id),
        operation_key varchar(200) NOT NULL, dispatch_state varchar(32) NOT NULL CHECK(dispatch_state IN ('reserved','dispatched','settled','outcome_unknown','cancelled')),
        request_id varchar(240), projection_digest varchar(64) CHECK(projection_digest ~ '^[a-f0-9]{{64}}$'),
        returned_ids jsonb NOT NULL DEFAULT '[]'::jsonb CHECK(jsonb_typeof(returned_ids)='array' AND jsonb_array_length(returned_ids)<=5),
        UNIQUE(workspace_id,project_id,id),
        UNIQUE(workspace_id,actor_id,operation_key), UNIQUE(workspace_id,reservation_id),
        FOREIGN KEY(workspace_id,project_id,reservation_id) REFERENCES xverum_credit_reservations(workspace_id,project_id,id));
    CREATE TABLE xverum_credit_settlements ({common}
        receipt_id uuid NOT NULL, account_id uuid NOT NULL, project_id uuid NOT NULL,
        credits_used integer NOT NULL CHECK(credits_used>=0), UNIQUE(workspace_id,receipt_id),
        FOREIGN KEY(workspace_id,receipt_id) REFERENCES xverum_receipts(workspace_id,id),
        FOREIGN KEY(workspace_id,account_id) REFERENCES xverum_credit_accounts(workspace_id,id),
        FOREIGN KEY(workspace_id,project_id) REFERENCES projects(workspace_id,id));
    CREATE INDEX ix_xverum_credit_hold ON xverum_credit_reservations(workspace_id,account_id,project_id);
    CREATE INDEX ix_xverum_credit_spend ON xverum_credit_settlements(workspace_id,account_id,project_id);
    ALTER TABLE xverum_quotes ADD CONSTRAINT fk_xverum_quote_search_receipt FOREIGN KEY(workspace_id,project_id,source_receipt_id) REFERENCES xverum_receipts(workspace_id,project_id,id);
    ''')
    for table in TABLES:
        op.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY')
        op.execute(f"CREATE POLICY tenant_isolation ON {table} USING (workspace_id=NULLIF(current_setting('app.workspace_id',true),'')::uuid) WITH CHECK (workspace_id=NULLIF(current_setting('app.workspace_id',true),'')::uuid)")
        op.execute(f'REVOKE ALL ON {table} FROM PUBLIC,buyeros_api,buyeros_worker')
        op.execute(f'GRANT SELECT ON {table} TO buyeros_api,buyeros_worker')
    op.execute('GRANT INSERT,DELETE ON xverum_project_assignments TO buyeros_api')
    # PostgreSQL row locks require UPDATE privilege; never grant cap/tariff writes.
    op.execute('GRANT UPDATE(updated_at) ON xverum_credit_accounts,xverum_credit_limits TO buyeros_api,buyeros_worker')
    op.execute('GRANT UPDATE(generation,version,status,configured_by,updated_at) ON xverum_connections TO buyeros_api')
    op.execute('GRANT INSERT ON xverum_quotes,xverum_credit_reservations,xverum_receipts TO buyeros_api')
    op.execute('GRANT INSERT ON xverum_credit_settlements TO buyeros_api,buyeros_worker')
    op.execute('GRANT UPDATE(held_credits,updated_at) ON xverum_credit_reservations TO buyeros_api,buyeros_worker')
    op.execute('GRANT UPDATE(version,outbox_id,claim_id,claimed_at,dispatch_state,request_id,projection_digest,returned_ids,updated_at) ON xverum_receipts TO buyeros_api,buyeros_worker')
    fences(revision)


def downgrade():
    for table in TABLES:
        op.execute(f'ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY')
    if any(op.get_bind().execute(sa.text(f'SELECT EXISTS(SELECT 1 FROM {table})')).scalar_one() for table in TABLES):
        raise RuntimeError('0062 downgrade blocked: preserve populated Xverum accounting and connections')
    op.execute('ALTER TABLE xverum_quotes DROP CONSTRAINT fk_xverum_quote_search_receipt')
    op.execute('ALTER TABLE xverum_connections DROP CONSTRAINT fk_xverum_connection_account')
    for table in reversed(TABLES):op.execute(f'DROP TABLE {table}')
    fences(down_revision)
    op.execute('DROP FUNCTION public.buyeros_xverum_connections_ready()')
