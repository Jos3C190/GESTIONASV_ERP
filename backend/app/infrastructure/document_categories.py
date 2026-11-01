"""Default document category catalogue and company bootstrap helper."""

from __future__ import annotations

import uuid
from collections.abc import Iterable

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.models.document_record import DocumentCategoryModel

GENERAL_CATEGORY_SEEDS: tuple[tuple[str, str, str], ...] = (("other", "Otros", "General"),)

EMPLOYEE_CATEGORY_SEEDS: tuple[tuple[str, str, str], ...] = (
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
    ("driver_license", "Licencia de conducir", "Conducción"),
    ("other", "Otros", "General"),
)

FLEET_CATEGORY_SEEDS: tuple[tuple[str, str, str], ...] = (
    ("circulation_card", "Tarjeta de circulación", "Documentos legales"),
    ("insurance_policy", "Póliza de seguro", "Documentos legales"),
    ("technical_inspection", "Revisión técnica", "Documentos legales"),
    ("transport_permit", "Permiso de transporte", "Documentos legales"),
    ("purchase_invoice", "Factura de compra", "Adquisición"),
    ("fuel_receipt", "Comprobante de combustible", "Operación"),
    ("maintenance_invoice", "Factura de mantenimiento", "Operación"),
    ("accident_report", "Reporte de accidente", "Operación"),
    ("other", "Otros", "General"),
)

#: (module, code) -> (requires_expiry, compliance_required). Las categorías obligatorias
#: son las que bloquean asignaciones y despachos cuando faltan o están vencidas.
CATEGORY_RULES: dict[tuple[str, str], tuple[bool, bool]] = {
    ("employees", "driver_license"): (True, True),
    ("fleet", "circulation_card"): (True, True),
    ("fleet", "insurance_policy"): (True, True),
    ("fleet", "technical_inspection"): (True, True),
    ("fleet", "transport_permit"): (True, False),
}

#: Categorías de empleados que gestiona el módulo Conductores.
DRIVER_CATEGORY_CODES: frozenset[str] = frozenset({"driver_license"})


def _rows(
    company_id: uuid.UUID,
    actor_id: uuid.UUID | None,
    seeds: Iterable[tuple[str, str, str]],
    *,
    module: str,
    start_order: int = 0,
) -> list[dict[str, object]]:
    return [
        {
            "id": uuid.uuid4(),
            "company_id": company_id,
            "module": module,
            "code": code,
            "name": name,
            "group_name": group_name,
            "sort_order": start_order + offset,
            "is_active": True,
            "requires_expiry": CATEGORY_RULES.get((module, code), (False, False))[0],
            "compliance_required": CATEGORY_RULES.get((module, code), (False, False))[1],
            "created_by": actor_id,
            "updated_by": actor_id,
        }
        for offset, (code, name, group_name) in enumerate(seeds)
    ]


async def ensure_default_document_categories(
    session: AsyncSession,
    company_id: uuid.UUID,
    actor_id: uuid.UUID | None = None,
) -> None:
    """Create the standard general/employee/fleet catalog for a new company.

    The unique company/module/code constraint makes this safe to call during
    retries or bootstrap repair jobs.
    """
    rows = _rows(company_id, actor_id, GENERAL_CATEGORY_SEEDS, module="general")
    rows.extend(
        _rows(company_id, actor_id, EMPLOYEE_CATEGORY_SEEDS, module="employees", start_order=1)
    )
    rows.extend(_rows(company_id, actor_id, FLEET_CATEGORY_SEEDS, module="fleet", start_order=1))
    statement = pg_insert(DocumentCategoryModel).values(rows)
    statement = statement.on_conflict_do_nothing(index_elements=["company_id", "module", "code"])
    await session.execute(statement)


__all__ = [
    "CATEGORY_RULES",
    "DRIVER_CATEGORY_CODES",
    "EMPLOYEE_CATEGORY_SEEDS",
    "FLEET_CATEGORY_SEEDS",
    "GENERAL_CATEGORY_SEEDS",
    "ensure_default_document_categories",
]
