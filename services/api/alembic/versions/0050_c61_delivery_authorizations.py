"""Proposed additive delivery authority ledger; install only after frozen run.

The local head/peer inventory must be rechecked before allocating this revision.
No historical message receives invented delivery authority or a new provider key.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision='0050_c61_delivery_authorizations'
down_revision='0049_c61_delivery_money'
branch_labels=depends_on=None

def _receipt_guard(head):
    for service in ('search','model','contact'):
        op.execute(f"CREATE OR REPLACE FUNCTION public.buyeros_{service}_receipts_writable() RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$ SELECT COALESCE((SELECT version_num='{head}' FROM public.alembic_version),false) $$")

def upgrade():
    op.create_table('delivery_authorizations',
        sa.Column('id',UUID(as_uuid=True),primary_key=True),
        sa.Column('workspace_id',UUID(as_uuid=True),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.Column('message_id',UUID(as_uuid=True),nullable=False),
        sa.Column('outbox_id',UUID(as_uuid=True),nullable=False),
        sa.Column('scope_hash',sa.String(64),nullable=False),
        sa.Column('scope_json',sa.Text,nullable=False),
        sa.Column('valid_until',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('workspace_id','id',name='uq_delivery_authorizations_workspace_id'),
        sa.UniqueConstraint('workspace_id','message_id',name='uq_delivery_authorizations_message'),
        sa.UniqueConstraint('workspace_id','outbox_id',name='uq_delivery_authorizations_outbox'),
        sa.ForeignKeyConstraint(['workspace_id'],['workspaces.id'],name='fk_delivery_authorizations_workspace'),
        sa.ForeignKeyConstraint(['workspace_id','message_id'],['delivery_messages.workspace_id','delivery_messages.id'],name='fk_delivery_authorizations_message'),
        sa.ForeignKeyConstraint(['workspace_id','outbox_id'],['outbox_events.workspace_id','outbox_events.id'],name='fk_delivery_authorizations_outbox'),
        sa.CheckConstraint("scope_hash ~ '^[0-9a-f]{64}$' AND octet_length(scope_json) BETWEEN 1 AND 524288 AND scope_hash=encode(sha256(convert_to(scope_json,'UTF8')),'hex')",name='scope_digest'),
        sa.Index('ix_delivery_authorizations_workspace_id','workspace_id'),
    )
    op.execute('ALTER TABLE delivery_authorizations ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE delivery_authorizations FORCE ROW LEVEL SECURITY')
    op.execute("CREATE POLICY delivery_authorizations_tenant ON delivery_authorizations USING (workspace_id=NULLIF(current_setting('app.workspace_id',true),'')::uuid) WITH CHECK (workspace_id=NULLIF(current_setting('app.workspace_id',true),'')::uuid)")
    op.execute('REVOKE ALL ON delivery_authorizations FROM PUBLIC,buyeros_api,buyeros_worker')
    op.execute('GRANT SELECT,INSERT ON delivery_authorizations TO buyeros_api,buyeros_worker')
    op.execute(r"""
    CREATE FUNCTION guard_delivery_authorization() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$
    DECLARE scope jsonb; bound boolean;
    BEGIN
      IF TG_OP='UPDATE' THEN
        RAISE EXCEPTION 'original delivery authority is immutable' USING ERRCODE='23514';
      END IF;
      scope:=NEW.scope_json::jsonb;
      IF jsonb_typeof(scope) IS DISTINCT FROM 'object'
        OR (SELECT count(*) FROM json_each(NEW.scope_json::json))<>14
        OR (SELECT count(*) FROM jsonb_object_keys(scope))<>14
        OR scope-ARRAY['workspace_id','project_id','sender_identity_id','recipient_refs','provider_name','account_reference','pricing_version','upper_bound','currency','reviewed_contract_hash','selected','reviewed','sender_verified','valid_until']<>'{}'::jsonb
        OR jsonb_typeof(scope->'recipient_refs') IS DISTINCT FROM 'array'
        OR EXISTS(SELECT 1 FROM unnest(ARRAY['workspace_id','project_id','sender_identity_id','provider_name','account_reference','pricing_version','upper_bound','currency','reviewed_contract_hash','valid_until']) keys(key) WHERE jsonb_typeof(scope->key) IS DISTINCT FROM 'string')
      THEN RAISE EXCEPTION 'complete bounded delivery authority scope required' USING ERRCODE='23514'; END IF;
      IF jsonb_array_length(scope->'recipient_refs') NOT BETWEEN 1 AND 10000
        OR EXISTS(SELECT 1 FROM jsonb_array_elements(scope->'recipient_refs') x WHERE jsonb_typeof(x) IS DISTINCT FROM 'string')
        OR EXISTS(SELECT 1 FROM jsonb_array_elements_text(scope->'recipient_refs') x WHERE x!~'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' OR x='00000000-0000-0000-0000-000000000000')
        OR (SELECT count(*) FROM jsonb_array_elements_text(scope->'recipient_refs'))<>(SELECT count(DISTINCT x) FROM jsonb_array_elements_text(scope->'recipient_refs') x)
        OR scope->'selected' IS DISTINCT FROM 'true'::jsonb
        OR scope->'reviewed' IS DISTINCT FROM 'true'::jsonb
        OR scope->'sender_verified' IS DISTINCT FROM 'true'::jsonb
        OR scope->>'reviewed_contract_hash'!~'^[0-9a-f]{64}$'
        OR scope->>'upper_bound'!~'^[0-9]{1,14}\.[0-9]{6}$'
        OR scope->>'currency' IS DISTINCT FROM 'USD'
        OR scope->>'pricing_version' LIKE 'legacy-%'
        OR NEW.valid_until IS DISTINCT FROM (scope->>'valid_until')::timestamptz
        OR NEW.valid_until<=clock_timestamp()
      THEN RAISE EXCEPTION 'selected reviewed current delivery authority required' USING ERRCODE='23514'; END IF;
      SELECT EXISTS(
        SELECT 1 FROM public.delivery_messages m
        JOIN public.provider_operations p ON p.workspace_id=m.workspace_id AND p.id=m.operation_id
        JOIN public.delivery_liabilities l ON l.workspace_id=m.workspace_id AND l.message_id=m.id AND l.operation_id=p.id
        JOIN public.budget_reservations b ON b.workspace_id=l.workspace_id AND b.id=l.reservation_id AND b.operation_id=p.id
        JOIN public.outbox_events o ON o.workspace_id=m.workspace_id AND o.id=NEW.outbox_id
        WHERE m.workspace_id=NEW.workspace_id AND m.id=NEW.message_id
          AND m.state='prepared' AND m.provider_ref IS NULL AND p.status='intent'
          AND p.capability='delivery' AND p.intent_key=m.intent_key AND p.input_hash=m.payload_digest
          AND p.provider_name=m.provider_name AND p.account_reference=m.account_reference
          AND o.event_type='delivery.submit' AND o.state='ready' AND o.intent_key=m.intent_key
          AND o.payload=jsonb_build_object('workspace_id',m.workspace_id::text,'message_id',m.id::text,'operation_id',p.id::text,'scope_hash',NEW.scope_hash)
          AND scope->>'workspace_id'=m.workspace_id::text AND scope->>'project_id'=m.project_id::text
          AND scope->>'sender_identity_id'=m.sender_identity_id::text
          AND scope->'recipient_refs' @> jsonb_build_array(m.recipient_ref::text)
          AND scope->>'provider_name'=m.provider_name AND scope->>'account_reference'=m.account_reference
          AND (scope->>'upper_bound')::numeric=l.max_liability AND l.max_liability>0
          AND scope->>'currency'=l.currency AND scope->>'pricing_version'=l.pricing_version
          AND b.state='active' AND b.upper_bound=l.max_liability AND b.remaining_hold=b.upper_bound
          AND b.currency=l.currency AND b.price_version=l.pricing_version
          AND (SELECT count(*) FROM public.budget_reservation_allocations x WHERE x.workspace_id=b.workspace_id AND x.reservation_id=b.id)=3
          AND NOT EXISTS(SELECT 1 FROM public.budget_reservation_allocations x
            JOIN public.budget_accounts a ON a.workspace_id=x.workspace_id AND a.id=x.account_id
            WHERE x.workspace_id=b.workspace_id AND x.reservation_id=b.id
              AND NOT ((a.scope='workspace' AND a.scope_id=m.workspace_id AND a.category='all')
                OR (a.scope='project' AND a.scope_id=m.project_id AND a.category='all')
                OR (a.scope='category' AND a.scope_id=m.project_id AND a.category='delivery')))
      ) INTO bound;
      IF NOT bound THEN RAISE EXCEPTION 'delivery authority requires exact original message liability and paid outbox' USING ERRCODE='23503'; END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER delivery_authorization_guard BEFORE INSERT OR UPDATE ON delivery_authorizations FOR EACH ROW EXECUTE FUNCTION guard_delivery_authorization();
    REVOKE ALL ON FUNCTION guard_delivery_authorization() FROM PUBLIC,buyeros_api,buyeros_worker;
    """)
    _receipt_guard(revision)

def downgrade():
    if op.get_bind().execute(sa.text('SELECT EXISTS(SELECT 1 FROM delivery_authorizations)')).scalar_one():
        raise RuntimeError('0050 downgrade blocked: retain original delivery authority and paid outbox bindings')
    op.drop_table('delivery_authorizations')
    op.execute('DROP FUNCTION guard_delivery_authorization()')
    _receipt_guard(down_revision)
