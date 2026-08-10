"""Infrastructure metadata persisted by migrations and bootstrap jobs."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class AppMeta(Base):
    """Application-level markers such as schema and first-setup versions."""

    __tablename__ = "app_meta"
    __table_args__ = (
        Index("ix_app_meta_key", "key", unique=True),
        {"comment": "Key/value store for app-level metadata (schema version markers, etc.)."},
    )

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, server_default=func.now()
    )
