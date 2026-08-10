"""ORM models: Role, Permission, RolePermission, UserRole."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPKMixin


class Permission(UUIDPKMixin, SoftDeleteMixin, Base):
    __tablename__ = "permissions"

    code: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    module: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    __table_args__ = (
        Index(
            "uq_permissions_code_visible",
            func.lower(code),
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        {"comment": "Permission catalogue (format: recurso:accion)."},
    )


class Role(UUIDPKMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "roles"

    company_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    is_system: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false", default=False
    )
    __table_args__ = (
        Index(
            "uq_roles_company_name_visible",
            "company_id",
            func.lower(name),
            unique=True,
            postgresql_where=text("company_id IS NOT NULL AND deleted_at IS NULL"),
            sqlite_where=text("company_id IS NOT NULL AND deleted_at IS NULL"),
        ),
        Index(
            "uq_roles_global_name_visible",
            func.lower(name),
            unique=True,
            postgresql_where=text("company_id IS NULL AND deleted_at IS NULL"),
            sqlite_where=text("company_id IS NULL AND deleted_at IS NULL"),
        ),
        Index("ix_roles_company_deleted_at", "company_id", "deleted_at"),
        {"comment": "System role templates and company-owned custom roles."},
    )


class RolePermission(Base):
    """Association table role<->permission with optional ABAC conditions."""

    __tablename__ = "role_permissions"

    role_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )
    permission_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True
    )
    conditions: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class UserRole(Base):
    """Association table user<->role with audit of who assigned it."""

    __tablename__ = "user_roles"

    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id", "company_id"],
            ["user_companies.user_id", "user_companies.company_id"],
            ondelete="CASCADE",
            name="fk_user_roles_user_company",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, index=True
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )
    assigned_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
