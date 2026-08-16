"""Normalize product dimensions and weight without reusing commercial units."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None

DIMENSION_UNITS = ("mm", "cm", "m", "in", "ft")
WEIGHT_UNITS = ("mg", "g", "kg", "t", "oz", "lb")


def _in_list(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    op.add_column("products", sa.Column("dimensions_legacy", sa.Text(), nullable=True))
    op.add_column("products", sa.Column("dimension_length", sa.Numeric(12, 3), nullable=True))
    op.add_column("products", sa.Column("dimension_width", sa.Numeric(12, 3), nullable=True))
    op.add_column("products", sa.Column("dimension_height", sa.Numeric(12, 3), nullable=True))
    op.add_column("products", sa.Column("dimension_unit", sa.String(4), nullable=True))
    op.add_column("products", sa.Column("weight", sa.Numeric(12, 3), nullable=True))
    op.add_column("products", sa.Column("weight_unit", sa.String(4), nullable=True))

    op.create_check_constraint(
        "ck_products_dimension_length_nonnegative",
        "products",
        "dimension_length IS NULL OR dimension_length >= 0",
    )
    op.create_check_constraint(
        "ck_products_dimension_width_nonnegative",
        "products",
        "dimension_width IS NULL OR dimension_width >= 0",
    )
    op.create_check_constraint(
        "ck_products_dimension_height_nonnegative",
        "products",
        "dimension_height IS NULL OR dimension_height >= 0",
    )
    op.create_check_constraint(
        "ck_products_weight_nonnegative",
        "products",
        "weight IS NULL OR weight >= 0",
    )
    op.create_check_constraint(
        "ck_products_dimension_unit",
        "products",
        f"dimension_unit IS NULL OR dimension_unit IN ({_in_list(DIMENSION_UNITS)})",
    )
    op.create_check_constraint(
        "ck_products_weight_unit",
        "products",
        f"weight_unit IS NULL OR weight_unit IN ({_in_list(WEIGHT_UNITS)})",
    )
    op.create_check_constraint(
        "ck_products_dimension_unit_pair",
        "products",
        "((dimension_length IS NULL AND dimension_width IS NULL AND dimension_height IS NULL) = (dimension_unit IS NULL))",
    )
    op.create_check_constraint(
        "ck_products_weight_unit_pair",
        "products",
        "((weight IS NULL) = (weight_unit IS NULL))",
    )

    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            UPDATE products
               SET dimensions_legacy = dimensions
             WHERE dimensions IS NOT NULL AND btrim(dimensions) <> ''
            """
        )
    )
    connection.execute(
        sa.text(
            r"""
            WITH parsed AS (
                SELECT id_product,
                       (m)[1]::numeric AS length_value,
                       (m)[2]::numeric AS width_value,
                       NULLIF((m)[3], '')::numeric AS height_value,
                       lower((m)[4]) AS unit_value
                  FROM (
                      SELECT id_product,
                             regexp_match(
                                 replace(dimensions, chr(215), 'x'),
                                 '^\s*([0-9]+(?:\.[0-9]+)?)\s*[xX*]\s*([0-9]+(?:\.[0-9]+)?)(?:\s*[xX*]\s*([0-9]+(?:\.[0-9]+)?))?\s*(mm|cm|m|in|ft)\s*$'
                             ) AS m
                        FROM products
                       WHERE dimensions IS NOT NULL
                  ) matched
                 WHERE m IS NOT NULL
            )
            UPDATE products AS p
               SET dimension_length = parsed.length_value,
                   dimension_width = parsed.width_value,
                   dimension_height = parsed.height_value,
                   dimension_unit = parsed.unit_value,
                   dimensions_legacy = NULL
              FROM parsed
             WHERE p.id_product = parsed.id_product
            """
        )
    )


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            UPDATE products
               SET dimensions = concat_ws(
                       ' ' || chr(215) || ' ',
                       trim(to_char(dimension_length, 'FM999999999990.###')),
                       trim(to_char(dimension_width, 'FM999999999990.###')),
                       trim(to_char(dimension_height, 'FM999999999990.###'))
                   ) || ' ' || dimension_unit
             WHERE dimension_length IS NOT NULL
                OR dimension_width IS NOT NULL
                OR dimension_height IS NOT NULL
            """
        )
    )
    connection.execute(
        sa.text(
            """
            UPDATE products
               SET dimensions = dimensions_legacy
             WHERE dimensions_legacy IS NOT NULL
               AND dimension_length IS NULL
               AND dimension_width IS NULL
               AND dimension_height IS NULL
            """
        )
    )

    for name in (
        "ck_products_weight_unit_pair",
        "ck_products_dimension_unit_pair",
        "ck_products_weight_unit",
        "ck_products_dimension_unit",
        "ck_products_weight_nonnegative",
        "ck_products_dimension_height_nonnegative",
        "ck_products_dimension_width_nonnegative",
        "ck_products_dimension_length_nonnegative",
    ):
        op.drop_constraint(name, "products", type_="check")
    for column in (
        "weight_unit",
        "weight",
        "dimension_unit",
        "dimension_height",
        "dimension_width",
        "dimension_length",
        "dimensions_legacy",
    ):
        op.drop_column("products", column)
