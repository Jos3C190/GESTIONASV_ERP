"""Phase 5: geographic catalogues, companies, branches and warehouses."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def _id() -> sa.Column:
    return sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()"))


def _timestamps() -> list[sa.Column]:
    return [sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now())]


def _address_columns() -> list[sa.Column]:
    return [sa.Column("department_id", UUID(as_uuid=True), sa.ForeignKey("geographic_departments.id", ondelete="RESTRICT"), nullable=False), sa.Column("municipality_id", UUID(as_uuid=True), sa.ForeignKey("municipalities.id", ondelete="RESTRICT"), nullable=False), sa.Column("district_id", UUID(as_uuid=True), sa.ForeignKey("districts.id", ondelete="RESTRICT"), nullable=False)]


def upgrade() -> None:
    op.create_table("geographic_departments", _id(), sa.Column("name", sa.String(120), nullable=False), sa.UniqueConstraint("name", name="uq_geographic_departments_name"))
    op.create_table("municipalities", _id(), sa.Column("department_id", UUID(as_uuid=True), sa.ForeignKey("geographic_departments.id", ondelete="RESTRICT"), nullable=False), sa.Column("name", sa.String(120), nullable=False), sa.UniqueConstraint("department_id", "name", name="uq_municipalities_department_name"))
    op.create_table("districts", _id(), sa.Column("municipality_id", UUID(as_uuid=True), sa.ForeignKey("municipalities.id", ondelete="RESTRICT"), nullable=False), sa.Column("name", sa.String(120), nullable=False), sa.UniqueConstraint("municipality_id", "name", name="uq_districts_municipality_name"))
    op.create_table("companies", _id(), sa.Column("name", sa.String(200), nullable=False), sa.Column("commercial_name", sa.String(200), nullable=False), sa.Column("nit", sa.String(32), nullable=False), sa.Column("nrc", sa.String(32), nullable=False), sa.Column("commercial_line_1", sa.String(200)), sa.Column("commercial_line_2", sa.String(200)), sa.Column("commercial_line_3", sa.String(200)), sa.Column("address", sa.Text, nullable=False), *_address_columns(), sa.Column("phone", sa.String(32)), sa.Column("email", sa.String(320)), sa.Column("web_site", sa.String(2048)), sa.Column("logo", sa.String(2048)), sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")), *_timestamps(), sa.UniqueConstraint("nit", name="uq_companies_nit"), sa.UniqueConstraint("nrc", name="uq_companies_nrc"))
    op.create_table("branches", _id(), sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False), sa.Column("name", sa.String(200), nullable=False), sa.Column("address", sa.Text, nullable=False), *_address_columns(), sa.Column("phone", sa.String(32)), sa.Column("email", sa.String(320)), sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")), *_timestamps(), sa.UniqueConstraint("company_id", "name", name="uq_branches_company_name"))
    op.create_table("warehouse_categories", _id(), sa.Column("name", sa.String(120), nullable=False), sa.Column("description", sa.Text), sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")), *_timestamps(), sa.UniqueConstraint("name", name="uq_warehouse_categories_name"))
    op.create_table("warehouses", _id(), sa.Column("branch_id", UUID(as_uuid=True), sa.ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False), sa.Column("warehouse_category_id", UUID(as_uuid=True), sa.ForeignKey("warehouse_categories.id", ondelete="RESTRICT"), nullable=False), sa.Column("name", sa.String(200), nullable=False), sa.Column("description", sa.Text), sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")), *_timestamps(), sa.UniqueConstraint("branch_id", "name", name="uq_warehouses_branch_name"))
    op.create_table("locations", _id(), sa.Column("warehouse_id", UUID(as_uuid=True), sa.ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False), sa.Column("code", sa.String(120), nullable=False), sa.Column("aisle", sa.String(64), nullable=False), sa.Column("rack", sa.String(64), nullable=False), sa.Column("level", sa.String(64), nullable=False), sa.Column("position", sa.String(64), nullable=False), sa.Column("capacity", sa.Integer, nullable=False), sa.Column("notes", sa.Text), sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")), *_timestamps(), sa.CheckConstraint("capacity > 0", name="ck_locations_capacity_positive"), sa.UniqueConstraint("warehouse_id", "code", name="uq_locations_warehouse_code"), sa.UniqueConstraint("warehouse_id", "aisle", "rack", "level", "position", name="uq_locations_warehouse_coordinates"))


def downgrade() -> None:
    for table in ("locations", "warehouses", "warehouse_categories", "branches", "companies", "districts", "municipalities", "geographic_departments"):
        op.drop_table(table)
