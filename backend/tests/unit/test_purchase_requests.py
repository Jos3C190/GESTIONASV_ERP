from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from app.domain.entities.purchase_request import (
    PurchaseRequest,
    PurchaseRequestDetail,
    PurchaseRequestStatus,
    PurchaseRequestTransitionError,
    ensure_purchase_request_transition,
)


def _detail(
    request_id: uuid.UUID,
    *,
    quantity: Decimal = Decimal("2.500000"),
) -> PurchaseRequestDetail:
    return PurchaseRequestDetail(
        id=uuid.uuid4(),
        purchase_request_id=request_id,
        product_id=1,
        unit_id=1,
        quantity=quantity,
    )


def _request(
    *,
    status: PurchaseRequestStatus = PurchaseRequestStatus.DRAFT,
) -> PurchaseRequest:
    request_id = uuid.uuid4()
    return PurchaseRequest(
        id=request_id,
        company_id=uuid.uuid4(),
        code="SCR-00001",
        branch_id=uuid.uuid4(),
        warehouse_id=uuid.uuid4(),
        requested_by_id=uuid.uuid4(),
        request_date=datetime.now(UTC),
        justification="Reposición de inventario",
        details=(_detail(request_id),),
        status=status,
    )


def test_purchase_request_statuses_cover_procurement_workflow() -> None:
    assert {status.value for status in PurchaseRequestStatus} == {
        "draft",
        "submitted",
        "approved",
        "rejected",
        "partially_quoted",
        "quoted",
        "partially_ordered",
        "completed",
        "cancelled",
    }


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (PurchaseRequestStatus.DRAFT, PurchaseRequestStatus.SUBMITTED),
        (PurchaseRequestStatus.SUBMITTED, PurchaseRequestStatus.APPROVED),
        (PurchaseRequestStatus.SUBMITTED, PurchaseRequestStatus.REJECTED),
        (PurchaseRequestStatus.APPROVED, PurchaseRequestStatus.PARTIALLY_QUOTED),
        (PurchaseRequestStatus.APPROVED, PurchaseRequestStatus.QUOTED),
        (PurchaseRequestStatus.PARTIALLY_QUOTED, PurchaseRequestStatus.QUOTED),
        (PurchaseRequestStatus.QUOTED, PurchaseRequestStatus.PARTIALLY_ORDERED),
        (PurchaseRequestStatus.QUOTED, PurchaseRequestStatus.COMPLETED),
        (PurchaseRequestStatus.PARTIALLY_ORDERED, PurchaseRequestStatus.COMPLETED),
    ],
)
def test_allows_expected_procurement_transitions(
    current: PurchaseRequestStatus,
    target: PurchaseRequestStatus,
) -> None:
    ensure_purchase_request_transition(current, target)


def test_rejects_illegal_transition() -> None:
    with pytest.raises(PurchaseRequestTransitionError) as rejected:
        ensure_purchase_request_transition(
            PurchaseRequestStatus.DRAFT,
            PurchaseRequestStatus.COMPLETED,
        )

    assert rejected.value.current is PurchaseRequestStatus.DRAFT
    assert rejected.value.target is PurchaseRequestStatus.COMPLETED


@pytest.mark.parametrize(
    "status",
    [PurchaseRequestStatus.DRAFT, PurchaseRequestStatus.SUBMITTED],
)
def test_allows_cancellation_before_approval(status: PurchaseRequestStatus) -> None:
    ensure_purchase_request_transition(status, PurchaseRequestStatus.CANCELLED)


@pytest.mark.parametrize("quantity", [Decimal("0"), Decimal("-1"), Decimal("NaN")])
def test_detail_requires_positive_finite_quantity(quantity: Decimal) -> None:
    with pytest.raises(ValueError, match="mayor que cero"):
        _detail(uuid.uuid4(), quantity=quantity)


def test_request_requires_at_least_one_detail() -> None:
    with pytest.raises(ValueError, match="al menos un detalle"):
        PurchaseRequest(
            id=uuid.uuid4(),
            company_id=uuid.uuid4(),
            code="SCR-00001",
            branch_id=uuid.uuid4(),
            warehouse_id=uuid.uuid4(),
            requested_by_id=uuid.uuid4(),
            request_date=datetime.now(UTC),
            justification="Reposición",
            details=(),
        )


@pytest.mark.parametrize(
    ("code", "justification"),
    [("", "Reposición"), ("SCR-00001", "   ")],
)
def test_request_requires_code_and_justification(code: str, justification: str) -> None:
    request_id = uuid.uuid4()
    with pytest.raises(ValueError, match="obligatori"):
        PurchaseRequest(
            id=request_id,
            company_id=uuid.uuid4(),
            code=code,
            branch_id=uuid.uuid4(),
            warehouse_id=uuid.uuid4(),
            requested_by_id=uuid.uuid4(),
            request_date=datetime.now(UTC),
            justification=justification,
            details=(_detail(request_id),),
        )


def test_request_rejects_detail_from_another_request() -> None:
    with pytest.raises(ValueError, match="pertenecer"):
        PurchaseRequest(
            id=uuid.uuid4(),
            company_id=uuid.uuid4(),
            code="SCR-00001",
            branch_id=uuid.uuid4(),
            warehouse_id=uuid.uuid4(),
            requested_by_id=uuid.uuid4(),
            request_date=datetime.now(UTC),
            justification="Reposición",
            details=(_detail(uuid.uuid4()),),
        )


def test_request_defaults_to_draft() -> None:
    assert _request().status is PurchaseRequestStatus.DRAFT
