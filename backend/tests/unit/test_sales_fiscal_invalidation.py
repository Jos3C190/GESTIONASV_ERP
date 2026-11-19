"""V4b: qué se puede invalidar o corregir, el motivo y el solicitante."""

from __future__ import annotations

import pytest
from app.core.exceptions import BusinessRuleError
from app.domain.entities.sales_fiscal_document import ACTIVE_STATUSES, FiscalDocumentStatus
from app.domain.entities.sales_fiscal_invalidation import (
    require_correctable,
    require_invalidatable,
    validate_reason,
    validate_requester,
)

S = FiscalDocumentStatus


def _code(call: object) -> str:
    with pytest.raises(BusinessRuleError) as raised:
        call()  # type: ignore[operator]
    return raised.value.code


def test_only_sealed_documents_without_work_in_progress_are_invalidated() -> None:
    for status in (S.ISSUED, S.SIMULATED):
        require_invalidatable(status, superseded=False, pending_invalidation=False)
    for status in (S.PENDING, S.CONTINGENCY, S.REJECTED, S.FAILED, S.INVALIDATED):
        assert (
            _code(
                lambda s=status: require_invalidatable(
                    s, superseded=False, pending_invalidation=False
                )
            )
            == "sales_invoice_not_invalidatable"
        )
    assert (
        _code(lambda: require_invalidatable(S.ISSUED, superseded=False, pending_invalidation=True))
        == "sales_invoice_invalidation_in_progress"
    )
    assert (
        _code(lambda: require_invalidatable(S.ISSUED, superseded=True, pending_invalidation=False))
        == "sales_invoice_replacement_in_progress"
    )


def test_correction_applies_to_invoices_and_tax_credit_vouchers() -> None:
    require_correctable(S.SIMULATED, "03", superseded=False, pending_invalidation=False)
    assert (
        _code(
            lambda: require_correctable(
                S.ISSUED, "05", superseded=False, pending_invalidation=False
            )
        )
        == "sales_invoice_not_correctable"
    )


def test_reason_and_requester() -> None:
    assert validate_reason("  El cliente desistió  ") == "El cliente desistió"
    for reason in (None, "", "abc", "x" * 201):
        assert (
            _code(lambda r=reason: validate_reason(r))
            == "sales_invoice_invalidation_reason_required"
        )
    person = validate_requester(" María Rivas ", "13", "01234567-8")
    assert (person.name, person.document_type) == ("María Rivas", "13")
    assert (
        _code(lambda: validate_requester("María", "99", "1")) == "sales_invoice_requester_invalid"
    )


def test_rejected_and_invalidated_documents_do_not_block_the_order() -> None:
    assert S.REJECTED not in ACTIVE_STATUSES
    assert S.INVALIDATED not in ACTIVE_STATUSES
    assert S.CONTINGENCY in ACTIVE_STATUSES
