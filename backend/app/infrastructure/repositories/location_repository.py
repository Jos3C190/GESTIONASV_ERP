"""SQLAlchemy adapter for warehouse-location use cases."""

from __future__ import annotations

import json
import uuid
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.domain.entities.location import (
    BatchRowRecord,
    CodeProjection,
    CodeSegment,
    LocationBatchRecord,
    LocationRecord,
    WarehouseLocationScope,
    normalize_location_component,
)
from app.domain.entities.location import (
    LocationCodeScheme as DomainLocationCodeScheme,
)
from app.infrastructure.models.audit import AuditLog
from app.infrastructure.models.location import (
    LocationBatchJob,
    LocationBatchRow,
    LocationCodeAlias,
    LocationCodeScheme,
)
from app.infrastructure.models.organization import (
    Branch,
    Location,
    Warehouse,
    WarehouseCapacityGroup,
)
from app.infrastructure.repositories.capacity_hierarchy_repository import (
    SqlAlchemyCapacityHierarchyRepository,
)

_LOCATION_FIELDS = (
    "area",
    "aisle",
    "rack",
    "level",
    "position",
    "capacity_group_id",
    "certified_max_weight_kg",
    "operational_max_weight_kg",
    "certified_usable_volume_m3",
    "operational_usable_volume_m3",
    "capacity_profile",
    "capacity_enforcement_mode",
    "storage_eligible",
    "usable_length_m",
    "usable_width_m",
    "usable_height_m",
    "notes",
    "location_type",
    "lifecycle_status",
    "barcode",
    "verification_code",
    "pick_sequence",
    "putaway_sequence",
    "external_id",
)
PREVIEW_ROW_LIMIT = 100


async def _location_capacity_group_filter_ids(
    session: AsyncSession,
    warehouse_id: uuid.UUID,
    capacity_group_id: uuid.UUID | None,
    include_descendants: bool,
    unassigned: bool,
) -> set[uuid.UUID] | None:
    if capacity_group_id is not None and unassigned:
        raise ValidationError(
            "Seleccione una estructura o las ubicaciones sin estructura, no ambas.",
            code="location_filter_conflict",
        )
    if capacity_group_id is None:
        return set() if unassigned else None
    group_rows = list(
        (
            await session.execute(
                select(WarehouseCapacityGroup.id, WarehouseCapacityGroup.parent_id).where(
                    WarehouseCapacityGroup.warehouse_id == warehouse_id,
                    WarehouseCapacityGroup.deleted_at.is_(None),
                )
            )
        ).all()
    )
    group_ids = {row[0] for row in group_rows}
    if capacity_group_id not in group_ids:
        raise NotFoundError(
            "La estructura no pertenece a este almacén o ya no está disponible.",
            code="location_capacity_group_not_found",
        )
    selected_ids = {capacity_group_id}
    if not include_descendants:
        return selected_ids
    children: dict[uuid.UUID, list[uuid.UUID]] = {}
    for group_id, parent_id in group_rows:
        if parent_id is not None:
            children.setdefault(parent_id, []).append(group_id)
    pending = list(children.get(capacity_group_id, ()))
    while pending:
        child_id = pending.pop()
        if child_id in selected_ids:
            continue
        selected_ids.add(child_id)
        pending.extend(children.get(child_id, ()))
    return selected_ids


def _location_model_values(values: Mapping[str, Any]) -> dict[str, Any]:
    """Build the explicit ORM write set for a location."""

    return {name: values.get(name) for name in _LOCATION_FIELDS}


@dataclass(slots=True)
class _LocationIndexes:
    by_code: dict[str, Location]
    by_external: dict[str, Location]
    by_coordinates: dict[tuple[str, str, str, str, str], Location]
    ambiguous_coordinates: set[tuple[str, str, str, str, str]]
    aliases: dict[str, uuid.UUID]


def _coordinate_key(data: object) -> tuple[str, str, str, str, str]:
    keys = ("area", "aisle", "rack", "level", "position")
    if isinstance(data, Mapping):
        return tuple(str(data.get(key) or "") for key in keys)  # type: ignore[return-value]
    return tuple(str(getattr(data, key, None) or "") for key in keys)  # type: ignore[return-value]


def _scheme_coordinate_key(
    data: object, scheme: DomainLocationCodeScheme
) -> tuple[str, str, str, str, str]:
    """Canonicalize persisted legacy coordinates with the selected scheme.

    Legacy rows can contain already-rendered values (for example ``A01``)
    while new imports contain the raw coordinate (``01``).  Canonicalizing
    both sides enables safe adoption without ever matching by display code.
    """

    keys = ("area", "aisle", "rack", "level", "position")
    segments = {segment.key: segment for segment in scheme.segments}
    values: list[str] = []
    for key in keys:
        segment = segments.get(key) or CodeSegment(
            key=key,
            label=key.capitalize(),
            width=0,
            required=key != "area",
        )
        raw = data.get(key) if isinstance(data, Mapping) else getattr(data, key, None)
        values.append(normalize_location_component(raw, segment))
    return tuple(values)  # type: ignore[return-value]


def _effective_update_projection(
    model: Location, values: Mapping[str, Any], projection: CodeProjection
) -> CodeProjection:
    if _coordinate_key(model) != _coordinate_key(values):
        return projection
    return CodeProjection(
        code=model.code,
        normalized_components={
            key: str(getattr(model, key) or "")
            for key in ("area", "aisle", "rack", "level", "position")
        },
        scheme_id=model.code_scheme_id or projection.scheme_id,
        scheme_version=model.scheme_version or projection.scheme_version,
    )


def _effective_code_source(model: Location, projection: CodeProjection) -> str:
    return "recode" if model.code.casefold() != projection.code.casefold() else model.code_source


def _scheme_to_domain(model: LocationCodeScheme) -> DomainLocationCodeScheme:
    return DomainLocationCodeScheme(
        id=model.id,
        warehouse_id=model.warehouse_id,
        name=model.name,
        version=model.version,
        separator=model.separator,
        segments=tuple(CodeSegment(**item) for item in model.segments),
        is_active=model.is_active,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _location_to_domain(model: Location) -> LocationRecord:
    return LocationRecord(
        id=model.id,
        warehouse_id=model.warehouse_id,
        code=model.code,
        area=model.area,
        aisle=model.aisle,
        rack=model.rack,
        level=model.level,
        position=model.position,
        capacity_group_id=model.capacity_group_id,
        certified_max_weight_kg=model.certified_max_weight_kg,
        operational_max_weight_kg=model.operational_max_weight_kg,
        certified_usable_volume_m3=model.certified_usable_volume_m3,
        operational_usable_volume_m3=model.operational_usable_volume_m3,
        capacity_profile=model.capacity_profile,
        capacity_enforcement_mode=model.capacity_enforcement_mode,
        storage_eligible=model.storage_eligible,
        usable_length_m=model.usable_length_m,
        usable_width_m=model.usable_width_m,
        usable_height_m=model.usable_height_m,
        notes=model.notes,
        location_type=model.location_type,
        lifecycle_status=model.lifecycle_status,
        barcode=model.barcode,
        verification_code=model.verification_code,
        pick_sequence=model.pick_sequence,
        putaway_sequence=model.putaway_sequence,
        external_id=model.external_id,
        scheme_id=model.code_scheme_id,
        scheme_version=model.scheme_version,
        code_source=model.code_source,
        is_active=model.is_active,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _row_to_domain(model: LocationBatchRow) -> BatchRowRecord:
    public_data = {
        key: value
        for key, value in dict(model.normalized_data or {}).items()
        if not key.startswith("_")
    }
    return BatchRowRecord(
        id=model.id,
        row_number=model.row_number,
        operation=model.operation,
        code=model.code,
        normalized_data=public_data,
        diff=dict(model.diff or {}),
        errors=tuple(model.errors or []),
        published_location_id=model.published_location_id,
    )


def _job_to_domain(
    model: LocationBatchJob,
    rows: Sequence[LocationBatchRow] = (),
    *,
    page: int = 1,
    size: int = PREVIEW_ROW_LIMIT,
) -> LocationBatchRecord:
    summary = dict(model.summary or {})
    permissions = summary.get("required_permissions") or []
    return LocationBatchRecord(
        id=model.id,
        warehouse_id=model.warehouse_id,
        kind=model.kind,
        status=model.status,
        idempotency_key=model.idempotency_key,
        input_checksum=model.input_checksum,
        scheme_id=model.code_scheme_id,
        scheme_version=model.scheme_version,
        total_rows=model.total_rows,
        create_count=model.create_count,
        update_count=model.update_count,
        unchanged_count=model.unchanged_count,
        conflict_count=model.conflict_count,
        error_count=model.error_count,
        summary=summary,
        created_by=model.created_by,
        published_by=model.published_by,
        created_at=model.created_at,
        published_at=model.published_at,
        rows=tuple(_row_to_domain(row) for row in rows),
        required_permissions=tuple(str(item) for item in permissions),
        rows_meta={
            "page": page,
            "size": size,
            "total": model.total_rows,
            "pages": (model.total_rows + size - 1) // size if model.total_rows else 1,
        },
    )


def _audit_state(location: Location) -> dict[str, Any]:
    return {
        "id": str(location.id),
        "warehouse_id": str(location.warehouse_id),
        "code": location.code,
        "area": location.area,
        "aisle": location.aisle,
        "rack": location.rack,
        "level": location.level,
        "position": location.position,
        "capacity_group_id": str(location.capacity_group_id)
        if location.capacity_group_id
        else None,
        "certified_max_weight_kg": str(location.certified_max_weight_kg)
        if location.certified_max_weight_kg is not None
        else None,
        "operational_max_weight_kg": str(location.operational_max_weight_kg)
        if location.operational_max_weight_kg is not None
        else None,
        "certified_usable_volume_m3": str(location.certified_usable_volume_m3)
        if location.certified_usable_volume_m3 is not None
        else None,
        "operational_usable_volume_m3": str(location.operational_usable_volume_m3)
        if location.operational_usable_volume_m3 is not None
        else None,
        "capacity_profile": location.capacity_profile,
        "capacity_enforcement_mode": location.capacity_enforcement_mode,
        "storage_eligible": location.storage_eligible,
        "usable_length_m": str(location.usable_length_m)
        if location.usable_length_m is not None
        else None,
        "usable_width_m": str(location.usable_width_m)
        if location.usable_width_m is not None
        else None,
        "usable_height_m": str(location.usable_height_m)
        if location.usable_height_m is not None
        else None,
        "location_type": location.location_type,
        "lifecycle_status": location.lifecycle_status,
        "external_id": location.external_id,
        "scheme_id": str(location.code_scheme_id) if location.code_scheme_id else None,
        "scheme_version": location.scheme_version,
        "code_source": location.code_source,
    }


def _json_safe(value: Any) -> Any:
    """Canonicalize adapter inputs before storing them in PostgreSQL JSONB."""

    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


_DECIMAL_LOCATION_FIELDS = frozenset(
    {
        "certified_max_weight_kg",
        "operational_max_weight_kg",
        "certified_usable_volume_m3",
        "operational_usable_volume_m3",
        "usable_length_m",
        "usable_width_m",
        "usable_height_m",
    }
)


def _location_values_equal(field: str, incoming: Any, current: Any) -> bool:
    if field not in _DECIMAL_LOCATION_FIELDS or incoming is None or current is None:
        return incoming == current
    try:
        return Decimal(str(incoming)) == Decimal(str(current))
    except (ArithmeticError, ValueError):
        return False


def _extend_batch_permissions(required: set[str], operation: str, diff: Mapping[str, Any]) -> None:
    if operation == "create":
        required.add("locations.create")
        return
    if operation != "update":
        return
    required.add("locations.update")
    if "code" in diff or any(key in diff for key in ("area", "aisle", "rack", "level", "position")):
        required.add("locations.recode")
    lifecycle = diff.get("lifecycle_status")
    active_change = diff.get("is_active")
    if isinstance(active_change, Mapping) and active_change.get("after") is True:
        required.add("locations.activate")
    elif isinstance(active_change, Mapping) and active_change.get("after") is False:
        required.add("locations.deactivate")
    elif isinstance(lifecycle, Mapping):
        required.add("locations.commission")


def _batch_row_has_positive_impact(operation: str, diff: Mapping[str, Any]) -> bool:
    """Return whether a row expands the warehouse's operational footprint."""

    if operation == "create":
        return True
    if operation != "update":
        return False
    active_change = diff.get("is_active")
    return (
        isinstance(active_change, Mapping)
        and active_change.get("before") is False
        and active_change.get("after") is True
    )


class SqlAlchemyLocationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _load_location_indexes(
        self,
        warehouse_id: uuid.UUID,
        *,
        scheme: DomainLocationCodeScheme,
        for_update: bool = False,
    ) -> _LocationIndexes:
        location_statement = select(Location).where(
            Location.warehouse_id == warehouse_id,
            Location.deleted_at.is_(None),
        )
        alias_statement = select(LocationCodeAlias.alias_code, LocationCodeAlias.location_id).where(
            LocationCodeAlias.warehouse_id == warehouse_id
        )
        if for_update:
            location_statement = location_statement.with_for_update()
            alias_statement = alias_statement.with_for_update()
        locations = list((await self._session.execute(location_statement)).scalars())
        aliases = (await self._session.execute(alias_statement)).all()
        by_coordinates: dict[tuple[str, str, str, str, str], Location] = {}
        ambiguous_coordinates: set[tuple[str, str, str, str, str]] = set()
        for item in locations:
            try:
                coordinate = _scheme_coordinate_key(item, scheme)
            except ValidationError:
                # Malformed legacy coordinates must never make a batch adopt a
                # row heuristically. They remain addressable by code/external ID.
                continue
            previous = by_coordinates.get(coordinate)
            if previous is not None and previous.id != item.id:
                ambiguous_coordinates.add(coordinate)
                by_coordinates.pop(coordinate, None)
            elif coordinate not in ambiguous_coordinates:
                by_coordinates[coordinate] = item
        return _LocationIndexes(
            by_code={item.code.casefold(): item for item in locations},
            by_external={
                item.external_id.casefold(): item for item in locations if item.external_id
            },
            by_coordinates=by_coordinates,
            ambiguous_coordinates=ambiguous_coordinates,
            aliases={alias.casefold(): location_id for alias, location_id in aliases},
        )

    async def get_warehouse_scope(self, warehouse_id: uuid.UUID) -> WarehouseLocationScope:
        row = (
            await self._session.execute(
                select(
                    Warehouse.id,
                    Branch.company_id,
                    Branch.id,
                    Warehouse.is_active,
                    Warehouse.operational_status,
                )
                .join(Branch, Branch.id == Warehouse.branch_id)
                .where(Warehouse.id == warehouse_id)
            )
        ).one_or_none()
        if row is None:
            raise NotFoundError("Almacén no encontrado.", code="warehouse_not_found")
        return WarehouseLocationScope(
            warehouse_id=row[0],
            company_id=row[1],
            branch_id=row[2],
            warehouse_active=row[3],
            operational_status=row[4],
        )

    async def get_batch_scope(self, job_id: uuid.UUID) -> WarehouseLocationScope:
        warehouse_id = await self._session.scalar(
            select(LocationBatchJob.warehouse_id).where(LocationBatchJob.id == job_id)
        )
        if warehouse_id is None:
            raise NotFoundError("Lote no encontrado.", code="location_batch_not_found")
        return await self.get_warehouse_scope(warehouse_id)

    async def get_scheme(
        self, warehouse_id: uuid.UUID, version: int | None = None
    ) -> DomainLocationCodeScheme:
        conditions = [LocationCodeScheme.warehouse_id == warehouse_id]
        if version is None:
            conditions.append(LocationCodeScheme.is_active.is_(True))
        else:
            conditions.append(LocationCodeScheme.version == version)
        model = await self._session.scalar(select(LocationCodeScheme).where(*conditions))
        if model is None:
            raise NotFoundError(
                "No existe un esquema de códigos para el almacén.",
                code="location_scheme_not_found",
            )
        return _scheme_to_domain(model)

    async def create_scheme_version(
        self,
        warehouse_id: uuid.UUID,
        *,
        name: str,
        separator: str,
        segments: Sequence[Mapping[str, Any]],
        actor_id: uuid.UUID,
    ) -> DomainLocationCodeScheme:
        scope = await self.get_warehouse_scope(warehouse_id)
        # Serialize version allocation for this warehouse.  The warehouse row
        # exists before every scheme and is therefore the stable lock target.
        await self._session.execute(
            select(Warehouse.id).where(Warehouse.id == warehouse_id).with_for_update()
        )
        latest = await self._session.scalar(
            select(func.coalesce(func.max(LocationCodeScheme.version), 0)).where(
                LocationCodeScheme.warehouse_id == warehouse_id
            )
        )
        model = LocationCodeScheme(
            warehouse_id=warehouse_id,
            name=name,
            version=int(latest or 0) + 1,
            separator=separator,
            segments=[dict(item) for item in segments],
            is_active=True,
            created_by=actor_id,
        )
        try:
            async with self._session.begin_nested():
                await self._session.execute(
                    update(LocationCodeScheme)
                    .where(
                        LocationCodeScheme.warehouse_id == warehouse_id,
                        LocationCodeScheme.is_active.is_(True),
                    )
                    .values(is_active=False)
                )
                self._session.add(model)
                await self._session.flush()
                self._session.add(
                    AuditLog(
                        action="LOCATION_SCHEME_VERSION_CREATED",
                        user_id=actor_id,
                        company_id=scope.company_id,
                        branch_id=scope.branch_id,
                        resource_type="location_code_schemes",
                        resource_id=str(model.id),
                        after_state={
                            "warehouse_id": str(warehouse_id),
                            "version": model.version,
                            "name": name,
                            "separator": separator,
                            "segments": model.segments,
                        },
                    )
                )
                await self._session.flush()
        except IntegrityError as exc:
            raise ConflictError(
                "No fue posible crear la versión del esquema por un cambio concurrente.",
                code="location_scheme_version_conflict",
            ) from exc
        return _scheme_to_domain(model)

    async def check_projection_conflicts(
        self,
        warehouse_id: uuid.UUID,
        projection: CodeProjection,
        *,
        exclude_location_id: uuid.UUID | None = None,
    ) -> tuple[bool, bool]:
        components = projection.normalized_components
        location_conditions: list[Any] = [
            Location.warehouse_id == warehouse_id,
            Location.deleted_at.is_(None),
        ]
        alias_conditions: list[Any] = [LocationCodeAlias.warehouse_id == warehouse_id]
        if exclude_location_id is not None:
            target = await self._session.scalar(
                select(Location.id).where(
                    Location.id == exclude_location_id,
                    Location.warehouse_id == warehouse_id,
                    Location.deleted_at.is_(None),
                )
            )
            if target is None:
                raise NotFoundError("Ubicación no encontrada.", code="location_not_found")
            location_conditions.append(Location.id != exclude_location_id)
            alias_conditions.append(LocationCodeAlias.location_id != exclude_location_id)
        code_exists = (
            await self._session.scalar(
                select(Location.id)
                .where(
                    *location_conditions,
                    func.lower(Location.code) == projection.code.casefold(),
                )
                .limit(1)
            )
        ) is not None
        if not code_exists:
            code_exists = (
                await self._session.scalar(
                    select(LocationCodeAlias.id)
                    .where(
                        *alias_conditions,
                        func.lower(LocationCodeAlias.alias_code) == projection.code.casefold(),
                    )
                    .limit(1)
                )
            ) is not None
        coordinates_exist = (
            await self._session.scalar(
                select(Location.id)
                .where(
                    *location_conditions,
                    func.coalesce(Location.area, "") == components.get("area", ""),
                    Location.aisle == components.get("aisle"),
                    Location.rack == components.get("rack"),
                    Location.level == components.get("level"),
                    Location.position == components.get("position"),
                )
                .limit(1)
            )
        ) is not None
        return code_exists, coordinates_exist

    async def get_location(
        self,
        warehouse_id: uuid.UUID,
        location_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> LocationRecord:
        statement = select(Location).where(
            Location.id == location_id,
            Location.warehouse_id == warehouse_id,
            Location.deleted_at.is_(None),
        )
        if for_update:
            await self._session.execute(
                select(Warehouse.id).where(Warehouse.id == warehouse_id).with_for_update()
            )
            statement = statement.with_for_update()
        model = await self._session.scalar(statement)
        if model is None:
            raise NotFoundError("Ubicación no encontrada.", code="location_not_found")
        return _location_to_domain(model)

    async def _validate_capacity_group(
        self, warehouse_id: uuid.UUID, group_id: uuid.UUID | None
    ) -> None:
        if group_id is None:
            return
        exists = await self._session.scalar(
            select(WarehouseCapacityGroup.id).where(
                WarehouseCapacityGroup.id == group_id,
                WarehouseCapacityGroup.warehouse_id == warehouse_id,
                WarehouseCapacityGroup.is_active.is_(True),
                WarehouseCapacityGroup.deleted_at.is_(None),
            )
        )
        if exists is None:
            raise ConflictError(
                "El grupo de capacidad no pertenece al almacén o no está activo.",
                code="location_capacity_group_unavailable",
            )

    async def create_location(
        self,
        warehouse_id: uuid.UUID,
        *,
        projection: CodeProjection,
        values: Mapping[str, Any],
        actor_id: uuid.UUID,
    ) -> LocationRecord:
        warehouse = await self._session.scalar(
            select(Warehouse).where(Warehouse.id == warehouse_id).with_for_update()
        )
        if warehouse is None:
            raise NotFoundError("Almacén no encontrado.", code="warehouse_not_found")
        if not warehouse.is_active or warehouse.operational_status == "inactive":
            raise ConflictError(
                "El almacén no admite nuevas ubicaciones en su estado actual.",
                code="warehouse_not_commissionable",
            )
        await self._validate_capacity_group(warehouse_id, values.get("capacity_group_id"))
        await SqlAlchemyCapacityHierarchyRepository(self._session).validate_location_write(
            warehouse_id, values
        )
        alias_conflict = await self._session.scalar(
            select(LocationCodeAlias.id).where(
                LocationCodeAlias.warehouse_id == warehouse_id,
                func.lower(LocationCodeAlias.alias_code) == projection.code.casefold(),
            )
        )
        if alias_conflict is not None:
            raise ConflictError(
                "El código corresponde a un alias histórico y no puede reutilizarse.",
                code="location_alias_conflict",
            )
        model = Location(
            warehouse_id=warehouse_id,
            code=projection.code,
            **_location_model_values(values),
            code_scheme_id=projection.scheme_id,
            scheme_version=projection.scheme_version,
            code_source=str(values.get("code_source") or "generated"),
            is_active=bool(values.get("is_active", True)),
        )
        scope = await self.get_warehouse_scope(warehouse_id)
        try:
            async with self._session.begin_nested():
                self._session.add(model)
                await self._session.flush()
                self._session.add(
                    AuditLog(
                        action="CREATE",
                        user_id=actor_id,
                        company_id=scope.company_id,
                        branch_id=scope.branch_id,
                        resource_type="locations",
                        resource_id=str(model.id),
                        after_state=_audit_state(model),
                    )
                )
                await self._session.flush()
        except IntegrityError as exc:
            raise ConflictError(
                "El código, las coordenadas o un identificador de escaneo ya están en uso.",
                code="location_identifier_conflict",
            ) from exc
        return _location_to_domain(model)

    async def update_location(  # noqa: C901 - coordinates, aliases and audit are atomic
        self,
        warehouse_id: uuid.UUID,
        location_id: uuid.UUID,
        *,
        projection: CodeProjection,
        values: Mapping[str, Any],
        actor_id: uuid.UUID,
        expected_updated_at: datetime | None = None,
    ) -> LocationRecord:
        warehouse = await self._session.scalar(
            select(Warehouse).where(Warehouse.id == warehouse_id).with_for_update()
        )
        model = await self._session.scalar(
            select(Location)
            .where(
                Location.id == location_id,
                Location.warehouse_id == warehouse_id,
                Location.deleted_at.is_(None),
            )
            .with_for_update()
        )
        if warehouse is None or model is None:
            raise NotFoundError("Ubicación no encontrada.", code="location_not_found")
        if expected_updated_at is not None and model.updated_at != expected_updated_at:
            raise ConflictError(
                "La ubicación fue modificada por otro usuario; recargue antes de guardar.",
                code="location_update_stale",
            )
        target_active = bool(values.get("is_active", model.is_active))
        if (
            target_active
            and not model.is_active
            and (not warehouse.is_active or warehouse.operational_status == "inactive")
        ):
            raise ConflictError(
                "El almacén no admite activar o ampliar ubicaciones en su estado actual.",
                code="warehouse_not_commissionable",
            )
        await self._validate_capacity_group(warehouse_id, values.get("capacity_group_id"))
        await SqlAlchemyCapacityHierarchyRepository(self._session).validate_location_write(
            warehouse_id, values, location_id=location_id
        )
        before = _audit_state(model)
        old_code = model.code
        effective_projection = _effective_update_projection(model, values, projection)
        effective_code_source = _effective_code_source(model, effective_projection)
        scope = await self.get_warehouse_scope(warehouse_id)
        if old_code.casefold() != effective_projection.code.casefold():
            target_alias_owner = await self._session.scalar(
                select(LocationCodeAlias.location_id).where(
                    LocationCodeAlias.warehouse_id == warehouse_id,
                    func.lower(LocationCodeAlias.alias_code)
                    == effective_projection.code.casefold(),
                )
            )
            if target_alias_owner is not None and target_alias_owner != model.id:
                raise ConflictError(
                    "El código corresponde al alias histórico de otra ubicación.",
                    code="location_alias_conflict",
                )
            existing_alias_owner = await self._session.scalar(
                select(LocationCodeAlias.location_id).where(
                    LocationCodeAlias.warehouse_id == warehouse_id,
                    func.lower(LocationCodeAlias.alias_code) == old_code.casefold(),
                )
            )
            if existing_alias_owner is not None and existing_alias_owner != model.id:
                raise ConflictError(
                    "El código anterior ya pertenece al historial de otra ubicación.",
                    code="location_alias_conflict",
                )
        try:
            async with self._session.begin_nested():
                if old_code.casefold() != effective_projection.code.casefold():
                    if existing_alias_owner is None:
                        self._session.add(
                            LocationCodeAlias(
                                warehouse_id=warehouse_id,
                                location_id=model.id,
                                alias_code=old_code,
                                code_scheme_id=model.code_scheme_id,
                                scheme_version=model.scheme_version,
                                reason="recode",
                                created_by=actor_id,
                            )
                        )
                    model.code = effective_projection.code
                for name in _LOCATION_FIELDS:
                    setattr(model, name, values.get(name))
                model.code_scheme_id = effective_projection.scheme_id
                model.scheme_version = effective_projection.scheme_version
                model.code_source = effective_code_source
                model.is_active = bool(values.get("is_active", model.is_active))
                await self._session.flush()
                self._session.add(
                    AuditLog(
                        action="RECODE" if old_code != model.code else "UPDATE",
                        user_id=actor_id,
                        company_id=scope.company_id,
                        branch_id=scope.branch_id,
                        resource_type="locations",
                        resource_id=str(model.id),
                        before_state=before,
                        after_state=_audit_state(model),
                    )
                )
                await self._session.flush()
        except IntegrityError as exc:
            raise ConflictError(
                "El código, las coordenadas o un identificador de escaneo ya están en uso.",
                code="location_identifier_conflict",
            ) from exc
        return _location_to_domain(model)

    async def list_locations(
        self,
        warehouse_id: uuid.UUID,
        *,
        page: int,
        size: int,
        search: str | None,
        area: str | None,
        location_type: str | None,
        lifecycle_status: str | None,
        is_active: bool | None,
        capacity_group_id: uuid.UUID | None,
        include_descendants: bool,
        unassigned: bool,
    ) -> tuple[list[LocationRecord], int]:
        conditions: list[Any] = [
            Location.warehouse_id == warehouse_id,
            Location.deleted_at.is_(None),
        ]
        if search:
            pattern = f"%{search.strip()}%"
            conditions.append(
                or_(
                    Location.code.ilike(pattern),
                    Location.area.ilike(pattern),
                    Location.aisle.ilike(pattern),
                    Location.rack.ilike(pattern),
                    Location.level.ilike(pattern),
                    Location.position.ilike(pattern),
                    Location.barcode.ilike(pattern),
                    Location.external_id.ilike(pattern),
                    Location.notes.ilike(pattern),
                    Location.id.in_(
                        select(LocationCodeAlias.location_id).where(
                            LocationCodeAlias.warehouse_id == warehouse_id,
                            LocationCodeAlias.alias_code.ilike(pattern),
                        )
                    ),
                )
            )
        if area:
            if area == "__none__":
                conditions.append(or_(Location.area.is_(None), Location.area == ""))
            else:
                conditions.append(Location.area == area.strip().upper())
        if location_type:
            conditions.append(Location.location_type == location_type)
        if lifecycle_status:
            conditions.append(Location.lifecycle_status == lifecycle_status)
        if is_active is not None:
            conditions.append(Location.is_active.is_(is_active))
        capacity_group_ids = await _location_capacity_group_filter_ids(
            self._session,
            warehouse_id,
            capacity_group_id,
            include_descendants,
            unassigned,
        )
        if unassigned:
            conditions.append(Location.capacity_group_id.is_(None))
        elif capacity_group_ids is not None:
            conditions.append(Location.capacity_group_id.in_(capacity_group_ids))
        total = int(
            await self._session.scalar(select(func.count(Location.id)).where(*conditions)) or 0
        )
        rows = list(
            (
                await self._session.execute(
                    select(Location)
                    .where(*conditions)
                    .order_by(
                        Location.pick_sequence.asc().nullslast(),
                        Location.code.asc(),
                        Location.id.asc(),
                    )
                    .offset((page - 1) * size)
                    .limit(size)
                )
            ).scalars()
        )
        return [_location_to_domain(row) for row in rows], total

    async def location_summary(self, warehouse_id: uuid.UUID) -> dict[str, Any]:
        rows = (
            await self._session.execute(
                select(
                    Location.lifecycle_status,
                    Location.location_type,
                    Location.area,
                    Location.is_active,
                    Location.storage_eligible,
                    Location.certified_max_weight_kg,
                    Location.operational_max_weight_kg,
                    Location.certified_usable_volume_m3,
                    Location.operational_usable_volume_m3,
                    Location.capacity_enforcement_mode,
                ).where(
                    Location.warehouse_id == warehouse_id,
                    Location.deleted_at.is_(None),
                )
            )
        ).all()
        by_status = Counter(row[0] for row in rows)
        by_type = Counter(row[1] for row in rows)
        capacity_statuses = Counter(
            (
                "not_configured"
                if not row[4] or not any(row[index] is not None for index in range(5, 9))
                else "available"
                if all(row[index] is not None for index in range(5, 9))
                else "incomplete"
            )
            for row in rows
        )
        # Keep the API value stable and machine-readable.  The frontend renders
        # this sentinel as “Sin área”; returning the display label here would
        # create a second option alongside the canonical ``__none__`` filter.
        areas = Counter(row[2] or "__none__" for row in rows)
        return {
            "total": len(rows),
            "storage_eligible": sum(1 for row in rows if row[4]),
            "capacity_configured": capacity_statuses["available"],
            "capacity_incomplete": capacity_statuses["incomplete"],
            "active": sum(1 for row in rows if row[3]),
            "inactive": sum(1 for row in rows if not row[3]),
            "by_status": dict(sorted(by_status.items())),
            "by_type": dict(sorted(by_type.items())),
            "areas": dict(sorted(areas.items())),
        }

    @staticmethod
    def _resolve_batch_target(  # noqa: PLR0911 - each rejection preserves a precise conflict reason
        data: Mapping[str, Any],
        indexes: _LocationIndexes,
    ) -> tuple[Location | None, str | None]:
        """Resolve a stable target using strong IDs before legacy coordinates."""

        external_key = str(data.get("external_id") or "").casefold()
        code_key = str(data.get("code") or "").casefold()
        existing_by_external = indexes.by_external.get(external_key) if external_key else None
        existing_by_code = indexes.by_code.get(code_key) if code_key else None
        direct = {
            item.id: item for item in (existing_by_external, existing_by_code) if item is not None
        }
        if len(direct) > 1:
            return None, "Los identificadores de la fila apuntan a ubicaciones diferentes."

        coordinate_key = _coordinate_key(data)
        if coordinate_key in indexes.ambiguous_coordinates:
            return None, "Las coordenadas coinciden con más de una ubicación heredada."
        coordinate = indexes.by_coordinates.get(coordinate_key)
        target = next(iter(direct.values()), None)
        if target is not None:
            if coordinate is not None and coordinate.id != target.id:
                return (
                    None,
                    "Los identificadores y las coordenadas apuntan a ubicaciones diferentes.",
                )
            return target, None
        if coordinate is None:
            return None, None
        if coordinate.code_source != "legacy":
            return None, "Las coordenadas ya pertenecen a una ubicación administrada."

        provided_fields = set(data.get("_provided_fields") or ())
        incoming_external = data.get("external_id")
        if (
            "external_id" in provided_fields
            and coordinate.external_id is not None
            and incoming_external != coordinate.external_id
        ):
            return None, "El ID externo no coincide con la ubicación heredada."
        return coordinate, None

    @classmethod
    def _preview_operation(  # noqa: C901 - conflict, legacy adoption and diff semantics
        cls,
        data: Mapping[str, Any],
        indexes: _LocationIndexes,
    ) -> tuple[str, str | None, dict[str, Any], list[str], Location | None]:
        errors = list(data.get("_errors") or [])
        code = data.get("code")
        if errors or not code:
            return (
                "error",
                str(code) if code else None,
                {},
                errors or ["Fila inválida."],
                None,
            )
        existing, target_error = cls._resolve_batch_target(data, indexes)
        if target_error:
            return "conflict", str(code), {}, [target_error], None
        alias_owner = indexes.aliases.get(str(code).casefold())
        if alias_owner is not None and (existing is None or alias_owner != existing.id):
            return (
                "conflict",
                str(code),
                {},
                ["El código es un alias histórico reservado."],
                None,
            )
        if existing is None:
            return "create", str(code), {}, [], None
        effective_data = dict(data)
        provided_fields = set(data.get("_provided_fields") or ())
        if provided_fields:
            for field in _LOCATION_FIELDS:
                if field not in provided_fields:
                    effective_data[field] = getattr(existing, field)
            if "lifecycle_status" not in provided_fields:
                effective_data["is_active"] = existing.is_active
        diff: dict[str, Any] = {}
        for field in _LOCATION_FIELDS:
            incoming = effective_data.get(field)
            current = getattr(existing, field)
            if not _location_values_equal(field, incoming, current):
                diff[field] = {"before": current, "after": incoming}
        incoming_active = bool(effective_data.get("is_active", True))
        if incoming_active != existing.is_active:
            diff["is_active"] = {"before": existing.is_active, "after": incoming_active}
        if str(code).casefold() != existing.code.casefold():
            diff["code"] = {"before": existing.code, "after": code}
        return ("update" if diff else "unchanged"), str(code), diff, [], existing

    def _stage_batch_rows(  # noqa: C901 - staging validates each row under one batch invariant
        self,
        job: LocationBatchJob,
        source_rows: Sequence[Mapping[str, Any]],
        indexes: _LocationIndexes,
    ) -> tuple[Counter[str], list[LocationBatchRow], tuple[str, ...], bool]:
        counts: Counter[str] = Counter()
        required_permissions = {"locations.import" if job.kind == "import" else "locations.bulk"}
        seen_codes: set[str] = set()
        seen_external_ids: set[str] = set()
        seen_coordinates: set[tuple[Any, ...]] = set()
        seen_target_ids: set[uuid.UUID] = set()
        preview_rows: list[LocationBatchRow] = []
        has_positive_impact = False
        for source in source_rows:
            operation, code, diff, errors, target = self._preview_operation(source, indexes)
            code_key = code.casefold() if code else None
            external_key = str(source.get("external_id") or "").casefold() or None
            coordinate_key = tuple(
                source.get(key) for key in ("area", "aisle", "rack", "level", "position")
            )
            if operation not in {"error", "conflict"} and (
                (code_key is not None and code_key in seen_codes)
                or (external_key is not None and external_key in seen_external_ids)
                or coordinate_key in seen_coordinates
                or (target is not None and target.id in seen_target_ids)
            ):
                operation = "conflict"
                errors = ["El mismo código o coordenadas se repiten dentro del lote."]
                diff = {}
            if code_key:
                seen_codes.add(code_key)
            if external_key:
                seen_external_ids.add(external_key)
            seen_coordinates.add(coordinate_key)
            if target is not None:
                seen_target_ids.add(target.id)
            counts[operation] += 1
            has_positive_impact = has_positive_impact or _batch_row_has_positive_impact(
                operation, diff
            )
            normalized_data = {
                key: value for key, value in source.items() if key not in {"row_number", "_errors"}
            }
            if target is not None:
                provided_fields = set(source.get("_provided_fields") or ())
                if provided_fields:
                    for field in _LOCATION_FIELDS:
                        if field not in provided_fields:
                            normalized_data[field] = getattr(target, field)
                    if "lifecycle_status" not in provided_fields:
                        normalized_data["is_active"] = target.is_active
            _extend_batch_permissions(required_permissions, operation, diff)
            if operation in {"update", "unchanged"} and target is not None:
                normalized_data["_preview_target_location_id"] = str(target.id)
                normalized_data["_preview_target_updated_at"] = target.updated_at.isoformat()
            row = LocationBatchRow(
                job_id=job.id,
                row_number=int(source["row_number"]),
                operation=operation,
                code=code,
                normalized_data=_json_safe(normalized_data),
                diff=_json_safe(diff),
                errors=_json_safe(errors),
            )
            self._session.add(row)
            if len(preview_rows) < PREVIEW_ROW_LIMIT:
                preview_rows.append(row)
        return (
            counts,
            preview_rows,
            tuple(sorted(required_permissions)),
            has_positive_impact,
        )

    async def create_batch_preview(
        self,
        warehouse_id: uuid.UUID,
        *,
        kind: str,
        idempotency_key: str,
        input_checksum: str,
        scheme: DomainLocationCodeScheme,
        source_rows: Sequence[Mapping[str, Any]],
        actor_id: uuid.UUID,
    ) -> LocationBatchRecord:
        existing = await self._session.scalar(
            select(LocationBatchJob).where(
                LocationBatchJob.warehouse_id == warehouse_id,
                LocationBatchJob.kind == kind,
                LocationBatchJob.idempotency_key == idempotency_key,
            )
        )
        if existing:
            if existing.input_checksum != input_checksum:
                raise ConflictError(
                    "La clave de idempotencia ya fue utilizada con otra entrada.",
                    code="location_batch_idempotency_mismatch",
                )
            return await self.get_batch(existing.id)

        indexes = await self._load_location_indexes(warehouse_id, scheme=scheme)
        scope = await self.get_warehouse_scope(warehouse_id)
        job = LocationBatchJob(
            warehouse_id=warehouse_id,
            kind=kind,
            status="preview",
            idempotency_key=idempotency_key,
            input_checksum=input_checksum,
            code_scheme_id=scheme.id,
            scheme_version=scheme.version,
            total_rows=len(source_rows),
            created_by=actor_id,
        )
        preview_rows: list[LocationBatchRow] = []
        try:
            async with self._session.begin_nested():
                self._session.add(job)
                await self._session.flush()
                (
                    counts,
                    preview_rows,
                    required_permissions,
                    has_positive_impact,
                ) = self._stage_batch_rows(job, source_rows, indexes)
                if (
                    not scope.warehouse_active or scope.operational_status == "inactive"
                ) and has_positive_impact:
                    raise ConflictError(
                        "El almacén solo admite retiros, reducciones o cambios de metadatos en su estado actual.",
                        code="warehouse_not_commissionable",
                    )
                job.create_count = counts["create"]
                job.update_count = counts["update"]
                job.unchanged_count = counts["unchanged"]
                job.conflict_count = counts["conflict"]
                job.error_count = counts["error"]
                job.summary = {
                    "publishable": not (job.conflict_count or job.error_count),
                    "preview_row_limit": PREVIEW_ROW_LIMIT,
                    "counts": dict(counts),
                    "required_permissions": list(required_permissions),
                }
                self._session.add(
                    AuditLog(
                        action="LOCATION_BATCH_PREVIEW",
                        user_id=actor_id,
                        company_id=scope.company_id,
                        branch_id=scope.branch_id,
                        resource_type="location_batch_jobs",
                        resource_id=str(job.id),
                        after_state={
                            "warehouse_id": str(warehouse_id),
                            "kind": kind,
                            "input_checksum": input_checksum,
                            "scheme_version": scheme.version,
                            "total_rows": job.total_rows,
                            **job.summary,
                        },
                        metadata_={
                            "correlation_id": str(job.id),
                            "idempotency_key": idempotency_key,
                        },
                    )
                )
                await self._session.flush()
        except IntegrityError as exc:
            winner = await self._session.scalar(
                select(LocationBatchJob).where(
                    LocationBatchJob.warehouse_id == warehouse_id,
                    LocationBatchJob.kind == kind,
                    LocationBatchJob.idempotency_key == idempotency_key,
                )
            )
            if winner is None:
                raise
            if winner.input_checksum != input_checksum:
                raise ConflictError(
                    "La clave de idempotencia ya fue utilizada con otra entrada.",
                    code="location_batch_idempotency_mismatch",
                ) from exc
            return await self.get_batch(winner.id)

        return _job_to_domain(job, preview_rows)

    async def get_batch(
        self, job_id: uuid.UUID, *, page: int = 1, size: int = 100
    ) -> LocationBatchRecord:
        page = max(1, page)
        size = max(1, min(size, PREVIEW_ROW_LIMIT))
        job = await self._session.get(LocationBatchJob, job_id)
        if job is None:
            raise NotFoundError("Lote no encontrado.", code="location_batch_not_found")
        rows = list(
            (
                await self._session.execute(
                    select(LocationBatchRow)
                    .where(LocationBatchRow.job_id == job_id)
                    .order_by(LocationBatchRow.row_number)
                    .offset((page - 1) * size)
                    .limit(size)
                )
            ).scalars()
        )
        return _job_to_domain(job, rows, page=page, size=size)

    async def batch_required_permissions(self, job_id: uuid.UUID) -> tuple[str, ...]:
        job = await self._session.get(LocationBatchJob, job_id)
        if job is None:
            raise NotFoundError("Lote no encontrado.", code="location_batch_not_found")
        rows = (
            await self._session.execute(
                select(LocationBatchRow.operation, LocationBatchRow.diff).where(
                    LocationBatchRow.job_id == job_id,
                    LocationBatchRow.operation.in_(("create", "update")),
                )
            )
        ).all()
        required = {"locations.import" if job.kind == "import" else "locations.bulk"}
        for operation, diff in rows:
            _extend_batch_permissions(required, operation, dict(diff or {}))
        return tuple(sorted(required))

    async def publish_batch(  # noqa: C901
        self, job_id: uuid.UUID, *, actor_id: uuid.UUID
    ) -> LocationBatchRecord:
        job = await self._session.scalar(
            select(LocationBatchJob).where(LocationBatchJob.id == job_id).with_for_update()
        )
        if job is None:
            raise NotFoundError("Lote no encontrado.", code="location_batch_not_found")
        if job.status == "published":
            return await self.get_batch(job.id)
        if job.status != "preview":
            raise ConflictError(
                "El lote ya no se encuentra en estado de vista previa.",
                code="location_batch_status_invalid",
            )
        if job.conflict_count or job.error_count:
            raise ConflictError(
                "Corrija los conflictos y errores antes de publicar el lote.",
                code="location_batch_not_publishable",
            )
        warehouse = await self._session.scalar(
            select(Warehouse).where(Warehouse.id == job.warehouse_id).with_for_update()
        )
        if warehouse is None:
            raise NotFoundError("Almacén no encontrado.", code="warehouse_not_found")
        warehouse_is_commissionable = warehouse.is_active and (
            warehouse.operational_status != "inactive"
        )
        scheme = await self.get_scheme(job.warehouse_id, job.scheme_version)
        rows = list(
            (
                await self._session.execute(
                    select(LocationBatchRow)
                    .where(LocationBatchRow.job_id == job.id)
                    .order_by(LocationBatchRow.row_number)
                    .with_for_update()
                )
            ).scalars()
        )
        indexes = await self._load_location_indexes(
            job.warehouse_id, scheme=scheme, for_update=True
        )
        # Revalidate every row under the warehouse lock; previews are advisory,
        # publication is the authoritative atomic decision. Capacity limits of
        # locations are independent scopes and are never summed as warehouse
        # structural resistance.
        has_positive_impact = False
        validated_targets: dict[uuid.UUID, Location] = {}
        for row in rows:
            operation, _code, current_diff, errors, existing = self._preview_operation(
                row.normalized_data, indexes
            )
            if operation in {"error", "conflict"}:
                raise ConflictError(
                    f"La fila {row.row_number} cambió desde la vista previa: {'; '.join(errors)}",
                    code="location_batch_stale_preview",
                )
            if row.operation != operation:
                raise ConflictError(
                    f"La fila {row.row_number} cambió desde la vista previa.",
                    code="location_batch_stale_preview",
                )
            if _json_safe(current_diff) != _json_safe(row.diff or {}):
                raise ConflictError(
                    f"La fila {row.row_number} fue modificada después de la vista previa.",
                    code="location_batch_stale_preview",
                )
            has_positive_impact = has_positive_impact or _batch_row_has_positive_impact(
                operation, current_diff
            )
            if operation in {"update", "unchanged"}:
                data = row.normalized_data
                if existing is None:
                    raise ConflictError(
                        f"La fila {row.row_number} ya no tiene un destino actualizable.",
                        code="location_batch_stale_preview",
                    )
                preview_target = str(data.get("_preview_target_location_id") or "")
                preview_updated_at = str(data.get("_preview_target_updated_at") or "")
                if (
                    preview_target != str(existing.id)
                    or preview_updated_at != existing.updated_at.isoformat()
                ):
                    raise ConflictError(
                        f"La fila {row.row_number} fue modificada después de la vista previa.",
                        code="location_batch_stale_preview",
                    )
                validated_targets[row.id] = existing
        if not warehouse_is_commissionable and has_positive_impact:
            raise ConflictError(
                "El almacén solo admite retiros, reducciones o cambios de metadatos en su estado actual.",
                code="warehouse_not_commissionable",
            )

        group_ids = {
            uuid.UUID(str(row.normalized_data["capacity_group_id"]))
            for row in rows
            if row.operation in {"create", "update"}
            and row.normalized_data.get("capacity_group_id")
        }
        if group_ids:
            available_groups = set(
                (
                    await self._session.execute(
                        select(WarehouseCapacityGroup.id).where(
                            WarehouseCapacityGroup.id.in_(group_ids),
                            WarehouseCapacityGroup.warehouse_id == job.warehouse_id,
                            WarehouseCapacityGroup.is_active.is_(True),
                            WarehouseCapacityGroup.deleted_at.is_(None),
                        )
                    )
                ).scalars()
            )
            if available_groups != group_ids:
                raise ConflictError(
                    "El lote referencia un grupo de capacidad no disponible en el almacén.",
                    code="location_capacity_group_unavailable",
                )

        scope = await self.get_warehouse_scope(job.warehouse_id)
        try:
            async with self._session.begin_nested():
                job.status = "publishing"
                for row in rows:
                    data = dict(row.normalized_data)
                    projection = CodeProjection(
                        code=str(data["code"]),
                        normalized_components={
                            key: str(data.get(key) or "")
                            for key in ("area", "aisle", "rack", "level", "position")
                        },
                        scheme_id=scheme.id,
                        scheme_version=scheme.version,
                    )
                    if row.operation == "create":
                        await SqlAlchemyCapacityHierarchyRepository(
                            self._session
                        ).validate_location_write(job.warehouse_id, data)
                        model = Location(
                            warehouse_id=job.warehouse_id,
                            code=projection.code,
                            **_location_model_values(data),
                            code_scheme_id=scheme.id,
                            scheme_version=scheme.version,
                            code_source=str(data.get("code_source") or "generated"),
                            is_active=bool(data.get("is_active", True)),
                        )
                        self._session.add(model)
                        await self._session.flush()
                        self._session.add(
                            AuditLog(
                                action="CREATE",
                                user_id=actor_id,
                                company_id=scope.company_id,
                                branch_id=scope.branch_id,
                                resource_type="locations",
                                resource_id=str(model.id),
                                after_state=_audit_state(model),
                                metadata_={
                                    "correlation_id": str(job.id),
                                    "batch_row": row.row_number,
                                },
                            )
                        )
                        row.published_location_id = model.id
                    elif row.operation == "update":
                        model = validated_targets.get(row.id)
                        if model is None:
                            raise ConflictError(
                                f"La fila {row.row_number} ya no tiene un destino actualizable.",
                                code="location_batch_stale_preview",
                            )
                        before_state = _audit_state(model)
                        await SqlAlchemyCapacityHierarchyRepository(
                            self._session
                        ).validate_location_write(job.warehouse_id, data, location_id=model.id)
                        old_code = model.code
                        if old_code.casefold() != projection.code.casefold():
                            old_alias_owner = indexes.aliases.get(old_code.casefold())
                            if old_alias_owner is not None and old_alias_owner != model.id:
                                raise ConflictError(
                                    f"La fila {row.row_number} usa el alias de otra ubicación.",
                                    code="location_batch_stale_preview",
                                )
                            if old_alias_owner is None:
                                self._session.add(
                                    LocationCodeAlias(
                                        warehouse_id=job.warehouse_id,
                                        location_id=model.id,
                                        alias_code=old_code,
                                        code_scheme_id=model.code_scheme_id,
                                        scheme_version=model.scheme_version,
                                        reason="bulk_recode",
                                        created_by=actor_id,
                                    )
                                )
                                indexes.aliases[old_code.casefold()] = model.id
                        model.code = projection.code
                        for name in _LOCATION_FIELDS:
                            setattr(model, name, data.get(name))
                        model.code_scheme_id = scheme.id
                        model.scheme_version = scheme.version
                        model.code_source = str(data.get("code_source") or "imported")
                        model.is_active = bool(data.get("is_active", True))
                        await self._session.flush()
                        self._session.add(
                            AuditLog(
                                action="UPDATE",
                                user_id=actor_id,
                                company_id=scope.company_id,
                                branch_id=scope.branch_id,
                                resource_type="locations",
                                resource_id=str(model.id),
                                before_state=before_state,
                                after_state=_audit_state(model),
                                metadata_={
                                    "correlation_id": str(job.id),
                                    "batch_row": row.row_number,
                                },
                            )
                        )
                        row.published_location_id = model.id
                    elif row.operation == "unchanged":
                        model = validated_targets.get(row.id)
                        row.published_location_id = model.id if model else None
                job.status = "published"
                job.published_by = actor_id
                job.published_at = datetime.now(UTC)
                self._session.add(
                    AuditLog(
                        action="LOCATION_BATCH_PUBLISHED",
                        user_id=actor_id,
                        company_id=scope.company_id,
                        branch_id=scope.branch_id,
                        resource_type="location_batch_jobs",
                        resource_id=str(job.id),
                        before_state={"status": "preview"},
                        after_state={
                            "status": "published",
                            "kind": job.kind,
                            "total_rows": job.total_rows,
                            "created": job.create_count,
                            "updated": job.update_count,
                            "unchanged": job.unchanged_count,
                        },
                        metadata_={
                            "correlation_id": str(job.id),
                            "idempotency_key": job.idempotency_key,
                            "input_checksum": job.input_checksum,
                        },
                    )
                )
                await self._session.flush()
        except IntegrityError as exc:
            raise ConflictError(
                "La publicación encontró un identificador duplicado.",
                code="location_batch_publish_conflict",
            ) from exc
        return await self.get_batch(job.id, page=1, size=PREVIEW_ROW_LIMIT)
