"""Tenant-scoped, cross-replica API rate windows."""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class ApiRateWindow(Base):
    __tablename__ = "api_rate_windows"
    __table_args__ = (CheckConstraint("hits > 0", name="ck_api_rate_windows_positive_hits"),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    bucket: Mapped[str] = mapped_column(String(24), primary_key=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    hits: Mapped[int] = mapped_column(Integer, nullable=False)
