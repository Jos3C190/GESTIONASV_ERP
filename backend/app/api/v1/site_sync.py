"""Reconcile the automatic branch/warehouse geofences in Traccar with the ERP.

The ERP decides which sites exist (see ``app.application.tracking.sites``);
this module only makes Traccar match it. Reconciliation is idempotent, so it
runs after every branch or warehouse change, lazily when tracking is opened
with a stale state, and on demand. A Traccar outage never blocks the ERP: the
error is recorded and the next run repairs the difference.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

from fastapi import HTTPException, Request
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.after_commit import run_after_commit, wait_for_pending
from app.api.v1.deps import SessionDep
from app.api.v1.traccar_access import traccar, traccar_credentials
from app.application.tracking.devices import COMPANY_ATTRIBUTE
from app.application.tracking.sites import (
    Site,
    build_sites,
    is_site_geofence,
    plan_site_geofences,
    site_geofence_body,
)
from app.infrastructure.db.session import async_session_factory
from app.infrastructure.models.fleet import FleetVehicleModel
from app.infrastructure.models.organization import Branch, Warehouse
from app.infrastructure.models.tracking import TrackingSyncStateModel

logger = logging.getLogger(__name__)

#: A successful reconciliation older than this is refreshed when tracking is opened.
STALE_AFTER = timedelta(minutes=10)
#: After a failed reconciliation, how soon opening tracking retries it.
RETRY_AFTER = timedelta(minutes=1)


async def load_sites(
    session: AsyncSession, company_id: uuid.UUID
) -> tuple[list[Site], list[dict[str, Any]]]:
    branches = list(
        (await session.scalars(select(Branch).where(Branch.company_id == company_id))).all()
    )
    warehouses = list(
        (await session.scalars(select(Warehouse).where(Warehouse.company_id == company_id))).all()
    )
    return build_sites(branches, warehouses)


def _owned(item: dict[str, Any], company_id: uuid.UUID) -> bool:
    attributes = item.get("attributes") or {}
    return str(attributes.get(COMPANY_ATTRIBUTE, "")).lower() == str(company_id)


async def _link_devices(
    session: AsyncSession, company_id: uuid.UUID, geofence_ids: set[int]
) -> None:
    """Every GPS device of the company must report every site geofence."""
    devices = (
        await session.scalars(
            select(FleetVehicleModel.traccar_device_id).where(
                FleetVehicleModel.company_id == company_id,
                FleetVehicleModel.traccar_device_id.is_not(None),
                FleetVehicleModel.status != "retired",
            )
        )
    ).all()
    for device_id in devices:
        linked: list[dict[str, Any]] = (
            await traccar(f"/api/geofences?{urlencode({'deviceId': device_id})}") or []
        )
        present = {int(item["id"]) for item in linked}
        for geofence_id in sorted(geofence_ids - present):
            await traccar(
                "/api/permissions",
                method="POST",
                body={"deviceId": device_id, "geofenceId": geofence_id},
            )


async def reconcile_site_geofences(session: AsyncSession, company_id: uuid.UUID) -> None:
    sites, _ = await load_sites(session, company_id)
    desired = [site_geofence_body(site, company_id) for site in sites]
    items: list[dict[str, Any]] = await traccar("/api/geofences") or []
    existing = [item for item in items if is_site_geofence(item) and _owned(item, company_id)]
    plan = plan_site_geofences(desired, existing)
    kept = {int(item["id"]) for item in existing} - set(plan.delete)
    for geofence_id in plan.delete:
        await traccar(f"/api/geofences/{geofence_id}", method="DELETE")
    for geofence_id, body in plan.update:
        await traccar(f"/api/geofences/{geofence_id}", method="PUT", body=body)
    for body in plan.create:
        created = await traccar("/api/geofences", method="POST", body=body)
        kept.add(int(created["id"]))
    await _link_devices(session, company_id, kept)


async def _state(session: AsyncSession, company_id: uuid.UUID) -> TrackingSyncStateModel:
    state = await session.get(TrackingSyncStateModel, company_id)
    if state is None:
        state = TrackingSyncStateModel(company_id=company_id)
        session.add(state)
    return state


async def run_site_sync(company_id: uuid.UUID) -> None:
    """Reconcile in a session of its own and record the outcome; never raises."""
    if traccar_credentials() is None:
        return
    async with async_session_factory() as session:
        # Una sola reconciliación por empresa a la vez; si otra ya corre, esta sobra.
        acquired = await session.scalar(
            text("SELECT pg_try_advisory_xact_lock(hashtext(:key))"),
            {"key": f"tracking-sites:{company_id}"},
        )
        if not acquired:
            return
        state = await _state(session, company_id)
        state.last_attempt_at = datetime.now(UTC)
        try:
            await reconcile_site_geofences(session, company_id)
        except HTTPException as exc:
            state.last_error = str(exc.detail)
            logger.warning(
                "tracking_site_sync_failed company_id=%s detail=%s", company_id, exc.detail
            )
        except Exception:
            state.last_error = "Error inesperado al sincronizar las geocercas."
            logger.exception("tracking_site_sync_crashed company_id=%s", company_id)
        else:
            state.sites_synced_at = state.last_attempt_at
            state.last_error = None
        await session.commit()


async def sync_if_stale(session: AsyncSession, company_id: uuid.UUID) -> None:
    if traccar_credentials() is None:
        return
    state = await session.get(TrackingSyncStateModel, company_id)
    now = datetime.now(UTC)
    if state is not None and state.last_error is not None:
        # Tras un fallo se reintenta como mucho una vez por minuto para no frenar la vista.
        due = state.last_attempt_at is None or now - state.last_attempt_at > RETRY_AFTER
    else:
        due = (
            state is None
            or state.sites_synced_at is None
            or now - state.sites_synced_at > STALE_AFTER
        )
    if due:
        await run_site_sync(company_id)
        session.expire_all()


async def sync_state(session: AsyncSession, company_id: uuid.UUID) -> dict[str, Any]:
    state = await session.get(TrackingSyncStateModel, company_id)
    return {
        "configured": traccar_credentials() is not None,
        "synced_at": state.sites_synced_at if state else None,
        "last_attempt_at": state.last_attempt_at if state else None,
        "error": state.last_error if state else None,
    }


def sync_sites_on_commit(session: AsyncSession, company_id: uuid.UUID) -> None:
    """Reconcile once ``session`` commits (never on rollback)."""
    run_after_commit(session, lambda: run_site_sync(company_id))


#: Kept for callers that wait for the sync itself.
wait_for_pending_syncs = wait_for_pending


def sync_sites_after_change(request: Request, session: SessionDep) -> None:
    """Route dependency: reconcile after a branch or warehouse change commits."""
    company_id = getattr(request.state, "effective_company_id", None)
    if isinstance(company_id, uuid.UUID):
        sync_sites_on_commit(session, company_id)
