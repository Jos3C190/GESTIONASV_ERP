"""Enterprise multi-company context and operational branch/warehouse profiles."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_companies",
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "company_id",
            UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "assigned_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("user_id", "company_id", name="uq_user_companies_membership"),
    )
    op.create_index("ix_user_companies_company", "user_companies", ["company_id"])
    op.execute(
        "INSERT INTO user_companies (user_id, company_id) SELECT u.id, c.id FROM users u CROSS JOIN companies c ON CONFLICT DO NOTHING"
    )

    op.add_column("companies", sa.Column("description", sa.Text()))

    branch_columns = (
        sa.Column("code", sa.String(32)),
        sa.Column("latitude", sa.Numeric(9, 6)),
        sa.Column("longitude", sa.Numeric(9, 6)),
        sa.Column("operational_status", sa.String(20), nullable=False, server_default="active"),
        sa.Column(
            "manager_employee_id",
            UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="SET NULL"),
        ),
        sa.Column("opened_at", sa.Date()),
        sa.Column("description", sa.Text()),
        sa.Column("schedule", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("zone", sa.String(120)),
        sa.Column("services", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("facilities", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("images", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("area", sa.Numeric(12, 2)),
        sa.Column("area_built", sa.Numeric(12, 2)),
        sa.Column("area_unbuilt", sa.Numeric(12, 2)),
        sa.Column("floors", sa.Integer()),
        sa.Column("parking", sa.Integer()),
        sa.Column("people_capacity", sa.Integer()),
        sa.Column("property_type", sa.String(24)),
        sa.Column("offices", sa.Integer()),
        sa.Column("meeting_rooms", sa.Integer()),
        sa.Column("bathrooms", sa.Integer()),
        sa.Column("accesses", sa.Integer()),
        sa.Column("emergency_exits", sa.Integer()),
        sa.Column("accessibility", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("construction_type", sa.String(32)),
        sa.Column("construction_year", sa.Integer()),
        sa.Column("building_condition", sa.String(20)),
        sa.Column("cadastral_code", sa.String(80)),
        sa.Column("permit_expiry", sa.Date()),
        sa.Column("lease_expiry", sa.Date()),
        sa.Column("landlord", sa.String(200)),
        sa.Column("website", sa.String(2048)),
        sa.Column("cctv_cameras", sa.Integer()),
        sa.Column("access_control", sa.String(32)),
        sa.Column("has_alarm", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("fire_system", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column(
            "has_backup_generator", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("has_ups", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    for column in branch_columns:
        op.add_column("branches", column)
    op.create_check_constraint(
        "ck_branches_latitude", "branches", "latitude IS NULL OR latitude BETWEEN -90 AND 90"
    )
    op.create_check_constraint(
        "ck_branches_longitude", "branches", "longitude IS NULL OR longitude BETWEEN -180 AND 180"
    )
    op.create_check_constraint(
        "ck_branches_operational_status",
        "branches",
        "operational_status IN ('active','inactive','maintenance')",
    )
    op.create_unique_constraint("uq_branches_company_code", "branches", ["company_id", "code"])

    warehouse_columns = (
        sa.Column("code", sa.String(32)),
        sa.Column("warehouse_type", sa.String(32), nullable=False, server_default="general"),
        sa.Column("operational_status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("physical_location", sa.String(200)),
        sa.Column(
            "manager_employee_id",
            UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="SET NULL"),
        ),
        sa.Column("area", sa.Numeric(12, 2)),
        sa.Column("height", sa.Numeric(12, 2)),
        sa.Column("length", sa.Numeric(12, 2)),
        sa.Column("width", sa.Numeric(12, 2)),
        sa.Column("shelves_total", sa.Integer()),
        sa.Column("capacity", sa.Integer()),
        sa.Column("shifts", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("cameras", sa.Integer()),
        sa.Column("access_control", sa.String(32)),
        sa.Column("has_alarm", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("fire_system", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("last_security_audit", sa.Date()),
        sa.Column("temperature_range", sa.String(64)),
        sa.Column("humidity_range", sa.String(64)),
        sa.Column("cooling", sa.String(32)),
        sa.Column("has_ventilation", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("last_maintenance", sa.Date()),
        sa.Column("next_maintenance", sa.Date()),
        sa.Column("maintenance_notes", sa.Text()),
        sa.Column("sanitary_permit", sa.String(120)),
        sa.Column("sanitary_permit_expiry", sa.Date()),
        sa.Column("last_inspection", sa.Date()),
        sa.Column("certifications", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
    )
    for column in warehouse_columns:
        op.add_column("warehouses", column)
    op.create_check_constraint(
        "ck_warehouses_capacity", "warehouses", "capacity IS NULL OR capacity > 0"
    )
    op.create_check_constraint(
        "ck_warehouses_operational_status",
        "warehouses",
        "operational_status IN ('active','inactive','maintenance','full')",
    )
    op.create_unique_constraint("uq_warehouses_branch_code", "warehouses", ["branch_id", "code"])


def downgrade() -> None:
    op.drop_constraint("uq_warehouses_branch_code", "warehouses", type_="unique")
    op.drop_constraint("ck_warehouses_operational_status", "warehouses", type_="check")
    op.drop_constraint("ck_warehouses_capacity", "warehouses", type_="check")
    for name in (
        "certifications",
        "last_inspection",
        "sanitary_permit_expiry",
        "sanitary_permit",
        "maintenance_notes",
        "next_maintenance",
        "last_maintenance",
        "has_ventilation",
        "cooling",
        "humidity_range",
        "temperature_range",
        "last_security_audit",
        "fire_system",
        "has_alarm",
        "access_control",
        "cameras",
        "shifts",
        "capacity",
        "shelves_total",
        "width",
        "length",
        "height",
        "area",
        "manager_employee_id",
        "physical_location",
        "operational_status",
        "warehouse_type",
        "code",
    ):
        op.drop_column("warehouses", name)
    op.drop_constraint("uq_branches_company_code", "branches", type_="unique")
    op.drop_constraint("ck_branches_operational_status", "branches", type_="check")
    op.drop_constraint("ck_branches_longitude", "branches", type_="check")
    op.drop_constraint("ck_branches_latitude", "branches", type_="check")
    for name in (
        "has_ups",
        "has_backup_generator",
        "fire_system",
        "has_alarm",
        "access_control",
        "cctv_cameras",
        "website",
        "landlord",
        "lease_expiry",
        "permit_expiry",
        "cadastral_code",
        "building_condition",
        "construction_year",
        "construction_type",
        "accessibility",
        "emergency_exits",
        "accesses",
        "bathrooms",
        "meeting_rooms",
        "offices",
        "property_type",
        "people_capacity",
        "parking",
        "floors",
        "area_unbuilt",
        "area_built",
        "area",
        "images",
        "facilities",
        "services",
        "zone",
        "schedule",
        "description",
        "opened_at",
        "manager_employee_id",
        "operational_status",
        "longitude",
        "latitude",
        "code",
    ):
        op.drop_column("branches", name)
    op.drop_column("companies", "description")
    op.drop_index("ix_user_companies_company", table_name="user_companies")
    op.drop_table("user_companies")
