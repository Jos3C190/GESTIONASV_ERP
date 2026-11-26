"""Punto de venta: cajas, turnos, efectivo, arqueos, depósitos y PIN de supervisor (revisión 0146, V6a).

Las restricciones de negocio (estados, montos, inmutabilidad) viven en la migración; aquí se reflejan
las columnas, llaves y unicidades que usa el ORM.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    PrimaryKeyConstraint,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


def _id() -> Mapped[uuid.UUID]:
    return mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )


def _company() -> Mapped[uuid.UUID]:
    return mapped_column(
        PGUUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )


def _user(nullable: bool = False) -> Mapped[uuid.UUID]:
    return mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=nullable
    )


def _now() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


def _money(nullable: bool = True) -> Mapped[Decimal]:
    return mapped_column(Numeric(12, 2), nullable=nullable)


class PosRegisterModel(Base):
    __tablename__ = "pos_registers"

    id: Mapped[uuid.UUID] = _id()
    company_id: Mapped[uuid.UUID] = _company()
    branch_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    establishment_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    point_of_sale_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    opening_float: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="0"
    )
    cash_out_approval_threshold: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="20"
    )
    cash_drawer_limit: Mapped[Decimal | None] = _money()
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    created_by_id: Mapped[uuid.UUID] = _user()
    updated_by_id: Mapped[uuid.UUID] = _user()
    created_at: Mapped[datetime] = _now()
    updated_at: Mapped[datetime] = _now()

    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_pos_registers_company_id"),
        UniqueConstraint(
            "company_id", "id", "branch_id", name="uq_pos_registers_company_id_branch"
        ),
        UniqueConstraint("company_id", "code", name="uq_pos_registers_code"),
        UniqueConstraint("company_id", "point_of_sale_id", name="uq_pos_registers_point_of_sale"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            name="fk_pos_registers_branch",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "establishment_id", "branch_id"],
            [
                "fiscal_establishments.company_id",
                "fiscal_establishments.id",
                "fiscal_establishments.branch_id",
            ],
            name="fk_pos_registers_establishment",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "establishment_id", "point_of_sale_id"],
            [
                "fiscal_points_of_sale.company_id",
                "fiscal_points_of_sale.establishment_id",
                "fiscal_points_of_sale.id",
            ],
            name="fk_pos_registers_point_of_sale",
            ondelete="RESTRICT",
        ),
    )


class PosShiftModel(Base):
    __tablename__ = "pos_shifts"

    id: Mapped[uuid.UUID] = _id()
    company_id: Mapped[uuid.UUID] = _company()
    branch_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    register_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    cashier_id: Mapped[uuid.UUID] = _user()
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, server_default="open")
    opening_float: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    opened_at: Mapped[datetime] = _now()
    counted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    recount_reason: Mapped[str | None] = mapped_column(String(300))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by_id: Mapped[uuid.UUID | None] = _user(nullable=True)
    approval_notes: Mapped[str | None] = mapped_column(String(300))
    expected_cash: Mapped[Decimal | None] = _money()
    counted_cash: Mapped[Decimal | None] = _money()
    cash_difference: Mapped[Decimal | None] = _money()
    expected_card: Mapped[Decimal | None] = _money()
    declared_card: Mapped[Decimal | None] = _money()
    expected_transfer: Mapped[Decimal | None] = _money()
    declared_transfer: Mapped[Decimal | None] = _money()
    retained_float: Mapped[Decimal | None] = _money()
    cash_to_deposit: Mapped[Decimal | None] = _money()
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)

    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_pos_shifts_company_id"),
        UniqueConstraint("company_id", "id", "branch_id", name="uq_pos_shifts_company_id_branch"),
        UniqueConstraint("company_id", "number", name="uq_pos_shifts_number"),
        UniqueConstraint("company_id", "idempotency_key", name="uq_pos_shifts_idempotency"),
        ForeignKeyConstraint(
            ["company_id", "register_id", "branch_id"],
            ["pos_registers.company_id", "pos_registers.id", "pos_registers.branch_id"],
            name="fk_pos_shifts_register",
            ondelete="RESTRICT",
        ),
    )


class PosCashMovementModel(Base):
    __tablename__ = "pos_cash_movements"

    id: Mapped[uuid.UUID] = _id()
    company_id: Mapped[uuid.UUID] = _company()
    shift_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    reason: Mapped[str] = mapped_column(String(200), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(60))
    authorized_by_id: Mapped[uuid.UUID | None] = _user(nullable=True)
    created_by_id: Mapped[uuid.UUID] = _user()
    created_at: Mapped[datetime] = _now()
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)

    __table_args__ = (
        UniqueConstraint("company_id", "idempotency_key", name="uq_pos_cash_movements_idempotency"),
        ForeignKeyConstraint(
            ["company_id", "shift_id"],
            ["pos_shifts.company_id", "pos_shifts.id"],
            name="fk_pos_cash_movements_shift",
            ondelete="RESTRICT",
        ),
    )


class PosShiftCountModel(Base):
    __tablename__ = "pos_shift_counts"

    id: Mapped[uuid.UUID] = _id()
    company_id: Mapped[uuid.UUID] = _company()
    shift_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    kind: Mapped[str] = mapped_column(String(8), nullable=False)
    sequence: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    cash_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    card_total: Mapped[Decimal | None] = _money()
    transfer_total: Mapped[Decimal | None] = _money()
    notes: Mapped[str | None] = mapped_column(String(300))
    counted_by_id: Mapped[uuid.UUID] = _user()
    counted_at: Mapped[datetime] = _now()

    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_pos_shift_counts_company_id"),
        UniqueConstraint(
            "company_id", "shift_id", "kind", "sequence", name="uq_pos_shift_counts_sequence"
        ),
        ForeignKeyConstraint(
            ["company_id", "shift_id"],
            ["pos_shifts.company_id", "pos_shifts.id"],
            name="fk_pos_shift_counts_shift",
            ondelete="RESTRICT",
        ),
    )


class PosShiftCountLineModel(Base):
    __tablename__ = "pos_shift_count_lines"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    count_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    form: Mapped[str] = mapped_column(String(4), nullable=False)
    denomination: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("company_id", "count_id", "form", "denomination"),
        ForeignKeyConstraint(
            ["company_id", "count_id"],
            ["pos_shift_counts.company_id", "pos_shift_counts.id"],
            name="fk_pos_shift_count_lines_count",
            ondelete="RESTRICT",
        ),
    )


class PosDepositModel(Base):
    __tablename__ = "pos_deposits"

    id: Mapped[uuid.UUID] = _id()
    company_id: Mapped[uuid.UUID] = _company()
    branch_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    deposited_on: Mapped[date] = mapped_column(Date, nullable=False)
    bank_name: Mapped[str] = mapped_column(String(80), nullable=False)
    account_reference: Mapped[str] = mapped_column(String(40), nullable=False)
    slip_number: Mapped[str] = mapped_column(String(40), nullable=False)
    expected_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    deposited_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    difference: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    notes: Mapped[str | None] = mapped_column(String(300))
    created_by_id: Mapped[uuid.UUID] = _user()
    created_at: Mapped[datetime] = _now()
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)

    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_pos_deposits_company_id"),
        UniqueConstraint("company_id", "number", name="uq_pos_deposits_number"),
        UniqueConstraint("company_id", "bank_name", "slip_number", name="uq_pos_deposits_slip"),
        UniqueConstraint("company_id", "idempotency_key", name="uq_pos_deposits_idempotency"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            name="fk_pos_deposits_branch",
            ondelete="RESTRICT",
        ),
    )


class PosDepositShiftModel(Base):
    __tablename__ = "pos_deposit_shifts"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    deposit_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    shift_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("company_id", "deposit_id", "shift_id"),
        UniqueConstraint("company_id", "shift_id", name="uq_pos_deposit_shifts_shift"),
        ForeignKeyConstraint(
            ["company_id", "deposit_id"],
            ["pos_deposits.company_id", "pos_deposits.id"],
            name="fk_pos_deposit_shifts_deposit",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "shift_id", "branch_id"],
            ["pos_shifts.company_id", "pos_shifts.id", "pos_shifts.branch_id"],
            name="fk_pos_deposit_shifts_shift",
            ondelete="RESTRICT",
        ),
    )


class PosSupervisorPinModel(Base):
    __tablename__ = "pos_supervisor_pins"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    pin_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    failed_attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = _now()
