"""A company's transfer rules. A company that never saved them follows these defaults."""

from __future__ import annotations

from typing import Any

from app.domain.entities.inventory_transfer import TransferPolicy


def policy_from(row: Any | None) -> TransferPolicy:
    """Rules to apply: the saved ones, or branch routes off with approval required."""
    if row is None:
        return TransferPolicy()
    return TransferPolicy(
        allow_branch_to_branch=row.allow_branch_to_branch,
        allow_branch_to_central=row.allow_branch_to_central,
        require_approval=row.require_approval,
    )
