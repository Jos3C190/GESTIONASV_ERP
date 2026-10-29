"""Pure availability policy for quarantined handling units."""

from __future__ import annotations

from datetime import date
from enum import StrEnum


class ReleaseRequirement(StrEnum):
    PARTIAL_SPLIT = "partial_split"
    MEASUREMENT = "measurement_required"
    EXPIRY = "expired_lot"
    LABEL = "label_confirmation_required"
    RETACEO = "retaceo_not_final"
    RETACEO_COST = "retaceo_cost_unapplied"


def handling_unit_release_requirements(
    *,
    is_partial: bool,
    measurement_status: str,
    measurement_source: str,
    expiry_date: date | None,
    today: date,
    label_confirmation_required: bool,
    label_confirmed: bool,
    retaceo_readiness_error: str | None = None,
) -> tuple[ReleaseRequirement, ...]:
    """Return all reasons that require the unit to remain unavailable.

    The function is intentionally persistence-free. Adapters resolve whether a
    current label or an applicable landed-cost record exists, then call this
    same rule for individual and grouped release decisions.
    """
    requirements: list[ReleaseRequirement] = []
    if is_partial:
        requirements.append(ReleaseRequirement.PARTIAL_SPLIT)
    if measurement_status == "incomplete" or measurement_source == "split_estimate":
        requirements.append(ReleaseRequirement.MEASUREMENT)
    if expiry_date is not None and expiry_date < today:
        requirements.append(ReleaseRequirement.EXPIRY)
    if label_confirmation_required and not label_confirmed:
        requirements.append(ReleaseRequirement.LABEL)
    if retaceo_readiness_error == "not_final":
        requirements.append(ReleaseRequirement.RETACEO)
    elif retaceo_readiness_error == "cost_unapplied":
        requirements.append(ReleaseRequirement.RETACEO_COST)
    return tuple(requirements)
