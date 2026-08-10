"""Regression tests for the default ORM soft-delete visibility rule."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.infrastructure.db import session as _session_events  # noqa: F401
from app.infrastructure.db.base import SoftDeleteMixin
from sqlalchemy import String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column


class FilterTestBase(DeclarativeBase):
    pass


class FilterTestUser(FilterTestBase):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)


class FilterTestRecord(SoftDeleteMixin, FilterTestBase):
    __tablename__ = "soft_delete_filter_records"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)


def test_default_select_hides_deleted_records_and_explicit_opt_out_reveals_them() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    FilterTestBase.metadata.create_all(engine)
    active_id = uuid.uuid4()
    deleted_id = uuid.uuid4()

    with Session(engine) as session:
        session.add_all(
            [
                FilterTestRecord(id=active_id, name="Visible"),
                FilterTestRecord(
                    id=deleted_id,
                    name="Eliminado",
                    deleted_at=datetime.now(UTC),
                    deletion_reason="Duplicado",
                ),
            ]
        )
        session.commit()

        visible_ids = set(session.scalars(select(FilterTestRecord.id)).all())
        all_ids = set(
            session.scalars(
                select(FilterTestRecord.id).execution_options(include_deleted=True)
            ).all()
        )

    assert visible_ids == {active_id}
    assert all_ids == {active_id, deleted_id}


def test_global_filter_also_applies_to_primary_key_lookups_expressed_as_selects() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    FilterTestBase.metadata.create_all(engine)
    deleted_id = uuid.uuid4()

    with Session(engine) as session:
        session.add(
            FilterTestRecord(
                id=deleted_id,
                name="Eliminado",
                deleted_at=datetime.now(UTC),
            )
        )
        session.commit()

        hidden = session.scalar(
            select(FilterTestRecord).where(FilterTestRecord.id == deleted_id)
        )
        recoverable = session.scalar(
            select(FilterTestRecord)
            .where(FilterTestRecord.id == deleted_id)
            .execution_options(include_deleted=True)
        )

    assert hidden is None
    assert recoverable is not None
    assert recoverable.id == deleted_id
