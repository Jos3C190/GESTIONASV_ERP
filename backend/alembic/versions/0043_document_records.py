"""Business document records, employee ownership and categories."""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0043"
down_revision = "0042"
branch_labels = None
depends_on = None

PERMISSIONS = (
    ("documents:update", "Editar metadatos documentales", "documents"),
    ("documents:categories", "Gestionar categorías documentales generales", "documents"),
    ("employee_documents:read", "Consultar expedientes documentales de empleados", "documents"),
    ("employee_documents:upload", "Cargar documentos al expediente de empleados", "documents"),
    ("employee_documents:update", "Editar metadatos del expediente de empleados", "documents"),
    (
        "employee_documents:download",
        "Descargar documentos del expediente de empleados",
        "documents",
    ),
    ("employee_documents:delete", "Enviar documentos del expediente a la papelera", "documents"),
    ("employee_documents:restore", "Restaurar documentos del expediente", "documents"),
    ("employee_documents:process", "Procesar documentos del expediente", "documents"),
    (
        "employee_documents:restricted",
        "Consultar documentos restringidos del expediente",
        "documents",
    ),
    (
        "employee_documents:manage_categories",
        "Gestionar categorías del expediente de empleados",
        "documents",
    ),
)


EMPLOYEE_CATEGORIES = (
    ("cv", "CV", "Expediente personal"),
    ("employee_file", "Ficha del empleado", "Expediente personal"),
    ("job_application", "Solicitud de empleo", "Expediente personal"),
    ("dui", "DUI", "Expediente personal"),
    ("nit", "NIT", "Expediente personal"),
    ("passport", "Pasaporte", "Expediente personal"),
    ("work_permit", "Permiso de trabajo", "Expediente personal"),
    ("identity_document", "Documento de identidad", "Expediente personal"),
    ("personal_reference", "Referencia personal", "Expediente personal"),
    ("employment_reference", "Referencia laboral", "Expediente personal"),
    ("background_check", "Constancia de antecedentes", "Expediente personal"),
    ("emergency_contacts", "Contactos de emergencia", "Expediente personal"),
    ("academic_degree", "Título académico", "Formación y experiencia"),
    ("diploma", "Diploma", "Formación y experiencia"),
    ("professional_certification", "Certificación profesional", "Formación y experiencia"),
    ("course_certificate", "Constancia de curso", "Formación y experiencia"),
    ("training_certificate", "Constancia de capacitación", "Formación y experiencia"),
    ("professional_license", "Licencia profesional", "Formación y experiencia"),
    ("recommendation_letter", "Carta de recomendación", "Formación y experiencia"),
    ("internal_training", "Historial de capacitación interna", "Formación y experiencia"),
    ("employment_contract", "Contrato laboral", "Relación laboral"),
    ("contract_addendum", "Adenda de contrato", "Relación laboral"),
    ("job_profile", "Descripción o perfil de puesto", "Relación laboral"),
    ("confidentiality_agreement", "Acuerdo de confidencialidad", "Relación laboral"),
    ("offer_letter", "Carta de oferta", "Relación laboral"),
    ("internal_regulations_ack", "Acuse de reglamento interno", "Relación laboral"),
    ("consent", "Autorización o consentimiento", "Relación laboral"),
    ("uniform_delivery", "Acta de entrega de uniforme", "Relación laboral"),
    ("equipment_delivery", "Acta de entrega de herramientas o equipo", "Relación laboral"),
    ("promotion_letter", "Carta de ascenso", "Relación laboral"),
    ("transfer_letter", "Carta de traslado", "Relación laboral"),
    ("salary_change_letter", "Carta de cambio salarial", "Relación laboral"),
    ("performance_review", "Evaluación de desempeño", "Seguimiento"),
    ("improvement_plan", "Plan de mejora", "Seguimiento"),
    ("recognition", "Reconocimiento", "Seguimiento"),
    ("warning", "Amonestación", "Seguimiento"),
    ("disciplinary_record", "Acta disciplinaria", "Seguimiento"),
    ("leave", "Permiso", "Seguimiento"),
    ("license", "Licencia", "Seguimiento"),
    ("sick_leave", "Incapacidad", "Seguimiento"),
    ("work_accident", "Accidente laboral", "Seguimiento"),
    ("medical_certificate", "Constancia médica", "Seguimiento"),
    ("resignation", "Carta de renuncia", "Finalización laboral"),
    ("dismissal_notice", "Notificación de despido", "Finalización laboral"),
    ("severance", "Finiquito", "Finalización laboral"),
    ("asset_clearance", "Solvencia de equipos y activos", "Finalización laboral"),
    ("exit_interview", "Entrevista de salida", "Finalización laboral"),
    ("employment_certificate", "Constancia laboral", "Finalización laboral"),
    ("other", "Otros", "General"),
)


def _literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _seed_categories() -> None:
    # Every company receives its own editable catalog.  The INSERT is
    # idempotent so startup/bootstrap scripts can safely call the same logic.
    for code, name, group_name in (("other", "Otros", "General"),):
        op.execute(
            "INSERT INTO document_categories "
            "(id, company_id, module, code, name, group_name, sort_order, is_active, created_at, updated_at) "
            "SELECT gen_random_uuid(), c.id, 'general', "
            f"{_literal(code)}, {_literal(name)}, {_literal(group_name)}, 0, true, now(), now() "
            "FROM companies c ON CONFLICT (company_id, module, code) DO NOTHING"
        )
    for index, (code, name, group_name) in enumerate(EMPLOYEE_CATEGORIES, start=1):
        op.execute(
            "INSERT INTO document_categories "
            "(id, company_id, module, code, name, group_name, sort_order, is_active, created_at, updated_at) "
            "SELECT gen_random_uuid(), c.id, 'employees', "
            f"{_literal(code)}, {_literal(name)}, {_literal(group_name)}, {index}, true, now(), now() "
            "FROM companies c ON CONFLICT (company_id, module, code) DO NOTHING"
        )


def upgrade() -> None:
    for code, description, module in PERMISSIONS:
        op.execute(
            "INSERT INTO permissions (id, code, description, module, created_at) "
            f"VALUES (gen_random_uuid(), {_literal(code)}, {_literal(description)}, "
            f"{_literal(module)}, now()) ON CONFLICT DO NOTHING"
        )
    permission_codes = ",".join(_literal(code) for code, _description, _module in PERMISSIONS)
    op.execute(
        "INSERT INTO role_permissions (role_id, permission_id, created_at) "
        "SELECT r.id, p.id, now() FROM roles r CROSS JOIN permissions p "
        "WHERE r.name IN ('SUPER_ADMIN', 'RECURSOS_HUMANOS') "
        "AND r.is_system IS TRUE AND r.company_id IS NULL AND r.deleted_at IS NULL "
        f"AND p.deleted_at IS NULL AND p.code IN ({permission_codes}) ON CONFLICT DO NOTHING"
    )
    op.create_table(
        "document_categories",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("module", sa.String(32), nullable=False),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("group_name", sa.String(120), nullable=False, server_default="General"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint(
            "company_id", "module", "code", name="uq_document_categories_company_module_code"
        ),
        sa.CheckConstraint(
            "module IN ('general','employees')", name="ck_document_categories_module"
        ),
    )
    op.create_index(
        "uq_document_categories_company_module_name",
        "document_categories",
        ["company_id", "module", sa.text("lower(name)")],
        unique=True,
    )
    op.create_index(
        "ix_document_categories_company_module_active",
        "document_categories",
        ["company_id", "module", "is_active"],
    )

    op.create_table(
        "document_records",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("module", sa.String(32), nullable=False, server_default="general"),
        sa.Column("owner_type", sa.String(32), nullable=True),
        sa.Column("owner_id", UUID(as_uuid=True), nullable=True),
        sa.Column("category_id", UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("reference_code", sa.String(120), nullable=True),
        sa.Column("issuer", sa.String(180), nullable=True),
        sa.Column("issued_on", sa.Date(), nullable=True),
        sa.Column("expires_on", sa.Date(), nullable=True),
        sa.Column("confidentiality", sa.String(16), nullable=False, server_default="restricted"),
        sa.Column("tags", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("version_group_id", UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("replaces_document_id", UUID(as_uuid=True), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["id"], ["document_assets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["category_id"], ["document_categories.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["replaces_document_id"], ["document_records.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint("module IN ('general','employees')", name="ck_document_records_module"),
        sa.CheckConstraint(
            "(module = 'general' AND owner_type IS NULL AND owner_id IS NULL) OR "
            "(module = 'employees' AND owner_type = 'employee' AND owner_id IS NOT NULL)",
            name="ck_document_records_owner",
        ),
        sa.CheckConstraint(
            "confidentiality IN ('internal','restricted')",
            name="ck_document_records_confidentiality",
        ),
        sa.CheckConstraint("version_number > 0", name="ck_document_records_version_positive"),
        sa.CheckConstraint(
            "expires_on IS NULL OR issued_on IS NULL OR expires_on >= issued_on",
            name="ck_document_records_dates",
        ),
        sa.UniqueConstraint(
            "version_group_id", "version_number", name="uq_document_records_version"
        ),
    )
    op.create_index(
        "uq_document_records_current_version",
        "document_records",
        ["version_group_id"],
        unique=True,
        postgresql_where=sa.text("is_current IS TRUE"),
    )
    op.create_index(
        "ix_document_records_company_module_owner",
        "document_records",
        ["company_id", "module", "owner_type", "owner_id"],
    )
    op.create_index(
        "ix_document_records_company_category", "document_records", ["company_id", "category_id"]
    )
    op.create_index(
        "ix_document_records_company_expiry", "document_records", ["company_id", "expires_on"]
    )
    op.create_index(
        "ix_document_records_group_current", "document_records", ["version_group_id", "is_current"]
    )

    _seed_categories()

    # Existing technical assets become general records.  Existing rejected or
    # pending assets are retained so maintenance can finish their lifecycle.
    op.execute(
        """
        INSERT INTO document_records
          (id, company_id, module, category_id, title, confidentiality,
           version_group_id, version_number, is_current, created_at, updated_at)
        SELECT a.id, a.company_id, 'general', c.id, left(a.original_filename, 200),
               'internal', gen_random_uuid(), 1, true, a.created_at, a.updated_at
        FROM document_assets a
        JOIN document_categories c
          ON c.company_id = a.company_id AND c.module = 'general' AND c.code = 'other'
        ON CONFLICT (id) DO NOTHING
        """
    )


def downgrade() -> None:
    # Business records are dependent on assets and can be removed safely when
    # rolling back this additive revision.  Permission/catalogue rows are left
    # intact because they may be referenced by user-managed roles.
    op.drop_table("document_records")
    op.drop_table("document_categories")
    permission_codes = ",".join(_literal(code) for code, _description, _module in PERMISSIONS)
    op.execute(
        "DELETE FROM role_permissions WHERE permission_id IN "
        f"(SELECT id FROM permissions WHERE code IN ({permission_codes}))"
    )
    op.execute(f"DELETE FROM permissions WHERE code IN ({permission_codes})")
