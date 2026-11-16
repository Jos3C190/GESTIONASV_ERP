"""Reglas puras de protección de datos personales."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from app.core.exceptions import BusinessRuleError
from app.domain.entities.privacy import (
    NOTICE_ELEMENTS,
    IncidentNotifications,
    RequestAction,
    RequestState,
    RequestStatus,
    RightType,
    add_business_days,
    apply_action,
    easter_sunday,
    is_business_day,
    national_holidays,
    new_request_due,
    notice_template,
    notification_deadline,
    require_erasure_request,
    require_incident_closable,
    require_notice_complete,
)


def test_easter_and_holy_week() -> None:
    assert easter_sunday(2026) == date(2026, 4, 5)
    assert easter_sunday(2027) == date(2027, 3, 28)
    holidays = national_holidays(2026)
    assert {date(2026, 4, 2), date(2026, 4, 3), date(2026, 4, 4)} <= holidays
    assert date(2026, 6, 17) in holidays
    assert date(2026, 8, 6) in holidays


def test_business_days_skip_weekends_and_holidays() -> None:
    assert not is_business_day(date(2026, 11, 2))  # Día de los Difuntos
    assert not is_business_day(date(2026, 11, 14))  # sábado
    assert is_business_day(date(2026, 11, 16))
    # Viernes 30 de octubre + 1 día hábil: el lunes 2 de noviembre es asueto.
    assert add_business_days(date(2026, 10, 30), 1) == date(2026, 11, 3)
    # Recibida el lunes 16 de noviembre de 2026: vence el lunes 14 de diciembre.
    assert new_request_due(date(2026, 11, 16)) == date(2026, 12, 14)
    # Cruzando Navidad y Año Nuevo.
    # Miércoles 23 de diciembre: jueves 24 (1), el 25 es asueto, lunes 28 (2), martes 29 (3).
    assert add_business_days(date(2026, 12, 23), 3) == date(2026, 12, 29)


def _state(status: RequestStatus = RequestStatus.RECEIVED) -> RequestState:
    return RequestState(status, date(2026, 11, 16), date(2026, 12, 14), None, None)


def test_extension_adds_twenty_business_days_once() -> None:
    result = apply_action(
        _state(),
        RequestAction.EXTEND,
        today=date(2026, 11, 20),
        text=None,
        extension_reason="Hay que reunir registros de varias sucursales.",
    )
    assert result.status == RequestStatus.EXTENDED
    assert result.extended_due_on == add_business_days(date(2026, 12, 14), 20)
    with pytest.raises(BusinessRuleError) as again:
        apply_action(
            _state(RequestStatus.EXTENDED),
            RequestAction.EXTEND,
            today=date(2026, 11, 20),
            text=None,
            extension_reason="Otra vez más motivo",
        )
    assert again.value.code == "privacy_request_action_invalid"
    with pytest.raises(BusinessRuleError) as no_reason:
        apply_action(
            _state(),
            RequestAction.EXTEND,
            today=date(2026, 11, 20),
            text=None,
            extension_reason="x",
        )
    assert no_reason.value.code == "privacy_request_extension_reason_required"


def test_correction_and_archive() -> None:
    asked = apply_action(
        _state(),
        RequestAction.REQUEST_CORRECTION,
        today=date(2026, 11, 16),
        text="Falta copia del DUI",
        extension_reason=None,
    )
    assert asked.correction_due_on == add_business_days(date(2026, 11, 16), 10)
    waiting = RequestState(
        RequestStatus.AWAITING_CORRECTION,
        date(2026, 11, 16),
        date(2026, 12, 14),
        asked.correction_due_on,
        None,
    )
    with pytest.raises(BusinessRuleError) as early:
        apply_action(
            waiting,
            RequestAction.ARCHIVE,
            today=date(2026, 11, 20),
            text="El titular no completó",
            extension_reason=None,
        )
    assert early.value.code == "privacy_request_archive_too_early"
    archived = apply_action(
        waiting,
        RequestAction.ARCHIVE,
        today=date(2026, 12, 31),
        text="El titular no completó la solicitud a tiempo.",
        extension_reason=None,
    )
    assert archived.closes is True


def test_closing_needs_a_written_answer() -> None:
    with pytest.raises(BusinessRuleError) as exc:
        apply_action(
            _state(),
            RequestAction.RESOLVE,
            today=date(2026, 11, 20),
            text="ok",
            extension_reason=None,
        )
    assert exc.value.code == "privacy_request_resolution_required"
    done = apply_action(
        _state(RequestStatus.IN_PROGRESS),
        RequestAction.RESOLVE,
        today=date(2026, 11, 20),
        text="Se entregaron los datos por correo.",
        extension_reason=None,
    )
    assert (done.status, done.resolution) == (
        RequestStatus.RESOLVED,
        "Se entregaron los datos por correo.",
    )
    assert _state().overdue(date(2026, 12, 15)) is True
    assert _state().overdue(date(2026, 12, 14)) is False


def test_erasure_requires_a_working_cancellation_or_forgetting_request() -> None:
    require_erasure_request(RightType.ERASURE, RequestStatus.IN_PROGRESS)
    for right, status in (
        (RightType.ACCESS, RequestStatus.IN_PROGRESS),
        (RightType.CANCELLATION, RequestStatus.RESOLVED),
    ):
        with pytest.raises(BusinessRuleError) as exc:
            require_erasure_request(right, status)
        assert exc.value.code == "privacy_erasure_request_required"


def test_notice_must_cover_article_24() -> None:
    body = notice_template(
        company_name="Empresa ficticia", address="San Salvador", email="d@x.test", phone=None
    )
    assert "veinte días hábiles" in body
    covered = require_notice_complete("Aviso de privacidad", body, list(NOTICE_ELEMENTS))
    assert len(covered) == 9
    with pytest.raises(BusinessRuleError) as missing:
        require_notice_complete("Aviso de privacidad", body, ["cookies"])
    assert missing.value.code == "privacy_notice_incomplete"
    with pytest.raises(BusinessRuleError) as short:
        require_notice_complete("Aviso", "corto", list(NOTICE_ELEMENTS))
    assert short.value.code == "privacy_notice_body_too_short"


def test_incident_deadline_and_closure() -> None:
    discovered = datetime(2026, 11, 16, 9, 0, tzinfo=UTC)
    assert notification_deadline(discovered) == discovered + timedelta(hours=72)
    with pytest.raises(BusinessRuleError) as exc:
        require_incident_closable(IncidentNotifications(discovered, None, None, None))
    assert "Fiscalía" in exc.value.message
    require_incident_closable(
        IncidentNotifications(discovered, discovered, None, "Datos cifrados, sin riesgo")
    )
