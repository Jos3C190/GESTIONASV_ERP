import hashlib
import json
from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from app.api.v1.schemas.inventory_labels import (
    InventoryLabelConfirmationIn,
    InventoryLabelPreviewIn,
    InventoryLabelPrintIn,
)
from app.core.exceptions import ConflictError, NotFoundError
from app.domain.entities.inventory_label import (
    LabelPrintLayout,
    print_fingerprint,
    validate_print_reason,
)
from app.domain.entities.purchase import PurchaseInventoryWorkflow
from app.infrastructure.models.inventory_valuation import InventoryValuationSettingModel
from app.infrastructure.repositories.inventory_label_repository import (
    SqlAlchemyInventoryLabelRepository,
    _presentation_equivalence,
)
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.dialects import postgresql


class ConfirmationSession:
    def __init__(self, scalar_results):
        self.scalar_results = list(scalar_results)
        self.scalar_statements = []
        self.execute = AsyncMock()
        self.added = []
        self.flush = AsyncMock()

    async def scalar(self, statement):
        self.scalar_statements.append(statement)
        return self.scalar_results.pop(0)

    def add(self, value):
        self.added.append(value)


def confirmation_fingerprint(handling_unit_id, handling_unit_code, label_print_id):
    payload = {
        "handling_unit_id": str(handling_unit_id),
        "handling_unit_code": handling_unit_code,
        "label_print_id": str(label_print_id),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def handling_unit(*, unit_id, code="HU-0001", revision=1, quantity="12"):
    return SimpleNamespace(
        id=unit_id,
        code=code,
        label_revision=revision,
        quantity_base=Decimal(quantity),
        closed_at=None,
    )


def printed_label(*, print_id, code="HU-0001", revision=1, quantity="12"):
    return SimpleNamespace(
        id=print_id,
        label_snapshot={
            "handling_unit_code": code,
            "label_revision": revision,
            "quantity_base": str(Decimal(quantity)),
        },
    )


async def confirm_label(session, *, company_id, unit_id, code, print_id, key="confirm-1"):
    repository = SqlAlchemyInventoryLabelRepository(session)  # type: ignore[arg-type]
    return await repository.confirm_handling_unit_label(
        company_id=company_id,
        handling_unit_id=unit_id,
        handling_unit_code=code,
        label_print_id=print_id,
        idempotency_key=key,
        actor_id=uuid4(),
    )


def test_label_target_requires_exactly_one_lot_line_or_handling_unit() -> None:
    lot_detail_id = uuid4()
    handling_unit_id = uuid4()

    assert InventoryLabelPreviewIn(
        inventory_lot_detail_id=lot_detail_id
    ).inventory_lot_detail_id == (lot_detail_id)
    assert InventoryLabelPreviewIn(handling_unit_id=handling_unit_id).handling_unit_id == (
        handling_unit_id
    )
    with pytest.raises(PydanticValidationError):
        InventoryLabelPreviewIn()
    with pytest.raises(PydanticValidationError):
        InventoryLabelPreviewIn(
            inventory_lot_detail_id=lot_detail_id,
            handling_unit_id=handling_unit_id,
        )


@pytest.mark.asyncio
async def test_label_preview_explains_when_an_existing_unit_has_no_receipt_lot() -> None:
    company_id = uuid4()
    handling_unit_id = uuid4()

    class UnitWithoutLotSession:
        execute = AsyncMock(return_value=SimpleNamespace(one_or_none=lambda: None))
        scalar = AsyncMock(return_value=handling_unit_id)

    session = UnitWithoutLotSession()
    repository = SqlAlchemyInventoryLabelRepository(session)  # type: ignore[arg-type]

    with pytest.raises(ConflictError) as error:
        await repository._resolve_target(
            company_id=company_id,
            inventory_lot_detail_id=None,
            handling_unit_id=handling_unit_id,
        )

    assert error.value.code == "inventory_label_receipt_lot_required"
    assert "no está vinculada a un lote de recepción" in str(error.value)
    query = session.scalar.await_args.args[0]
    sql = str(query.compile(dialect=postgresql.dialect()))
    assert "inventory_handling_units.company_id =" in sql
    assert "inventory_handling_units.id =" in sql
    assert "inventory_handling_units.inventory_lot_id IS NULL" in sql


def test_label_print_request_validates_quantity_and_reason() -> None:
    body = InventoryLabelPrintIn(
        idempotency_key="label-print-0001",
        inventory_lot_detail_id=uuid4(),
        quantity_printed=3,
        print_date=date(2026, 10, 13),
        reason="initial",
    )
    assert body.quantity_printed == 3

    with pytest.raises(PydanticValidationError):
        InventoryLabelPrintIn(
            idempotency_key="label-print-0001",
            inventory_lot_detail_id=uuid4(),
            quantity_printed=0,
            print_date=date(2026, 10, 13),
            reason="initial",
        )


def test_label_confirmation_request_requires_print_and_idempotency_key() -> None:
    body = InventoryLabelConfirmationIn(
        idempotency_key="label-confirm-0001",
        handling_unit_id=uuid4(),
        handling_unit_code="HU-0001",
        label_print_id=uuid4(),
    )
    assert body.handling_unit_code == "HU-0001"
    with pytest.raises(PydanticValidationError):
        InventoryLabelConfirmationIn(
            idempotency_key="x",
            handling_unit_id=uuid4(),
            handling_unit_code="HU-0001",
            label_print_id=uuid4(),
        )


@pytest.mark.parametrize(("content", "width", "height"), [("qr", 25, 35), ("barcode", 50, 25)])
def test_label_layout_reserves_space_for_visible_product_lot_and_dates(content, width, height):
    with pytest.raises(ValueError, match="producto, lote y fechas"):
        LabelPrintLayout(content, width, height)


def test_label_notes_are_optional_and_limited_without_changing_required_trace_data():
    values = {
        "idempotency_key": "label-notes-0001",
        "handling_unit_id": uuid4(),
        "quantity_printed": 1,
        "print_date": date(2026, 10, 28),
        "reason": "initial",
    }
    assert InventoryLabelPrintIn(**values).notes is None
    assert InventoryLabelPrintIn(**values, notes="Mantener seco").notes == "Mantener seco"
    with pytest.raises(PydanticValidationError):
        InventoryLabelPrintIn(**values, notes="x" * 161)


@pytest.mark.asyncio
async def test_label_print_snapshots_notes_receipt_date_and_lot_without_stock_writes():
    company_id, lot_id, unit_id = uuid4(), uuid4(), uuid4()
    session = AsyncMock()
    session.add = lambda entry: added.append(entry)
    added = []
    repo = SqlAlchemyInventoryLabelRepository(session)
    repo._lock_target = AsyncMock()
    repo.get_by_key = AsyncMock(return_value=None)
    repo.preview = AsyncMock(
        return_value={
            "inventory_lot_id": lot_id,
            "inventory_item_id": uuid4(),
            "product_internal_code": "INT-004",
            "product_name": "Azúcar Glass Premium 10kg",
            "receipt_lot_code": "LOT-COM-00027",
            "receipt_lot_header_code": "LOT-COM-00027",
            "manufacturer_lot_code": "FAB-01",
            "received_on": date(2026, 10, 28),
            "quantity_base": Decimal("10"),
            "base_unit_symbol": "cj",
            "expiry_date": date(2027, 2, 1),
            "handling_unit_code": "HU-0001",
            "label_revision": 1,
            "presentation_equivalence": None,
            "stock_status": "quarantine",
            "print_count": 0,
        }
    )
    entry, created = await repo.register_print(
        company_id=company_id,
        inventory_lot_detail_id=None,
        handling_unit_id=unit_id,
        idempotency_key="label-notes-0001",
        quantity_printed=2,
        print_date=date(2026, 10, 29),
        reason="initial",
        actor_id=uuid4(),
        layout=LabelPrintLayout("barcode", 80, 50),
        notes="  Mantener seco  ",
    )
    assert created
    assert added == [entry]
    assert entry.label_snapshot["notes"] == "Mantener seco"
    assert entry.label_snapshot["received_on"] == "2026-10-28"
    assert entry.label_snapshot["receipt_lot_code"] == "LOT-COM-00027"
    assert entry.label_snapshot["expiry_date"] == "2027-02-01"
    assert entry.quantity_printed == 2
    session.flush.assert_awaited_once()
    repo.get_by_key = AsyncMock(return_value=entry)
    replay, replay_created = await repo.register_print(
        company_id=company_id,
        inventory_lot_detail_id=None,
        handling_unit_id=unit_id,
        idempotency_key="label-notes-0001",
        quantity_printed=2,
        print_date=date(2026, 10, 29),
        reason="initial",
        actor_id=uuid4(),
        layout=LabelPrintLayout("barcode", 80, 50),
        notes="Mantener seco",
    )
    assert replay is entry
    assert not replay_created
    assert added == [entry]
    with pytest.raises(ConflictError, match="otros datos"):
        await repo.register_print(
            company_id=company_id,
            inventory_lot_detail_id=None,
            handling_unit_id=unit_id,
            idempotency_key="label-notes-0001",
            quantity_printed=2,
            print_date=date(2026, 10, 29),
            reason="initial",
            actor_id=uuid4(),
            layout=LabelPrintLayout("barcode", 80, 50),
            notes="Distinta nota",
        )


@pytest.mark.asyncio
async def test_preview_applies_the_persisted_new_workflow_closure_requirement():
    repo = SqlAlchemyInventoryLabelRepository(AsyncMock())
    repo._resolve_target = AsyncMock(
        return_value={
            "lot": SimpleNamespace(purchase_id=uuid4(), received_at=datetime.now(UTC)),
            "item": SimpleNamespace(is_active=True),
            "product": SimpleNamespace(),
            "variant": None,
            "unit": None,
            "company_unit": None,
            "purchase": SimpleNamespace(
                status="verified", inventory_workflow=PurchaseInventoryWorkflow.AFTER_RETACEO.value
            ),
        }
    )
    repo._ensure_retaceo_final = AsyncMock(side_effect=ConflictError("Cierre pendiente"))
    with pytest.raises(ConflictError):
        await repo.preview(company_id=uuid4(), handling_unit_id=uuid4())
    assert repo._ensure_retaceo_final.await_args.kwargs["require_closed"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [None, "cancelled", "draft", "calculated", "verified", "closed"])
async def test_new_workflow_labels_require_a_closed_retaceo_even_without_valuation(status):
    class Rows:
        def all(self):
            return [] if status is None else [SimpleNamespace(status=status, applied_at=None)]

    session = AsyncMock()
    session.scalars.return_value = Rows()
    session.get.return_value = None
    repo = SqlAlchemyInventoryLabelRepository(session)
    if status == "closed":
        await repo._ensure_retaceo_final(uuid4(), uuid4(), datetime.now(UTC), require_closed=True)
    else:
        with pytest.raises(ConflictError) as failure:
            await repo._ensure_retaceo_final(
                uuid4(), uuid4(), datetime.now(UTC), require_closed=True
            )
        assert failure.value.code == "inventory_label_retaceo_not_final"


def test_label_presentation_shows_package_equivalence_without_changing_quantity() -> None:
    assert (
        _presentation_equivalence(
            {"packaging_type": "box", "base_quantity": "12"},
            "24.000000",
            "unidad",
        )
        == "2 cajas × 12 unidad = 24 unidad"
    )


def test_initial_print_and_reprint_follow_print_history() -> None:
    validate_print_reason("initial", 0)
    validate_print_reason("reprint", 1)

    with pytest.raises(ConflictError, match="impresión inicial"):
        validate_print_reason("initial", 1)
    with pytest.raises(ConflictError, match="tirada inicial"):
        validate_print_reason("reprint", 0)


def test_print_fingerprint_is_stable_and_detects_payload_changes() -> None:
    first = {"target": str(uuid4()), "reason": "initial", "quantity_printed": 1}
    reordered = {
        "quantity_printed": 1,
        "reason": "initial",
        "target": first["target"],
    }

    assert print_fingerprint(first) == print_fingerprint(reordered)
    assert print_fingerprint(first) != print_fingerprint({**first, "quantity_printed": 2})


@pytest.mark.asyncio
async def test_print_registration_replays_same_idempotency_key_and_rejects_reuse() -> None:
    company_id = uuid4()
    lot_detail_id = uuid4()
    payload = {
        "inventory_lot_detail_id": str(lot_detail_id),
        "handling_unit_id": None,
        "quantity_printed": 2,
        "print_date": "2026-10-13",
        "reason": "initial",
    }
    fingerprint = print_fingerprint(payload)
    existing = type("PrintRecord", (), {"fingerprint": fingerprint})()
    repository = SqlAlchemyInventoryLabelRepository(AsyncMock())
    repository._lock_target = AsyncMock()
    repository.get_by_key = AsyncMock(return_value=existing)

    entry, created = await repository.register_print(
        company_id=company_id,
        inventory_lot_detail_id=lot_detail_id,
        handling_unit_id=None,
        idempotency_key="label-receipt-001",
        quantity_printed=2,
        print_date=date(2026, 10, 13),
        reason="initial",
        actor_id=uuid4(),
    )

    assert entry is existing
    assert created is False
    repository._lock_target.assert_awaited_once()

    repository.get_by_key = AsyncMock(return_value=type("PrintRecord", (), {"fingerprint": "x"})())
    with pytest.raises(ConflictError, match="ya se usó con otros datos"):
        await repository.register_print(
            company_id=company_id,
            inventory_lot_detail_id=lot_detail_id,
            handling_unit_id=None,
            idempotency_key="label-receipt-001",
            quantity_printed=3,
            print_date=date(2026, 10, 13),
            reason="initial",
            actor_id=uuid4(),
        )


@pytest.mark.asyncio
async def test_confirmation_requires_a_print_scoped_to_company_and_handling_unit() -> None:
    company_id, unit_id, print_id = uuid4(), uuid4(), uuid4()
    session = ConfirmationSession(
        [None, handling_unit(unit_id=unit_id), None]
    )  # A foreign or nonexistent print is invisible to the scoped lookup.

    with pytest.raises(ConflictError) as error:
        await confirm_label(
            session,
            company_id=company_id,
            unit_id=unit_id,
            code="HU-0001",
            print_id=print_id,
        )

    assert error.value.code == "inventory_label_print_required"
    print_lookup = str(session.scalar_statements[2].compile(dialect=postgresql.dialect()))
    assert "inventory_label_prints.company_id =" in print_lookup
    assert "inventory_label_prints.handling_unit_id =" in print_lookup


@pytest.mark.asyncio
async def test_confirmation_rejects_missing_or_foreign_handling_unit() -> None:
    company_id, unit_id, print_id = uuid4(), uuid4(), uuid4()
    session = ConfirmationSession([None, None])

    with pytest.raises(ConflictError) as error:
        await confirm_label(
            session,
            company_id=company_id,
            unit_id=unit_id,
            code="HU-0001",
            print_id=print_id,
        )

    assert error.value.code == "inventory_label_confirmation_unit_changed"
    assert session.added == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("unit_revision", "unit_quantity"),
    [(2, "6"), (1, "10")],
    ids=["split-revision-changed", "quantity-changed"],
)
async def test_confirmation_rejects_print_from_obsolete_unit_revision_or_quantity(
    unit_revision, unit_quantity
) -> None:
    company_id, unit_id, print_id = uuid4(), uuid4(), uuid4()
    unit = handling_unit(
        unit_id=unit_id, code="HU-0001", revision=unit_revision, quantity=unit_quantity
    )
    old_print = printed_label(print_id=print_id, code="HU-0001", revision=1, quantity="12")
    session = ConfirmationSession([None, unit, old_print])

    with pytest.raises(ConflictError) as error:
        await confirm_label(
            session,
            company_id=company_id,
            unit_id=unit_id,
            code="HU-0001",
            print_id=print_id,
        )

    assert error.value.code == "inventory_label_print_stale"
    assert session.added == []


@pytest.mark.asyncio
async def test_split_child_cannot_inherit_parent_label_confirmation() -> None:
    company_id, parent_id, child_id, parent_print_id, child_print_id = (
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
    )
    parent_session = ConfirmationSession(
        [
            None,
            handling_unit(unit_id=parent_id, revision=2, quantity="6"),
            printed_label(print_id=parent_print_id, revision=1, quantity="12"),
        ]
    )
    with pytest.raises(ConflictError, match="versión anterior"):
        await confirm_label(
            parent_session,
            company_id=company_id,
            unit_id=parent_id,
            code="HU-0001",
            print_id=parent_print_id,
            key="split-parent-confirm",
        )

    child_session = ConfirmationSession(
        [None, handling_unit(unit_id=child_id, code="HU-0001-F01", quantity="6"), None]
    )
    with pytest.raises(ConflictError) as error:
        await confirm_label(
            child_session,
            company_id=company_id,
            unit_id=child_id,
            code="HU-0001-F01",
            print_id=child_print_id,
            key="split-child-confirm",
        )
    assert error.value.code == "inventory_label_print_required"


@pytest.mark.asyncio
async def test_confirmation_replay_is_idempotent_and_conflicting_payload_is_rejected() -> None:
    company_id, unit_id, print_id = uuid4(), uuid4(), uuid4()
    fingerprint = confirmation_fingerprint(unit_id, "HU-0001", print_id)
    existing = SimpleNamespace(request_fingerprint=fingerprint)
    same_session = ConfirmationSession([existing])

    result, created = await confirm_label(
        same_session,
        company_id=company_id,
        unit_id=unit_id,
        code="HU-0001",
        print_id=print_id,
        key="same-request",
    )

    assert result is existing
    assert created is False
    assert same_session.added == []
    same_session.flush.assert_not_awaited()

    conflicting_session = ConfirmationSession([SimpleNamespace(request_fingerprint="other")])
    with pytest.raises(ConflictError) as error:
        await confirm_label(
            conflicting_session,
            company_id=company_id,
            unit_id=unit_id,
            code="HU-0001",
            print_id=print_id,
            key="same-request",
        )
    assert error.value.code == "inventory_label_confirmation_idempotency_conflict"


@pytest.mark.asyncio
async def test_confirmation_records_explicit_placement_once_and_reuses_existing_revision() -> None:
    company_id, unit_id, print_id = uuid4(), uuid4(), uuid4()
    unit = handling_unit(unit_id=unit_id)
    label_print = printed_label(print_id=print_id)
    session = ConfirmationSession([None, unit, label_print, None])

    confirmation, created = await confirm_label(
        session,
        company_id=company_id,
        unit_id=unit_id,
        code="HU-0001",
        print_id=print_id,
    )

    assert created is True
    assert confirmation.handling_unit_id == unit_id
    assert confirmation.label_print_id == print_id
    assert confirmation.label_revision == 1
    assert confirmation.quantity_base == Decimal("12")
    assert len(session.added) == 1
    session.flush.assert_awaited_once()

    saved_revision = SimpleNamespace(handling_unit_code="HU-0001", quantity_base=Decimal("12"))
    duplicate_session = ConfirmationSession([None, unit, label_print, saved_revision])
    result, duplicate_created = await confirm_label(
        duplicate_session,
        company_id=company_id,
        unit_id=unit_id,
        code="HU-0001",
        print_id=print_id,
        key="another-confirmation-key",
    )
    assert result is saved_revision
    assert duplicate_created is False
    assert duplicate_session.added == []
    duplicate_session.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_preview_lookup_is_company_scoped_for_receipt_lot_detail() -> None:
    class EmptyResult:
        @staticmethod
        def one_or_none() -> None:
            return None

    class CaptureSession:
        statement = None

        async def execute(self, statement):
            self.statement = statement
            return EmptyResult()

    session = CaptureSession()
    repository = SqlAlchemyInventoryLabelRepository(session)  # type: ignore[arg-type]

    with pytest.raises(NotFoundError):
        await repository.preview(company_id=uuid4(), inventory_lot_detail_id=uuid4())

    sql = str(session.statement.compile(dialect=postgresql.dialect()))
    assert "inventory_lot_details.company_id =" in sql


@pytest.mark.asyncio
async def test_final_legacy_retaceo_without_application_does_not_block_old_receipt_labels() -> None:
    class Rows:
        def all(self):
            return [SimpleNamespace(status="verified", applied_at=None)]

    class Session:
        async def scalars(self, _statement):
            return Rows()

        async def get(self, model, _key):
            assert model is InventoryValuationSettingModel
            return SimpleNamespace(opened_at=datetime(2026, 10, 1, tzinfo=UTC))

        async def scalar(self, _statement):
            pytest.fail("No debe exigir aplicación para una recepción previa al corte.")

    repository = SqlAlchemyInventoryLabelRepository(Session())  # type: ignore[arg-type]
    await repository._ensure_retaceo_final(uuid4(), uuid4(), datetime(2026, 9, 30, tzinfo=UTC))


@pytest.mark.asyncio
async def test_cancelled_retaceo_does_not_block_label_and_active_draft_does() -> None:
    class Rows:
        def __init__(self, retaceos):
            self.retaceos = retaceos

        def all(self):
            return self.retaceos

    class Session:
        def __init__(self, retaceos):
            self.retaceos = retaceos

        async def scalars(self, _statement):
            return Rows(self.retaceos)

        async def get(self, _model, _key):
            return None

        async def scalar(self, _statement):
            return None

    repository = SqlAlchemyInventoryLabelRepository(
        Session([SimpleNamespace(status="cancelled", applied_at=None)])
    )  # type: ignore[arg-type]
    await repository._ensure_retaceo_final(uuid4(), uuid4(), datetime(2026, 9, 30, tzinfo=UTC))

    repository = SqlAlchemyInventoryLabelRepository(
        Session([SimpleNamespace(status="draft", applied_at=None)])
    )  # type: ignore[arg-type]
    with pytest.raises(ConflictError) as error:
        await repository._ensure_retaceo_final(uuid4(), uuid4(), datetime(2026, 9, 30, tzinfo=UTC))
    assert error.value.code == "inventory_label_retaceo_not_final"


@pytest.mark.asyncio
async def test_valued_receipt_requires_retaceo_application_after_cutover() -> None:
    class Rows:
        def __init__(self, values):
            self.values = values

        def all(self):
            return self.values

    class Session:
        def __init__(self):
            self.retaceo = SimpleNamespace(id=uuid4(), status="verified", applied_at=None)
            self.query_count = 0

        async def scalars(self, _statement):
            self.query_count += 1
            return Rows([self.retaceo] if self.query_count == 1 else [])

        async def get(self, _model, _key):
            return SimpleNamespace(opened_at=datetime(2026, 10, 1, tzinfo=UTC))

        async def scalar(self, _statement):
            return None

    repository = SqlAlchemyInventoryLabelRepository(Session())  # type: ignore[arg-type]
    with pytest.raises(ConflictError) as error:
        await repository._ensure_retaceo_final(uuid4(), uuid4(), datetime(2026, 10, 2, tzinfo=UTC))
    assert error.value.code == "inventory_label_retaceo_cost_unapplied"
