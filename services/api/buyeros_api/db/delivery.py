"""Delivery metadata and immutable ledger bindings; no duplicate email content."""
import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import CheckConstraint, DateTime, ForeignKeyConstraint, Integer, String, Text, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, TenantMixin
from .budget import MONEY

STATES="'prepared','submitting','unknown','accepted','delivered','bounced','complained','unsubscribed','failed','rejected'"

def scoped_fk(column, table, name):
    return ForeignKeyConstraint(['workspace_id',column],[table+'.workspace_id',table+'.id'],name=name)

class DeliveryMessage(Base,TenantMixin):
    __tablename__='delivery_messages'
    __table_args__=(
        UniqueConstraint('workspace_id','id',name='uq_delivery_messages_workspace_id'),
        UniqueConstraint('workspace_id','intent_key',name='uq_delivery_messages_intent'),
        UniqueConstraint('workspace_id','operation_id',name='uq_delivery_messages_operation'),
        UniqueConstraint('provider_name','account_reference','provider_ref',name='uq_delivery_messages_provider_ref'),
        ForeignKeyConstraint(['workspace_id'],['workspaces.id'],name='fk_delivery_messages_workspace'),
        scoped_fk('project_id','projects','fk_delivery_messages_project'),
        scoped_fk('draft_id','outreach_drafts','fk_delivery_messages_draft'),
        ForeignKeyConstraint(['workspace_id','draft_id','revision_number','draft_revision_id'],['draft_revisions.workspace_id','draft_revisions.draft_id','draft_revisions.revision_number','draft_revisions.id'],name='fk_delivery_messages_exact_revision'),
        scoped_fk('recipient_ref','contact_points','fk_delivery_messages_recipient'),
        ForeignKeyConstraint(['workspace_id','project_id','sender_identity_id'],['sender_identity_versions.workspace_id','sender_identity_versions.project_id','sender_identity_versions.id'],name='fk_delivery_messages_sender'),
        scoped_fk('approval_id','approvals','fk_delivery_messages_approval'),
        scoped_fk('operation_id','provider_operations','fk_delivery_messages_operation'),
        ForeignKeyConstraint(['actor_id'],['users.id'],name='fk_delivery_messages_actor'),
        CheckConstraint('state IN ('+STATES+')',name='state'),
        CheckConstraint('revision_number>0',name='revision'),
        CheckConstraint("payload_digest ~ '^[0-9a-f]{64}$'",name='digest'),
        CheckConstraint("intent_key ~ '^[A-Za-z0-9:_/-]{1,128}$' AND provider_name ~ '^[A-Za-z0-9_-]{1,64}$' AND account_reference ~ '^[A-Za-z0-9:_/-]{1,128}$' AND (provider_ref IS NULL OR provider_ref ~ '^[A-Za-z0-9:_/-]{1,200}$')",name='opaque'),
        Index('ix_delivery_messages_project','workspace_id','project_id'),
        Index('ix_delivery_messages_draft','workspace_id','draft_id','revision_number','draft_revision_id'),
        Index('ix_delivery_messages_recipient','workspace_id','recipient_ref'),
        Index('ix_delivery_messages_sender','workspace_id','project_id','sender_identity_id'),
        Index('ix_delivery_messages_approval','workspace_id','approval_id'),
        Index('ix_delivery_messages_actor','actor_id'),
    )
    project_id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),nullable=False)
    draft_id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),nullable=False)
    draft_revision_id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),nullable=False)
    revision_number:Mapped[int]=mapped_column(Integer,nullable=False)
    recipient_ref:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),nullable=False)
    sender_identity_id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),nullable=False)
    approval_id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),nullable=False)
    actor_id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),nullable=False)
    operation_id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),nullable=False)
    intent_key:Mapped[str]=mapped_column(String(128),nullable=False)
    provider_name:Mapped[str]=mapped_column(String(64),nullable=False)
    account_reference:Mapped[str]=mapped_column(String(128),nullable=False)
    payload_digest:Mapped[str]=mapped_column(String(64),nullable=False)
    state:Mapped[str]=mapped_column(String(32),nullable=False)
    provider_ref:Mapped[str|None]=mapped_column(String(200),nullable=True)

class DeliveryEvent(Base,TenantMixin):
    __tablename__='delivery_events'
    __table_args__=(
        UniqueConstraint('workspace_id','id',name='uq_delivery_events_workspace_id'),
        UniqueConstraint('provider_name','account_reference','external_event_id',name='uq_delivery_events_external'),
        ForeignKeyConstraint(['workspace_id'],['workspaces.id'],name='fk_delivery_events_workspace'),
        scoped_fk('message_id','delivery_messages','fk_delivery_events_message'),
        CheckConstraint("state IN ('accepted','delivered','bounced','complained','unsubscribed','failed','rejected')",name='state'),
        CheckConstraint("body_digest ~ '^[0-9a-f]{64}$'",name='digest'),
        CheckConstraint("provider_name ~ '^[A-Za-z0-9_-]{1,64}$' AND account_reference ~ '^[A-Za-z0-9:_/-]{1,128}$' AND external_event_id ~ '^[A-Za-z0-9:_/-]{1,200}$' AND provider_ref ~ '^[A-Za-z0-9:_/-]{1,200}$'",name='opaque'),
        Index('ix_delivery_events_message','workspace_id','message_id'),
    )
    message_id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),nullable=False)
    provider_name:Mapped[str]=mapped_column(String(64),nullable=False)
    account_reference:Mapped[str]=mapped_column(String(128),nullable=False)
    external_event_id:Mapped[str]=mapped_column(String(200),nullable=False)
    provider_ref:Mapped[str]=mapped_column(String(200),nullable=False)
    state:Mapped[str]=mapped_column(String(32),nullable=False)
    body_digest:Mapped[str]=mapped_column(String(64),nullable=False)
    occurred_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)

class DeliveryLiability(Base,TenantMixin):
    __tablename__='delivery_liabilities'
    __table_args__=(
        UniqueConstraint('workspace_id','id',name='uq_delivery_liabilities_workspace_id'),
        UniqueConstraint('workspace_id','message_id',name='uq_delivery_liabilities_message'),
        UniqueConstraint('workspace_id','reservation_id',name='uq_delivery_liabilities_reservation'),
        ForeignKeyConstraint(['workspace_id'],['workspaces.id'],name='fk_delivery_liabilities_workspace'),
        scoped_fk('message_id','delivery_messages','fk_delivery_liabilities_message'),
        scoped_fk('operation_id','provider_operations','fk_delivery_liabilities_operation'),
        scoped_fk('reservation_id','budget_reservations','fk_delivery_liabilities_reservation'),
        CheckConstraint("max_liability>=0 AND currency='USD'",name='money'),
        CheckConstraint("pricing_version ~ '^[A-Za-z0-9:_/-]{1,64}$'",name='pricing'),
        Index('ix_delivery_liabilities_operation','workspace_id','operation_id'),
    )
    message_id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),nullable=False)
    operation_id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),nullable=False)
    reservation_id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),nullable=False)
    max_liability:Mapped[Decimal]=mapped_column(MONEY,nullable=False)
    currency:Mapped[str]=mapped_column(String(8),nullable=False)
    pricing_version:Mapped[str]=mapped_column(String(64),nullable=False)


"""Append to existing delivery metadata after frozen-source verification ends."""

class DeliveryAuthorization(Base,TenantMixin):
    __tablename__='delivery_authorizations'
    __table_args__=(
        UniqueConstraint('workspace_id','id',name='uq_delivery_authorizations_workspace_id'),
        UniqueConstraint('workspace_id','message_id',name='uq_delivery_authorizations_message'),
        UniqueConstraint('workspace_id','outbox_id',name='uq_delivery_authorizations_outbox'),
        ForeignKeyConstraint(['workspace_id'],['workspaces.id'],name='fk_delivery_authorizations_workspace'),
        scoped_fk('message_id','delivery_messages','fk_delivery_authorizations_message'),
        scoped_fk('outbox_id','outbox_events','fk_delivery_authorizations_outbox'),
        CheckConstraint("scope_hash ~ '^[0-9a-f]{64}$' AND octet_length(scope_json) BETWEEN 1 AND 524288 AND scope_hash=encode(sha256(convert_to(scope_json,'UTF8')),'hex')",name='scope_digest'),
    )
    message_id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),nullable=False)
    outbox_id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),nullable=False)
    scope_hash:Mapped[str]=mapped_column(String(64),nullable=False)
    scope_json:Mapped[str]=mapped_column(Text,nullable=False)
    valid_until:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
