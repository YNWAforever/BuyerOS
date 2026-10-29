"""Drive authorization metadata only. Credentials and content never belong here."""
import uuid
from sqlalchemy import Boolean, ForeignKey, ForeignKeyConstraint, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, TenantMixin


class DriveConnection(TenantMixin, Base):
    __tablename__ = 'conversation_drive_connections'
    __table_args__ = (
        UniqueConstraint('workspace_id', 'id'),
        UniqueConstraint('workspace_id', 'project_id'),
        ForeignKeyConstraint(['workspace_id', 'project_id'], ['projects.workspace_id', 'projects.id']),
    )
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    configured_by: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'), nullable=False)
    connected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    generation: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, default=uuid.uuid4)
    folders: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
