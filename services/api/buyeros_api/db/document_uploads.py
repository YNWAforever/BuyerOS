"""Tenant-bound immutable staging and source-page records."""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKeyConstraint, Integer, LargeBinary, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TenantMixin


class DocumentUpload(Base, TenantMixin):
    __tablename__ = 'document_uploads'
    __table_args__ = (
        UniqueConstraint('workspace_id', 'id'),
        ForeignKeyConstraint(['workspace_id', 'project_id'], ['projects.workspace_id', 'projects.id'], ondelete='CASCADE', name='fk_document_uploads_project'),
        ForeignKeyConstraint(['actor_user_id'], ['users.id'], name='fk_document_uploads_actor'),
        ForeignKeyConstraint(['workspace_id', 'project_id', 'document_id'], ['offer_documents.workspace_id', 'offer_documents.project_id', 'offer_documents.id'], ondelete='CASCADE', name='fk_document_uploads_document'),
    )
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    media_type: Mapped[str] = mapped_column(String(128), nullable=False)
    byte_length: Mapped[int] = mapped_column(Integer, nullable=False)
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    chunk_size: Mapped[int] = mapped_column(Integer, nullable=False, default=2097152)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default='uploading')
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default='1')


class DocumentUploadChunk(Base):
    __tablename__ = 'document_upload_chunks'
    __table_args__ = (ForeignKeyConstraint(['workspace_id', 'upload_id'], ['document_uploads.workspace_id', 'document_uploads.id'], ondelete='CASCADE'),)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    upload_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    chunk_index: Mapped[int] = mapped_column(Integer, primary_key=True)
    body: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)


class DocumentSlide(Base):
    __tablename__ = 'document_slides'
    __table_args__ = (ForeignKeyConstraint(['workspace_id', 'project_id', 'document_id'], ['offer_documents.workspace_id', 'offer_documents.project_id', 'offer_documents.id'], ondelete='CASCADE'),)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    slide_number: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    classification: Mapped[str] = mapped_column(String(16), nullable=False)
