"""Expand independent delivery metadata/ledger; populated rollback retains history."""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision='0048_c61_delivery_ledger'
down_revision='0047_c61_legacy_source_privacy'
branch_labels=depends_on=None
MONEY=sa.Numeric(18,6)
STATES="'prepared','submitting','unknown','accepted','delivered','bounced','complained','unsubscribed','failed','rejected'"

def scoped_fk(column,table,name):
    return sa.ForeignKeyConstraint(['workspace_id',column],[table+'.workspace_id',table+'.id'],name=name)

def _base():
    return [sa.Column('id',UUID(as_uuid=True),primary_key=True),sa.Column('workspace_id',UUID(as_uuid=True),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now())]

def _receipt_guard(head):
    for service in ('search','model','contact'):
        op.execute(f"CREATE OR REPLACE FUNCTION public.buyeros_{service}_receipts_writable() RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$ SELECT COALESCE((SELECT version_num='{head}' FROM public.alembic_version),false) $$")

def upgrade():
    op.create_table('delivery_messages',*_base(),
        sa.Column('project_id',UUID(as_uuid=True),nullable=False),
        sa.Column('draft_id',UUID(as_uuid=True),nullable=False),
        sa.Column('draft_revision_id',UUID(as_uuid=True),nullable=False),
        sa.Column('revision_number',sa.Integer,nullable=False),
        sa.Column('recipient_ref',UUID(as_uuid=True),nullable=False),
        sa.Column('sender_identity_id',UUID(as_uuid=True),nullable=False),
        sa.Column('approval_id',UUID(as_uuid=True),nullable=False),
        sa.Column('actor_id',UUID(as_uuid=True),nullable=False),
        sa.Column('operation_id',UUID(as_uuid=True),nullable=False),
        sa.Column('intent_key',sa.String(128),nullable=False),
        sa.Column('provider_name',sa.String(64),nullable=False),
        sa.Column('account_reference',sa.String(128),nullable=False),
        sa.Column('payload_digest',sa.String(64),nullable=False),
        sa.Column('state',sa.String(32),nullable=False),
        sa.Column('provider_ref',sa.String(200),nullable=True),
        sa.UniqueConstraint('workspace_id','id',name='uq_delivery_messages_workspace_id'),
        sa.UniqueConstraint('workspace_id','intent_key',name='uq_delivery_messages_intent'),
        sa.UniqueConstraint('workspace_id','operation_id',name='uq_delivery_messages_operation'),
        sa.UniqueConstraint('provider_name','account_reference','provider_ref',name='uq_delivery_messages_provider_ref'),
        sa.ForeignKeyConstraint(['workspace_id'],['workspaces.id'],name='fk_delivery_messages_workspace'),
        scoped_fk('project_id','projects','fk_delivery_messages_project'),
        scoped_fk('draft_id','outreach_drafts','fk_delivery_messages_draft'),
        sa.ForeignKeyConstraint(['workspace_id','draft_id','revision_number','draft_revision_id'],['draft_revisions.workspace_id','draft_revisions.draft_id','draft_revisions.revision_number','draft_revisions.id'],name='fk_delivery_messages_exact_revision'),
        scoped_fk('recipient_ref','contact_points','fk_delivery_messages_recipient'),
        sa.ForeignKeyConstraint(['workspace_id','project_id','sender_identity_id'],['sender_identity_versions.workspace_id','sender_identity_versions.project_id','sender_identity_versions.id'],name='fk_delivery_messages_sender'),
        scoped_fk('approval_id','approvals','fk_delivery_messages_approval'),
        scoped_fk('operation_id','provider_operations','fk_delivery_messages_operation'),
        sa.ForeignKeyConstraint(['actor_id'],['users.id'],name='fk_delivery_messages_actor'),
        sa.CheckConstraint('state IN ('+STATES+')',name='state'),
        sa.CheckConstraint('revision_number>0',name='revision'),
        sa.CheckConstraint("payload_digest ~ '^[0-9a-f]{64}$'",name='digest'),
        sa.CheckConstraint("intent_key ~ '^[A-Za-z0-9:_/-]{1,128}$' AND provider_name ~ '^[A-Za-z0-9_-]{1,64}$' AND account_reference ~ '^[A-Za-z0-9:_/-]{1,128}$' AND (provider_ref IS NULL OR provider_ref ~ '^[A-Za-z0-9:_/-]{1,200}$')",name='opaque'),
        sa.Index('ix_delivery_messages_project','workspace_id','project_id'),
        sa.Index('ix_delivery_messages_draft','workspace_id','draft_id','revision_number','draft_revision_id'),
        sa.Index('ix_delivery_messages_recipient','workspace_id','recipient_ref'),
        sa.Index('ix_delivery_messages_sender','workspace_id','project_id','sender_identity_id'),
        sa.Index('ix_delivery_messages_approval','workspace_id','approval_id'),
        sa.Index('ix_delivery_messages_actor','actor_id'),
    )
    op.create_table('delivery_events',*_base(),
        sa.Column('message_id',UUID(as_uuid=True),nullable=False),
        sa.Column('provider_name',sa.String(64),nullable=False),
        sa.Column('account_reference',sa.String(128),nullable=False),
        sa.Column('external_event_id',sa.String(200),nullable=False),
        sa.Column('provider_ref',sa.String(200),nullable=False),
        sa.Column('state',sa.String(32),nullable=False),
        sa.Column('body_digest',sa.String(64),nullable=False),
        sa.Column('occurred_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('workspace_id','id',name='uq_delivery_events_workspace_id'),
        sa.UniqueConstraint('provider_name','account_reference','external_event_id',name='uq_delivery_events_external'),
        sa.ForeignKeyConstraint(['workspace_id'],['workspaces.id'],name='fk_delivery_events_workspace'),
        scoped_fk('message_id','delivery_messages','fk_delivery_events_message'),
        sa.CheckConstraint("state IN ('accepted','delivered','bounced','complained','unsubscribed','failed','rejected')",name='state'),
        sa.CheckConstraint("body_digest ~ '^[0-9a-f]{64}$'",name='digest'),
        sa.CheckConstraint("provider_name ~ '^[A-Za-z0-9_-]{1,64}$' AND account_reference ~ '^[A-Za-z0-9:_/-]{1,128}$' AND external_event_id ~ '^[A-Za-z0-9:_/-]{1,200}$' AND provider_ref ~ '^[A-Za-z0-9:_/-]{1,200}$'",name='opaque'),
        sa.Index('ix_delivery_events_message','workspace_id','message_id'),
    )
    op.create_table('delivery_liabilities',*_base(),
        sa.Column('message_id',UUID(as_uuid=True),nullable=False),
        sa.Column('operation_id',UUID(as_uuid=True),nullable=False),
        sa.Column('reservation_id',UUID(as_uuid=True),nullable=False),
        sa.Column('max_liability',MONEY,nullable=False),
        sa.Column('currency',sa.String(8),nullable=False),
        sa.Column('pricing_version',sa.String(64),nullable=False),
        sa.UniqueConstraint('workspace_id','id',name='uq_delivery_liabilities_workspace_id'),
        sa.UniqueConstraint('workspace_id','message_id',name='uq_delivery_liabilities_message'),
        sa.UniqueConstraint('workspace_id','reservation_id',name='uq_delivery_liabilities_reservation'),
        sa.ForeignKeyConstraint(['workspace_id'],['workspaces.id'],name='fk_delivery_liabilities_workspace'),
        scoped_fk('message_id','delivery_messages','fk_delivery_liabilities_message'),
        scoped_fk('operation_id','provider_operations','fk_delivery_liabilities_operation'),
        scoped_fk('reservation_id','budget_reservations','fk_delivery_liabilities_reservation'),
        sa.CheckConstraint("max_liability>=0 AND currency='USD'",name='money'),
        sa.CheckConstraint("pricing_version ~ '^[A-Za-z0-9:_/-]{1,64}$'",name='pricing'),
        sa.Index('ix_delivery_liabilities_operation','workspace_id','operation_id'),
    )
    for table in ('delivery_messages','delivery_events','delivery_liabilities'):
        op.execute(f"CREATE INDEX ix_{table}_workspace_id ON {table}(workspace_id)")
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY {table}_tenant ON {table} USING (workspace_id=NULLIF(current_setting('app.workspace_id',true),'')::uuid) WITH CHECK (workspace_id=NULLIF(current_setting('app.workspace_id',true),'')::uuid)")
        op.execute(f"REVOKE ALL ON {table} FROM PUBLIC,buyeros_api,buyeros_worker")
        op.execute(f"GRANT SELECT,INSERT ON {table} TO buyeros_api,buyeros_worker")
    op.execute("GRANT UPDATE(state,provider_ref,updated_at) ON delivery_messages TO buyeros_api,buyeros_worker")
    op.execute("""
    CREATE FUNCTION guard_delivery_message() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$
    BEGIN
      IF TG_OP='INSERT' THEN
        IF NEW.state<>'prepared' OR NEW.provider_ref IS NOT NULL THEN
          RAISE EXCEPTION 'delivery starts prepared without provider acceptance' USING ERRCODE='23514';
        END IF;
        IF NOT EXISTS(SELECT 1 FROM public.approvals a JOIN public.outreach_drafts d ON d.workspace_id=a.workspace_id AND d.id=a.draft_id
          WHERE a.workspace_id=NEW.workspace_id AND a.id=NEW.approval_id AND a.draft_id=NEW.draft_id
          AND a.draft_revision_id=NEW.draft_revision_id AND a.revision_number=NEW.revision_number
          AND a.recipient_contact_id=NEW.recipient_ref AND a.context_snapshot#>>'{sender,id}'=NEW.sender_identity_id::text
          AND a.invalidated_reason IS NULL AND a.invalidated_at IS NULL AND a.approved_at IS NOT NULL
          AND d.project_id=NEW.project_id AND d.current_revision=NEW.revision_number AND d.state='approved')
        THEN RAISE EXCEPTION 'delivery requires exact current approval' USING ERRCODE='23514'; END IF;
        IF NOT EXISTS(SELECT 1 FROM public.provider_operations p WHERE p.workspace_id=NEW.workspace_id AND p.id=NEW.operation_id
          AND p.capability='delivery' AND p.intent_key=NEW.intent_key AND p.input_hash=NEW.payload_digest
          AND p.provider_name=NEW.provider_name AND p.account_reference=NEW.account_reference AND p.status='intent')
        THEN RAISE EXCEPTION 'delivery requires original operation binding' USING ERRCODE='23514'; END IF;
      ELSE
        IF (to_jsonb(NEW)-'state'-'provider_ref'-'updated_at') IS DISTINCT FROM (to_jsonb(OLD)-'state'-'provider_ref'-'updated_at')
          OR (OLD.provider_ref IS NOT NULL AND NEW.provider_ref IS DISTINCT FROM OLD.provider_ref)
        THEN RAISE EXCEPTION 'delivery original binding is immutable' USING ERRCODE='23514'; END IF;
        IF NEW.state IS DISTINCT FROM OLD.state AND NOT (CASE OLD.state
          WHEN 'prepared' THEN NEW.state IN ('submitting','rejected')
          WHEN 'submitting' THEN NEW.state IN ('unknown','accepted','delivered','bounced','complained','failed','rejected')
          WHEN 'unknown' THEN NEW.state IN ('accepted','delivered','bounced','complained','unsubscribed','failed')
          WHEN 'accepted' THEN NEW.state IN ('delivered','bounced','complained','unsubscribed','failed')
          WHEN 'delivered' THEN NEW.state IN ('bounced','complained','unsubscribed')
          WHEN 'bounced' THEN NEW.state IN ('complained','unsubscribed')
          WHEN 'complained' THEN NEW.state='unsubscribed' ELSE false END)
        THEN RAISE EXCEPTION 'delivery state cannot regress or resubmit' USING ERRCODE='23514'; END IF;
        IF NEW.state IN ('prepared','submitting','rejected') AND NEW.provider_ref IS NOT NULL
          OR NEW.state IN ('accepted','delivered','bounced','complained','unsubscribed') AND NEW.provider_ref IS NULL
        THEN RAISE EXCEPTION 'delivery acceptance requires original provider reference' USING ERRCODE='23514'; END IF;
      END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER delivery_message_guard BEFORE INSERT OR UPDATE ON delivery_messages FOR EACH ROW EXECUTE FUNCTION guard_delivery_message();
    REVOKE ALL ON FUNCTION guard_delivery_message() FROM PUBLIC,buyeros_api,buyeros_worker;

    CREATE FUNCTION guard_delivery_event() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$
    BEGIN
      IF NOT EXISTS(SELECT 1 FROM public.delivery_messages m WHERE m.workspace_id=NEW.workspace_id AND m.id=NEW.message_id
        AND m.provider_name=NEW.provider_name AND m.account_reference=NEW.account_reference AND m.provider_ref=NEW.provider_ref)
      THEN RAISE EXCEPTION 'delivery event requires original scoped provider reference' USING ERRCODE='23503'; END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER delivery_event_guard BEFORE INSERT ON delivery_events FOR EACH ROW EXECUTE FUNCTION guard_delivery_event();
    REVOKE ALL ON FUNCTION guard_delivery_event() FROM PUBLIC,buyeros_api,buyeros_worker;

    CREATE FUNCTION guard_delivery_liability() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$
    BEGIN
      IF NOT EXISTS(SELECT 1 FROM public.delivery_messages m JOIN public.budget_reservations b
        ON b.workspace_id=m.workspace_id AND b.operation_id=m.operation_id WHERE m.workspace_id=NEW.workspace_id
        AND m.id=NEW.message_id AND m.operation_id=NEW.operation_id AND b.id=NEW.reservation_id
        AND b.upper_bound=NEW.max_liability AND b.currency=NEW.currency AND b.price_version=NEW.pricing_version)
      THEN RAISE EXCEPTION 'delivery liability requires exact reserved operation' USING ERRCODE='23503'; END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER delivery_liability_guard BEFORE INSERT ON delivery_liabilities FOR EACH ROW EXECUTE FUNCTION guard_delivery_liability();
    REVOKE ALL ON FUNCTION guard_delivery_liability() FROM PUBLIC,buyeros_api,buyeros_worker;
    """)
    _receipt_guard(revision)

def downgrade():
    # History/unknown holds survive application rollback. Destructive removal
    # is permitted only before admission has ever populated these tables.
    for table in ('delivery_events','delivery_liabilities','delivery_messages'):
        if op.get_bind().execute(sa.text(f'SELECT EXISTS(SELECT 1 FROM {table})')).scalar_one():
            raise RuntimeError('0048 downgrade blocked: retain delivery history and liabilities')
    for table in ('delivery_events','delivery_liabilities','delivery_messages'):
        op.drop_table(table)
    for function in ('guard_delivery_event','guard_delivery_liability','guard_delivery_message'):
        op.execute(f'DROP FUNCTION {function}()')
    _receipt_guard(down_revision)
