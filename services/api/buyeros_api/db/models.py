"""Core identity tables: workspaces, users and tenant memberships (BO-005)."""

import uuid

from sqlalchemy import Boolean, ForeignKeyConstraint, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TenantMixin, UUIDPk


class Workspace(Base, UUIDPk):
    __tablename__ = "workspaces"
    __table_args__ = (UniqueConstraint("id", name="uq_workspaces_id"),)

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    controller_scope: Mapped[str | None] = mapped_column(String(200), nullable=True)
    data_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="live")


class User(Base, UUIDPk):
    """A verified OIDC subject. Upserted by immutable (issuer, subject)."""

    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("issuer", "subject", name="uq_users_issuer_subject"),)

    issuer: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)


class Membership(Base, TenantMixin):
    """Server-side authority: roles come from here, never from token claims."""

    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_memberships_workspace_id"),
        UniqueConstraint("workspace_id", "user_id", name="uq_memberships_workspace_user"),
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_memberships_workspace"),
        ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_memberships_user"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    roles: Mapped[list[str]] = mapped_column(ARRAY(String(32)), nullable=False, default=list)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
