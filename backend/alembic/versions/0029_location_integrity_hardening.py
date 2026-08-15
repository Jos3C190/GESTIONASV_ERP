"""Harden location tenant alignment and the code/alias namespace.

Revision ID: 0029
Revises: 0028

0028 was already deployed while the location feature was under review.  This
follow-up is intentionally incremental: it preserves all codes and data while
adding the database invariants required by the final application contract.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None

NEW_PERMISSION_CODES = (
    "locations.scheme",
    "locations.bulk",
    "locations.import",
    "locations.export",
    "locations.recode",
    "locations.labels",
    "locations.commission",
)


def _foreign_key_name(table: str, columns: Sequence[str]) -> str:
    expected = list(columns)
    for foreign_key in sa.inspect(op.get_bind()).get_foreign_keys(table):
        if foreign_key.get("constrained_columns") == expected and foreign_key.get("name"):
            return str(foreign_key["name"])
    raise RuntimeError(
        f"No se encontró la llave foránea esperada {table}({', '.join(columns)})."
    )


def upgrade() -> None:
    # Repair only the contradictory legacy case; do not overwrite meaningful
    # blocked/maintenance states created after 0028.
    op.execute(
        "UPDATE locations SET lifecycle_status = 'retired' "
        "WHERE code_source = 'legacy' AND is_active = false "
        "AND lifecycle_status = 'active'"
    )

    op.create_unique_constraint(
        "uq_location_code_schemes_identity_scope_version",
        "location_code_schemes",
        ["id", "warehouse_id", "version"],
    )
    op.create_unique_constraint(
        "uq_locations_identity_warehouse", "locations", ["id", "warehouse_id"]
    )

    op.drop_constraint(
        _foreign_key_name("locations", ["code_scheme_id"]),
        "locations",
        type_="foreignkey",
    )
    op.drop_constraint(
        _foreign_key_name("location_code_aliases", ["location_id"]),
        "location_code_aliases",
        type_="foreignkey",
    )
    op.drop_constraint(
        _foreign_key_name("location_code_aliases", ["code_scheme_id"]),
        "location_code_aliases",
        type_="foreignkey",
    )
    op.drop_constraint(
        _foreign_key_name("location_batch_jobs", ["code_scheme_id"]),
        "location_batch_jobs",
        type_="foreignkey",
    )

    op.create_foreign_key(
        "fk_locations_scheme_scope_version",
        "locations",
        "location_code_schemes",
        ["code_scheme_id", "warehouse_id", "scheme_version"],
        ["id", "warehouse_id", "version"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_location_code_aliases_location_scope",
        "location_code_aliases",
        "locations",
        ["location_id", "warehouse_id"],
        ["id", "warehouse_id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_location_code_aliases_scheme_scope_version",
        "location_code_aliases",
        "location_code_schemes",
        ["code_scheme_id", "warehouse_id", "scheme_version"],
        ["id", "warehouse_id", "version"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_location_batch_jobs_scheme_scope_version",
        "location_batch_jobs",
        "location_code_schemes",
        ["code_scheme_id", "warehouse_id", "scheme_version"],
        ["id", "warehouse_id", "version"],
        ondelete="RESTRICT",
    )

    # Active codes and aliases share one case-insensitive namespace.  Both
    # writers take the same transaction-scoped advisory lock before checking
    # the opposite table, which also closes the concurrent insert race.
    op.execute(
        """
        CREATE FUNCTION enforce_location_code_namespace()
        RETURNS trigger AS $$
        DECLARE
            new_code text;
            old_code text;
            new_lock bigint;
            old_lock bigint;
        BEGIN
            IF TG_TABLE_NAME = 'location_code_aliases' THEN
                new_code := lower(NEW.alias_code);
                old_code := CASE WHEN TG_OP = 'UPDATE' THEN lower(OLD.alias_code) ELSE new_code END;
            ELSE
                new_code := lower(NEW.code);
                old_code := CASE WHEN TG_OP = 'UPDATE' THEN lower(OLD.code) ELSE new_code END;
            END IF;
            new_lock := hashtextextended(NEW.warehouse_id::text || ':' || new_code, 0);
            old_lock := CASE
                WHEN TG_OP = 'UPDATE'
                THEN hashtextextended(OLD.warehouse_id::text || ':' || old_code, 0)
                ELSE new_lock
            END;
            PERFORM pg_advisory_xact_lock(LEAST(new_lock, old_lock));
            IF new_lock <> old_lock THEN
                PERFORM pg_advisory_xact_lock(GREATEST(new_lock, old_lock));
            END IF;

            IF TG_TABLE_NAME = 'location_code_aliases' THEN
                IF EXISTS (
                    SELECT 1 FROM locations l
                    WHERE l.warehouse_id = NEW.warehouse_id
                      AND l.deleted_at IS NULL
                      AND l.id <> NEW.location_id
                      AND lower(l.code) = new_code
                ) THEN
                    RAISE EXCEPTION 'El alias colisiona con un código de ubicación vigente.'
                        USING ERRCODE = '23505';
                END IF;
            ELSIF NEW.deleted_at IS NULL AND EXISTS (
                SELECT 1 FROM location_code_aliases a
                WHERE a.warehouse_id = NEW.warehouse_id
                  AND a.location_id <> NEW.id
                  AND lower(a.alias_code) = new_code
            ) THEN
                RAISE EXCEPTION 'El código colisiona con un alias histórico reservado.'
                    USING ERRCODE = '23505';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        "CREATE TRIGGER trg_location_code_namespace_alias "
        "BEFORE INSERT OR UPDATE OF warehouse_id, location_id, alias_code "
        "ON location_code_aliases FOR EACH ROW "
        "EXECUTE FUNCTION enforce_location_code_namespace()"
    )
    op.execute(
        "CREATE TRIGGER trg_location_code_namespace_location "
        "BEFORE INSERT OR UPDATE OF warehouse_id, code, deleted_at ON locations "
        "FOR EACH ROW EXECUTE FUNCTION enforce_location_code_namespace()"
    )

    # 0028 accidentally elevated the generic ADMINISTRADOR role beyond the
    # canonical RBAC catalogue.  Fail closed and keep operational warehouse
    # roles plus SUPER_ADMIN as the rollout grants.
    op.get_bind().execute(
        sa.text(
            "DELETE FROM role_permissions rp USING roles r, permissions p "
            "WHERE rp.role_id = r.id AND rp.permission_id = p.id "
            "AND r.name = 'ADMINISTRADOR' AND p.code = ANY(:codes)"
        ),
        {"codes": list(NEW_PERMISSION_CODES)},
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_location_code_namespace_location ON locations")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_location_code_namespace_alias ON location_code_aliases"
    )
    op.execute("DROP FUNCTION IF EXISTS enforce_location_code_namespace()")

    op.drop_constraint(
        "fk_location_batch_jobs_scheme_scope_version",
        "location_batch_jobs",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_location_code_aliases_scheme_scope_version",
        "location_code_aliases",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_location_code_aliases_location_scope",
        "location_code_aliases",
        type_="foreignkey",
    )
    op.drop_constraint("fk_locations_scheme_scope_version", "locations", type_="foreignkey")

    op.create_foreign_key(
        "fk_locations_code_scheme_id_location_code_schemes",
        "locations",
        "location_code_schemes",
        ["code_scheme_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "location_code_aliases_location_id_fkey",
        "location_code_aliases",
        "locations",
        ["location_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "location_code_aliases_code_scheme_id_fkey",
        "location_code_aliases",
        "location_code_schemes",
        ["code_scheme_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "location_batch_jobs_code_scheme_id_fkey",
        "location_batch_jobs",
        "location_code_schemes",
        ["code_scheme_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.drop_constraint("uq_locations_identity_warehouse", "locations", type_="unique")
    op.drop_constraint(
        "uq_location_code_schemes_identity_scope_version",
        "location_code_schemes",
        type_="unique",
    )
