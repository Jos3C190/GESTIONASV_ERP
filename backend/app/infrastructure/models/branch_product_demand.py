"""Manually classified purchase-demand level for a product at a branch."""

from __future__ import annotations

import uuid

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, TimestampMixin, UUIDPKMixin


class BranchProductDemandLevelModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "branch_product_demand_levels"

    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    product_id: Mapped[int] = mapped_column(Integer, nullable=False)
    level: Mapped[str] = mapped_column(String(16), nullable=False)
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            name="fk_branch_product_demand_levels_branch_company",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["company_id", "product_id"],
            ["products.company_id", "products.id_product"],
            name="fk_branch_product_demand_levels_product_company",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "company_id",
            "branch_id",
            "product_id",
            name="uq_branch_product_demand_levels_scope_product",
        ),
        CheckConstraint("level IN ('low','medium','high')", name="ck_branch_product_demand_level"),
        Index(
            "ix_branch_product_demand_levels_branch_product",
            "company_id",
            "branch_id",
            "product_id",
        ),
    )
