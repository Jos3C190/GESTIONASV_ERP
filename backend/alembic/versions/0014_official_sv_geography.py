"""Load the official post-restructuring geography of El Salvador.

Revision ID: 0014
Revises: 0013
"""

from __future__ import annotations

from uuid import uuid4

from alembic import op
from sqlalchemy import text

from app.infrastructure.catalogs.el_salvador_geography import GEOGRAPHY, catalog_counts

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def _id_for(connection, table: str, parent_column: str | None, parent_id, name: str):
    clauses = ["name = :name"]
    params = {"name": name}
    if parent_column:
        clauses.append(f"{parent_column} = :parent_id")
        params["parent_id"] = parent_id
    return connection.execute(
        text(f"SELECT id FROM {table} WHERE {' AND '.join(clauses)}"), params
    ).scalar_one_or_none()


def _insert_named(connection, table: str, parent_column: str | None, parent_id, name: str):
    existing = _id_for(connection, table, parent_column, parent_id, name)
    if existing:
        return existing
    identifier = uuid4()
    columns = "id, name"
    values = ":id, :name"
    params = {"id": identifier, "name": name}
    if parent_column:
        columns += f", {parent_column}"
        values += ", :parent_id"
        params["parent_id"] = parent_id
    connection.execute(text(f"INSERT INTO {table} ({columns}) VALUES ({values})"), params)
    return identifier


def upgrade() -> None:
    if catalog_counts() != (14, 44, 262):
        raise RuntimeError("The official geography catalog has an unexpected size")

    connection = op.get_bind()

    # The provisional seed used the former municipality name. Rename it first so
    # existing San Salvador company/branch foreign keys keep their identifiers.
    connection.execute(
        text(
            """
            UPDATE municipalities m
               SET name = 'San Salvador Centro'
              FROM geographic_departments d
             WHERE m.department_id = d.id
               AND d.name = 'San Salvador'
               AND m.name = 'San Salvador'
               AND NOT EXISTS (
                   SELECT 1 FROM municipalities current
                    WHERE current.department_id = d.id
                      AND current.name = 'San Salvador Centro'
               )
            """
        )
    )

    valid_departments = set()
    valid_municipalities = set()
    valid_districts = set()
    default_ids = None

    for department_name, municipalities in GEOGRAPHY.items():
        department_id = _insert_named(
            connection, "geographic_departments", None, None, department_name
        )
        valid_departments.add(department_id)
        for municipality_name, districts in municipalities.items():
            municipality_id = _insert_named(
                connection,
                "municipalities",
                "department_id",
                department_id,
                municipality_name,
            )
            valid_municipalities.add(municipality_id)
            for district_name in districts:
                district_id = _insert_named(
                    connection,
                    "districts",
                    "municipality_id",
                    municipality_id,
                    district_name,
                )
                valid_districts.add(district_id)
                if (
                    department_name == "San Salvador"
                    and municipality_name == "San Salvador Centro"
                    and district_name == "San Salvador"
                ):
                    default_ids = (department_id, municipality_id, district_id)

    if default_ids is None:
        raise RuntimeError("San Salvador default geography was not loaded")

    # Any provisional geography referenced by mock organizations is normalized to
    # San Salvador before obsolete catalog rows are removed.
    department_id, municipality_id, district_id = default_ids
    for table in ("companies", "branches"):
        connection.execute(
            text(
                f"""
                UPDATE {table} owner
                   SET department_id = :department_id,
                       municipality_id = :municipality_id,
                       district_id = :district_id
                 WHERE NOT (owner.department_id = ANY(:department_ids))
                    OR NOT (owner.municipality_id = ANY(:municipality_ids))
                    OR NOT (owner.district_id = ANY(:district_ids))
                """
            ),
            {
                "department_id": department_id,
                "municipality_id": municipality_id,
                "district_id": district_id,
                "department_ids": list(valid_departments),
                "municipality_ids": list(valid_municipalities),
                "district_ids": list(valid_districts),
            },
        )

    connection.execute(
        text("DELETE FROM districts WHERE NOT (id = ANY(:ids))"),
        {"ids": list(valid_districts)},
    )
    connection.execute(
        text("DELETE FROM municipalities WHERE NOT (id = ANY(:ids))"),
        {"ids": list(valid_municipalities)},
    )
    connection.execute(
        text("DELETE FROM geographic_departments WHERE NOT (id = ANY(:ids))"),
        {"ids": list(valid_departments)},
    )


def downgrade() -> None:
    # Reference catalogs are intentionally not replaced with provisional mock data.
    pass
