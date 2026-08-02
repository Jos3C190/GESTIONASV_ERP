"""Multi-company workforce and historical branch assignments.

Revision ID: 0010
Revises: 0009
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("departments", sa.Column("company_id", UUID(as_uuid=True), nullable=True))
    op.add_column("employees", sa.Column("company_id", UUID(as_uuid=True), nullable=True))
    op.execute(
        "UPDATE departments SET company_id=(SELECT id FROM companies ORDER BY created_at LIMIT 1) WHERE company_id IS NULL"
    )
    op.execute(
        "UPDATE employees e SET company_id=COALESCE((SELECT d.company_id FROM departments d WHERE d.id=e.department_id),(SELECT id FROM companies ORDER BY created_at LIMIT 1)) WHERE company_id IS NULL"
    )
    op.alter_column("departments", "company_id", nullable=False)
    op.alter_column("employees", "company_id", nullable=False)
    op.create_foreign_key(
        "fk_departments_company",
        "departments",
        "companies",
        ["company_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_employees_company",
        "employees",
        "companies",
        ["company_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_departments_company_id", "departments", ["company_id"])
    op.create_index("ix_employees_company_id", "employees", ["company_id"])
    op.drop_constraint("uq_departments_name", "departments", type_="unique")
    op.drop_constraint("uq_employees_code", "employees", type_="unique")
    op.create_unique_constraint(
        "uq_departments_company_name", "departments", ["company_id", "name"]
    )
    op.create_unique_constraint(
        "uq_employees_company_code", "employees", ["company_id", "employee_code"]
    )

    op.create_table(
        "department_branch_assignments",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column(
            "department_id",
            UUID(as_uuid=True),
            sa.ForeignKey("departments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "branch_id",
            UUID(as_uuid=True),
            sa.ForeignKey("branches.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "manager_employee_id",
            UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="SET NULL"),
        ),
        sa.Column("opened_at", sa.Date(), nullable=False, server_default=sa.text("CURRENT_DATE")),
        sa.Column("closed_at", sa.Date()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("department_id", "branch_id", name="uq_department_branch"),
        sa.CheckConstraint(
            "closed_at IS NULL OR closed_at >= opened_at", name="ck_department_branch_dates"
        ),
    )
    op.create_table(
        "employee_branch_assignments",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column(
            "employee_id",
            UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "branch_id",
            UUID(as_uuid=True),
            sa.ForeignKey("branches.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "assigned_from", sa.Date(), nullable=False, server_default=sa.text("CURRENT_DATE")
        ),
        sa.Column("assigned_until", sa.Date()),
        sa.Column("position", sa.String(120)),
        sa.Column("shift", sa.String(32)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "assigned_until IS NULL OR assigned_until >= assigned_from",
            name="ck_employee_branch_dates",
        ),
    )
    op.create_index("ix_employee_branch_employee", "employee_branch_assignments", ["employee_id"])
    op.create_index("ix_employee_branch_branch", "employee_branch_assignments", ["branch_id"])
    op.create_index(
        "uq_employee_branch_active",
        "employee_branch_assignments",
        ["employee_id", "branch_id"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )
    op.create_index(
        "uq_employee_primary_branch",
        "employee_branch_assignments",
        ["employee_id"],
        unique=True,
        postgresql_where=sa.text("is_active AND is_primary"),
    )


def downgrade() -> None:
    op.drop_table("employee_branch_assignments")
    op.drop_table("department_branch_assignments")
    op.drop_constraint("uq_employees_company_code", "employees", type_="unique")
    op.drop_constraint("uq_departments_company_name", "departments", type_="unique")
    op.create_unique_constraint("uq_employees_code", "employees", ["employee_code"])
    op.create_unique_constraint("uq_departments_name", "departments", ["name"])
    op.drop_column("employees", "company_id")
    op.drop_column("departments", "company_id")
