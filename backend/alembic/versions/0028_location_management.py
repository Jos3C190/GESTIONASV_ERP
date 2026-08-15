"""Add versioned location codes and atomic bulk staging.

Revision ID: 0028
Revises: 0027

The migration is deliberately additive.  Existing location codes are never
recalculated: they remain byte-for-byte identical and are marked ``legacy``.
Every warehouse receives an active version-1 A/R/N/P scheme for future writes.
"""

from __future__ import annotations

import json

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None

DEFAULT_SEGMENTS = [
    {"key": "aisle", "label": "Pasillo", "prefix": "A", "width": 2, "pad_char": "0", "required": True},
    {"key": "rack", "label": "Rack", "prefix": "R", "width": 2, "pad_char": "0", "required": True},
    {"key": "level", "label": "Nivel", "prefix": "N", "width": 2, "pad_char": "0", "required": True},
    {"key": "position", "label": "Posición", "prefix": "P", "width": 2, "pad_char": "0", "required": True},
]

NEW_PERMISSIONS = (
    ("locations.scheme", "Versionar esquemas de códigos de ubicación"),
    ("locations.bulk", "Generar y publicar ubicaciones por lotes"),
    ("locations.import", "Importar ubicaciones desde CSV o XLSX"),
    ("locations.export", "Exportar ubicaciones"),
    ("locations.recode", "Renumerar ubicaciones conservando alias"),
    ("locations.labels", "Generar etiquetas de ubicación"),
    ("locations.commission", "Comisionar y retirar ubicaciones"),
)


def upgrade() -> None:
    op.create_table(
        "location_code_schemes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("warehouse_id", UUID(as_uuid=True), sa.ForeignKey("warehouses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("separator", sa.String(3), nullable=False, server_default="-"),
        sa.Column("segments", JSONB(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("version > 0", name="ck_location_code_schemes_version_positive"),
        sa.UniqueConstraint("warehouse_id", "version", name="uq_location_code_schemes_warehouse_version"),
    )
    op.create_index(
        "uq_location_code_schemes_active",
        "location_code_schemes",
        ["warehouse_id"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )

    # Create the future-write scheme before adding its optional FK to legacy rows.
    op.get_bind().execute(
        sa.text(
            "INSERT INTO location_code_schemes "
            "(id, warehouse_id, name, version, separator, segments, is_active, created_at, updated_at) "
            "SELECT gen_random_uuid(), w.id, 'Esquema estándar A/R/N/P', 1, '-', "
            "CAST(:segments AS jsonb), true, now(), now() FROM warehouses w"
        ),
        {"segments": json.dumps(DEFAULT_SEGMENTS, ensure_ascii=False)},
    )

    location_columns = (
        sa.Column("area", sa.String(64), nullable=True),
        sa.Column("location_type", sa.String(32), nullable=False, server_default="standard"),
        sa.Column("lifecycle_status", sa.String(24), nullable=False, server_default="active"),
        sa.Column("barcode", sa.String(120), nullable=True),
        sa.Column("verification_code", sa.String(120), nullable=True),
        sa.Column("pick_sequence", sa.Integer(), nullable=True),
        sa.Column("putaway_sequence", sa.Integer(), nullable=True),
        sa.Column("external_id", sa.String(120), nullable=True),
        sa.Column("code_scheme_id", UUID(as_uuid=True), nullable=True),
        sa.Column("scheme_version", sa.Integer(), nullable=True),
        sa.Column("code_source", sa.String(20), nullable=False, server_default="legacy"),
    )
    for column in location_columns:
        op.add_column("locations", column)
    # Associate legacy rows with the default scheme for traceability only.  The
    # code itself is intentionally not regenerated or normalized.
    op.execute(
        "UPDATE locations l SET code_scheme_id = s.id, scheme_version = 1, code_source = 'legacy' "
        "FROM location_code_schemes s WHERE s.warehouse_id = l.warehouse_id AND s.version = 1"
    )
    op.create_foreign_key(
        "fk_locations_code_scheme_id_location_code_schemes",
        "locations",
        "location_code_schemes",
        ["code_scheme_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "ck_locations_pick_sequence_nonnegative",
        "locations",
        "pick_sequence IS NULL OR pick_sequence >= 0",
    )
    op.create_check_constraint(
        "ck_locations_putaway_sequence_nonnegative",
        "locations",
        "putaway_sequence IS NULL OR putaway_sequence >= 0",
    )
    op.create_check_constraint(
        "ck_locations_lifecycle_status",
        "locations",
        "lifecycle_status IN ('draft','active','blocked','blocked_in','blocked_out','maintenance','retired')",
    )
    op.create_check_constraint(
        "ck_locations_type",
        "locations",
        "location_type IN ('standard','bulk','receiving','reserve','picking','staging','quality','packing','shipping','returns','virtual')",
    )
    op.create_check_constraint(
        "ck_locations_code_source",
        "locations",
        "code_source IN ('legacy','generated','imported','recode')",
    )
    op.drop_index("uq_locations_warehouse_coordinates_visible", table_name="locations")
    op.create_index(
        "uq_locations_warehouse_coordinates_visible",
        "locations",
        ["warehouse_id", sa.text("coalesce(area, '')"), "aisle", "rack", "level", "position"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    for name, expression, predicate in (
        ("uq_locations_warehouse_barcode_visible", "lower(barcode)", "barcode IS NOT NULL AND deleted_at IS NULL"),
        ("uq_locations_warehouse_verification_visible", "lower(verification_code)", "verification_code IS NOT NULL AND deleted_at IS NULL"),
        ("uq_locations_warehouse_external_id_visible", "lower(external_id)", "external_id IS NOT NULL AND deleted_at IS NULL"),
    ):
        op.create_index(
            name,
            "locations",
            ["warehouse_id", sa.text(expression)],
            unique=True,
            postgresql_where=sa.text(predicate),
        )
    op.create_index(
        "ix_locations_warehouse_status_code",
        "locations",
        ["warehouse_id", "lifecycle_status", "code"],
    )

    op.create_table(
        "location_code_aliases",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("warehouse_id", UUID(as_uuid=True), sa.ForeignKey("warehouses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("location_id", UUID(as_uuid=True), sa.ForeignKey("locations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("alias_code", sa.String(120), nullable=False),
        sa.Column("code_scheme_id", UUID(as_uuid=True), sa.ForeignKey("location_code_schemes.id", ondelete="SET NULL")),
        sa.Column("scheme_version", sa.Integer()),
        sa.Column("reason", sa.String(32), nullable=False, server_default="recode"),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "uq_location_code_aliases_warehouse_code",
        "location_code_aliases",
        ["warehouse_id", sa.text("lower(alias_code)")],
        unique=True,
    )
    op.create_index("ix_location_code_aliases_location", "location_code_aliases", ["location_id"])

    op.create_table(
        "location_batch_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("warehouse_id", UUID(as_uuid=True), sa.ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="preview"),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("input_checksum", sa.String(64), nullable=False),
        sa.Column("code_scheme_id", UUID(as_uuid=True), sa.ForeignKey("location_code_schemes.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("scheme_version", sa.Integer(), nullable=False),
        sa.Column("total_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("create_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("update_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unchanged_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("conflict_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("summary", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("published_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("failure_reason", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("kind IN ('generate','import')", name="ck_location_batch_jobs_kind"),
        sa.CheckConstraint("status IN ('preview','publishing','published','failed','cancelled')", name="ck_location_batch_jobs_status"),
        sa.UniqueConstraint("warehouse_id", "kind", "idempotency_key", name="uq_location_batch_jobs_idempotency"),
    )
    op.create_index(
        "ix_location_batch_jobs_warehouse_created",
        "location_batch_jobs",
        ["warehouse_id", "created_at"],
    )

    op.create_table(
        "location_batch_rows",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("job_id", UUID(as_uuid=True), sa.ForeignKey("location_batch_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("operation", sa.String(16), nullable=False),
        sa.Column("code", sa.String(120)),
        sa.Column("normalized_data", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("diff", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("errors", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("published_location_id", UUID(as_uuid=True), sa.ForeignKey("locations.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("operation IN ('create','update','unchanged','conflict','error')", name="ck_location_batch_rows_operation"),
        sa.UniqueConstraint("job_id", "row_number", name="uq_location_batch_rows_job_row"),
    )
    op.create_index(
        "ix_location_batch_rows_job_operation",
        "location_batch_rows",
        ["job_id", "operation"],
    )

    connection = op.get_bind()
    for code, description in NEW_PERMISSIONS:
        connection.execute(
            sa.text(
                "INSERT INTO permissions (id, code, description, module, created_at) "
                "VALUES (gen_random_uuid(), :code, :description, 'locations', now()) "
                "ON CONFLICT DO NOTHING"
            ),
            {"code": code, "description": description},
        )
    connection.execute(
        sa.text(
            "INSERT INTO role_permissions (role_id, permission_id, conditions, created_at) "
            "SELECT r.id, p.id, '{}'::jsonb, now() FROM roles r CROSS JOIN permissions p "
            "WHERE r.name IN ('SUPER_ADMIN','ADMINISTRADOR','ADMINISTRADOR DE OPERACIONES','JEFE DE ALMACÉN') "
            "AND r.deleted_at IS NULL AND p.deleted_at IS NULL AND p.code = ANY(:codes) "
            "ON CONFLICT DO NOTHING"
        ),
        {"codes": [code for code, _ in NEW_PERMISSIONS]},
    )


def downgrade() -> None:
    duplicate_coordinates = op.get_bind().scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM locations WHERE deleted_at IS NULL "
            "GROUP BY warehouse_id, aisle, rack, level, position HAVING count(*) > 1)"
        )
    )
    if duplicate_coordinates:
        raise RuntimeError(
            "No se puede revertir 0028: existen ubicaciones visibles en áreas distintas "
            "con las mismas coordenadas legacy. Consolídelas antes del downgrade."
        )
    # Keep catalogue rows/grants on downgrade.  They are harmless while the
    # feature tables are absent, and deleting them could destroy a permission
    # or custom grant that already existed before this revision.

    op.drop_index("ix_location_batch_rows_job_operation", table_name="location_batch_rows")
    op.drop_table("location_batch_rows")
    op.drop_index("ix_location_batch_jobs_warehouse_created", table_name="location_batch_jobs")
    op.drop_table("location_batch_jobs")
    op.drop_index("ix_location_code_aliases_location", table_name="location_code_aliases")
    op.drop_index("uq_location_code_aliases_warehouse_code", table_name="location_code_aliases")
    op.drop_table("location_code_aliases")

    op.drop_index("ix_locations_warehouse_status_code", table_name="locations")
    for name in (
        "uq_locations_warehouse_external_id_visible",
        "uq_locations_warehouse_verification_visible",
        "uq_locations_warehouse_barcode_visible",
    ):
        op.drop_index(name, table_name="locations")
    op.drop_index("uq_locations_warehouse_coordinates_visible", table_name="locations")
    op.create_index(
        "uq_locations_warehouse_coordinates_visible",
        "locations",
        ["warehouse_id", "aisle", "rack", "level", "position"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    for name in (
        "ck_locations_code_source",
        "ck_locations_type",
        "ck_locations_lifecycle_status",
        "ck_locations_putaway_sequence_nonnegative",
        "ck_locations_pick_sequence_nonnegative",
    ):
        op.drop_constraint(name, "locations", type_="check")
    op.drop_constraint(
        "fk_locations_code_scheme_id_location_code_schemes", "locations", type_="foreignkey"
    )
    for column in (
        "code_source",
        "scheme_version",
        "code_scheme_id",
        "external_id",
        "putaway_sequence",
        "pick_sequence",
        "verification_code",
        "barcode",
        "lifecycle_status",
        "location_type",
        "area",
    ):
        op.drop_column("locations", column)
    op.drop_index("uq_location_code_schemes_active", table_name="location_code_schemes")
    op.drop_table("location_code_schemes")
