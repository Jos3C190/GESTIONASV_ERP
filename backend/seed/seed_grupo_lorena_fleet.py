"""Idempotent development seed for the Grupo Lorena fleet.

Each branch gets two delivery vehicles (a refrigerated truck for cakes and a
cargo van) and two drivers. Drivers are new fictional employees of the
"Logística y Distribución" department with an EMPLEADO user account that has an
unrecoverable random password, like every other seeded account.

The seed follows the same rules as the Fleet and Drivers screens: the
department is opened in the branch before hiring, the driver keeps an active
assignment in their home branch, and the license class allows the vehicle kind.
Mandatory documents (driver license, circulation card, insurance...) are not
invented: they must be uploaded through Documents. Until then each vehicle is
assigned to its driver with a recorded compliance override, exactly as a user
with ``fleet:compliance_override`` would do it.

Run inside the backend container: ``python -m seed.seed_grupo_lorena_fleet``.
"""

from __future__ import annotations

import asyncio
import secrets
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import func, select

from seed.grupo_lorena_media import COMPANY_ID
from seed.seed_grupo_lorena import SUPER_ADMIN_USERNAME, _restore_seed_record, _session_factory

SOURCE = "seed_grupo_lorena_fleet"
DEPARTMENT = "Logística y Distribución"
POSITION = "Conductor"
DRIVER_ROLE = "EMPLEADO"
OVERRIDE_REASON = (
    "Datos de desarrollo: licencia y documentos del vehículo pendientes de cargar en Documentos."
)


@dataclass(frozen=True, slots=True)
class VehicleSeed:
    code: str
    plate: str
    kind: str
    brand: str
    model: str
    year: int
    capacity_kg: str
    fuel_type: str
    odometer_km: str
    notes: str


@dataclass(frozen=True, slots=True)
class DriverSeed:
    code: str
    first: str
    last: str
    username: str
    license_class: str
    #: Vehicle code assigned to the driver.
    vehicle: str


@dataclass(frozen=True, slots=True)
class BranchFleetSeed:
    branch: str
    vehicles: tuple[VehicleSeed, VehicleSeed]
    drivers: tuple[DriverSeed, DriverSeed]


REFRIGERATED_NOTE = "Furgón refrigerado para pasteles y producto de cadena de frío."
VAN_NOTE = "Panel para reparto urbano de pedidos y abastecimiento entre sucursales."


def _fleet(
    branch: str,
    suffix: str,
    truck: tuple[str, str, str, int, str, str],
    van: tuple[str, str, str, int, str, str, str],
    truck_driver: tuple[str, str, str, str],
    van_driver: tuple[str, str, str, str],
) -> BranchFleetSeed:
    truck_code, van_code = f"VEH-{suffix}-01", f"VEH-{suffix}-02"
    plate, brand, model, year, capacity, odometer = truck
    van_plate, van_brand, van_model, van_year, van_capacity, van_fuel, van_odometer = van
    return BranchFleetSeed(
        branch=branch,
        vehicles=(
            VehicleSeed(
                truck_code,
                plate,
                "refrigerated",
                brand,
                model,
                year,
                capacity,
                "diesel",
                odometer,
                REFRIGERATED_NOTE,
            ),
            VehicleSeed(
                van_code,
                van_plate,
                "cargo_van",
                van_brand,
                van_model,
                van_year,
                van_capacity,
                van_fuel,
                van_odometer,
                VAN_NOTE,
            ),
        ),
        drivers=(
            DriverSeed(*truck_driver, license_class="pesada", vehicle=truck_code),
            DriverSeed(*van_driver, license_class="liviana", vehicle=van_code),
        ),
    )


FLEET: tuple[BranchFleetSeed, ...] = (
    _fleet(
        "LOR-SM-01",
        "SM",
        ("C 118-402", "Isuzu", "NQR 75 Refrigerado", 2022, "3500", "68420.0"),
        ("C 207-315", "Toyota", "Hiace Panel", 2023, "1200", "diesel", "41250.0"),
        ("GL-0027", "Wilfredo Antonio", "Saravia Medrano", "wilfredo.saravia"),
        ("GL-0028", "Josué Alexander", "Lazo Guzmán", "josue.lazo"),
    ),
    _fleet(
        "LOR-USU-01",
        "USU",
        ("C 118-517", "Hino", "300 Serie 616 Refrigerado", 2021, "3000", "82760.0"),
        ("C 207-428", "Nissan", "Urvan Panel", 2022, "1100", "gasoline", "53980.0"),
        ("GL-0029", "Edwin Rolando", "Chávez Portillo", "edwin.chavez"),
        ("GL-0030", "Marvin Ernesto", "Rivas Cruz", "marvin.rivas"),
    ),
    _fleet(
        "LOR-JIQ-01",
        "JIQ",
        ("C 118-633", "Mitsubishi Fuso", "Canter Refrigerado", 2020, "2500", "97310.0"),
        ("C 207-541", "Hyundai", "H-1 Panel", 2021, "1000", "diesel", "61470.0"),
        ("GL-0031", "Nelson Mauricio", "Ayala Rodríguez", "nelson.ayala"),
        ("GL-0032", "Cristian Josué", "Hernández Lovo", "cristian.hernandez"),
    ),
    _fleet(
        "LOR-LU-01",
        "LU",
        ("C 118-749", "Isuzu", "NPR Refrigerado", 2021, "3000", "88140.0"),
        ("C 207-654", "Toyota", "Hiace Panel", 2022, "1200", "diesel", "47720.0"),
        ("GL-0033", "Francisco Javier", "Umaña Reyes", "francisco.umana"),
        ("GL-0034", "René Alonso", "Mejía Vásquez", "rene.mejia"),
    ),
    _fleet(
        "LOR-SRL-01",
        "SRL",
        ("C 118-852", "Hino", "300 Serie 616 Refrigerado", 2022, "3000", "71590.0"),
        ("C 207-767", "Nissan", "Urvan Panel", 2023, "1100", "gasoline", "29860.0"),
        ("GL-0035", "Douglas Enrique", "Argueta Romero", "douglas.argueta"),
        ("GL-0036", "Kevin Alexis", "Sorto Benítez", "kevin.sorto"),
    ),
    _fleet(
        "LOR-GOT-01",
        "GOT",
        ("C 118-968", "Mitsubishi Fuso", "Canter Refrigerado", 2021, "2500", "90230.0"),
        ("C 207-873", "Hyundai", "H-1 Panel", 2022, "1000", "diesel", "52610.0"),
        ("GL-0037", "Óscar René", "Villalta Pérez", "oscar.villalta"),
        ("GL-0038", "Byron Ulises", "Majano Díaz", "byron.majano"),
    ),
    _fleet(
        "LOR-ET-01",
        "ET",
        ("C 119-074", "Isuzu", "NQR 75 Refrigerado", 2023, "3500", "38940.0"),
        ("C 207-986", "Toyota", "Hiace Panel", 2021, "1200", "diesel", "66380.0"),
        ("GL-0039", "Henry Alberto", "Campos Molina", "henry.campos"),
        ("GL-0040", "Erick Geovanny", "Flores Amaya", "erick.flores"),
    ),
)


def validate_fleet_seed() -> None:
    from app.api.v1.schemas.fleet import normalize_plate
    from app.application.fleet.compliance import LICENSE_CLASSES_BY_KIND

    vehicles = [vehicle for item in FLEET for vehicle in item.vehicles]
    drivers = [driver for item in FLEET for driver in item.drivers]
    for label, values in (
        ("códigos de vehículo", [vehicle.code for vehicle in vehicles]),
        ("placas", [normalize_plate(vehicle.plate) for vehicle in vehicles]),
        ("códigos de empleado", [driver.code for driver in drivers]),
        ("usuarios", [driver.username.casefold() for driver in drivers]),
        ("vehículos asignados", [driver.vehicle for driver in drivers]),
    ):
        if len(values) != len(set(values)):
            raise ValueError(f"Hay {label} duplicados en el seed de flota.")
    for item in FLEET:
        kinds = {vehicle.code: vehicle.kind for vehicle in item.vehicles}
        for driver in item.drivers:
            kind = kinds.get(driver.vehicle)
            if kind is None:
                raise ValueError(f"{driver.code} tiene un vehículo de otra sucursal.")
            if driver.license_class not in LICENSE_CLASSES_BY_KIND[kind]:
                raise ValueError(f"La licencia de {driver.code} no permite conducir {kind}.")


async def seed() -> None:  # noqa: C901 - explicit orchestration keeps the seed atomic
    from app.api.v1.routers.fleet import ensure_inventory_vehicle
    from app.core.security import hash_password
    from app.infrastructure.models.audit import AuditLog
    from app.infrastructure.models.employee import (
        Department,
        DepartmentBranchAssignment,
        Employee,
        EmployeeBranchAssignment,
    )
    from app.infrastructure.models.fleet import (
        DriverModel,
        FleetVehicleModel,
        OdometerReadingModel,
        VehicleDriverAssignmentModel,
    )
    from app.infrastructure.models.organization import Branch, UserBranch, UserCompany
    from app.infrastructure.models.rbac import Role, UserRole
    from app.infrastructure.models.user import User

    validate_fleet_seed()
    factory = _session_factory()
    async with factory() as session:
        actor = await session.scalar(
            select(User).where(
                func.lower(User.username) == SUPER_ADMIN_USERNAME.casefold(),
                User.deleted_at.is_(None),
            )
        )
        if actor is None:
            raise RuntimeError("Ejecute primero el seed de Grupo Lorena (falta el superadmin).")
        actor_id = actor.id
        department = await session.scalar(
            select(Department).where(
                Department.company_id == COMPANY_ID,
                Department.name == DEPARTMENT,
                Department.deleted_at.is_(None),
            )
        )
        role = await session.scalar(
            select(Role).where(
                Role.company_id == COMPANY_ID, Role.name == DRIVER_ROLE, Role.deleted_at.is_(None)
            )
        )
        if department is None or role is None:
            raise RuntimeError(f"Faltan el departamento {DEPARTMENT} o el rol {DRIVER_ROLE}.")

        def audit(
            action: str,
            resource_type: str,
            resource_id: object,
            branch_id: object,
            after_state: dict[str, object],
            **metadata: object,
        ) -> None:
            session.add(
                AuditLog(
                    user_id=actor_id,
                    company_id=COMPANY_ID,
                    branch_id=branch_id,
                    action=action,
                    resource_type=resource_type,
                    resource_id=str(resource_id),
                    after_state=after_state,
                    status="success",
                    metadata_={"source": SOURCE, **metadata},
                )
            )

        random_password_hash = hash_password(secrets.token_urlsafe(48))
        created = {"vehicles": 0, "drivers": 0, "users": 0, "assignments": 0}
        for item in FLEET:
            branch = await session.scalar(
                select(Branch).where(
                    Branch.company_id == COMPANY_ID,
                    Branch.code == item.branch,
                    Branch.deleted_at.is_(None),
                )
            )
            if branch is None or not branch.is_active:
                raise RuntimeError(f"La sucursal {item.branch} no existe o no está activa.")

            # The department must be open in the branch before hiring into it.
            opening = await session.scalar(
                select(DepartmentBranchAssignment).where(
                    DepartmentBranchAssignment.department_id == department.id,
                    DepartmentBranchAssignment.branch_id == branch.id,
                )
            )
            if opening is None:
                opening = DepartmentBranchAssignment(
                    department_id=department.id, branch_id=branch.id
                )
                session.add(opening)
            opening.is_active = True
            opening.closed_at = None

            vehicles: dict[str, FleetVehicleModel] = {}
            for vehicle_seed in item.vehicles:
                vehicle = await session.scalar(
                    select(FleetVehicleModel)
                    .where(
                        FleetVehicleModel.company_id == COMPANY_ID,
                        func.lower(FleetVehicleModel.code) == vehicle_seed.code.casefold(),
                    )
                    .order_by(FleetVehicleModel.deleted_at.asc().nullsfirst())
                    .limit(1)
                    .execution_options(include_deleted=True)
                )
                if vehicle is None:
                    vehicle = FleetVehicleModel(
                        company_id=COMPANY_ID,
                        branch_id=branch.id,
                        code=vehicle_seed.code,
                        plate=vehicle_seed.plate,
                        kind=vehicle_seed.kind,
                        brand=vehicle_seed.brand,
                        model=vehicle_seed.model,
                        year=vehicle_seed.year,
                        color="Blanco",
                        capacity_kg=Decimal(vehicle_seed.capacity_kg),
                        fuel_type=vehicle_seed.fuel_type,
                        odometer_km=Decimal(vehicle_seed.odometer_km),
                        notes=vehicle_seed.notes,
                        status="active",
                        created_by=actor_id,
                        updated_by=actor_id,
                    )
                    vehicle.inventory_vehicle_id = await ensure_inventory_vehicle(
                        session, vehicle, actor_id
                    )
                    session.add(vehicle)
                    await session.flush()
                    session.add(
                        OdometerReadingModel(
                            company_id=COMPANY_ID,
                            vehicle_id=vehicle.id,
                            reading_km=vehicle.odometer_km,
                            read_at=datetime.now(UTC),
                            source="manual",
                            notes="Lectura inicial al registrar el vehículo.",
                            recorded_by=actor_id,
                        )
                    )
                    audit(
                        "CREATE",
                        "fleet_vehicles",
                        vehicle.id,
                        branch.id,
                        {
                            "code": vehicle.code,
                            "plate": vehicle.plate,
                            "kind": vehicle.kind,
                            "branch_id": str(branch.id),
                        },
                    )
                    created["vehicles"] += 1
                else:
                    # Never move or rewrite a vehicle someone already edited.
                    _restore_seed_record(vehicle)
                vehicles[vehicle_seed.code] = vehicle

            for driver_seed in item.drivers:
                employee = await session.scalar(
                    select(Employee)
                    .where(
                        Employee.company_id == COMPANY_ID,
                        func.lower(Employee.employee_code) == driver_seed.code.casefold(),
                    )
                    .order_by(Employee.deleted_at.asc().nullsfirst())
                    .limit(1)
                    .execution_options(include_deleted=True)
                )
                if employee is None:
                    employee = Employee(
                        company_id=COMPANY_ID,
                        employee_code=driver_seed.code,
                        first_name=driver_seed.first,
                        last_name=driver_seed.last,
                        department_id=department.id,
                        position=POSITION,
                        hire_date=date(2024, int(driver_seed.code[-2:]) % 12 + 1, 1),
                        status="activo",
                    )
                    session.add(employee)
                    await session.flush()
                    audit(
                        "CREATE",
                        "employees",
                        employee.id,
                        branch.id,
                        {
                            "employee_code": employee.employee_code,
                            "name": f"{employee.first_name} {employee.last_name}",
                            "position": POSITION,
                        },
                        identity="fictional",
                    )
                else:
                    _restore_seed_record(employee)
                    employee.status = "activo"

                assignment = await session.scalar(
                    select(EmployeeBranchAssignment).where(
                        EmployeeBranchAssignment.employee_id == employee.id,
                        EmployeeBranchAssignment.branch_id == branch.id,
                        EmployeeBranchAssignment.is_active.is_(True),
                    )
                )
                if assignment is None:
                    session.add(
                        EmployeeBranchAssignment(
                            employee_id=employee.id,
                            branch_id=branch.id,
                            is_primary=True,
                            position=POSITION,
                            shift="mañana",
                            is_active=True,
                        )
                    )

                if employee.user_id is None:
                    user = await session.scalar(
                        select(User).where(
                            func.lower(User.username) == driver_seed.username.casefold(),
                            User.deleted_at.is_(None),
                        )
                    )
                    if user is None:
                        user = User(
                            username=driver_seed.username,
                            email=f"{driver_seed.username}@grupo-lorena.example",
                            password_hash=random_password_hash,
                            is_active=True,
                            is_superuser=False,
                        )
                        session.add(user)
                        await session.flush()
                        audit(
                            "CREATE",
                            "users",
                            user.id,
                            branch.id,
                            {"username": user.username, "employee_code": driver_seed.code},
                            password_reset_required=True,
                        )
                        created["users"] += 1
                    employee.user_id = user.id
                    if await session.get(UserCompany, (user.id, COMPANY_ID)) is None:
                        session.add(
                            UserCompany(
                                user_id=user.id,
                                company_id=COMPANY_ID,
                                is_default=True,
                                access_all_branches=False,
                                last_branch_id=branch.id,
                            )
                        )
                        await session.flush()
                    if await session.get(UserRole, (user.id, COMPANY_ID, role.id)) is None:
                        session.add(
                            UserRole(
                                user_id=user.id,
                                company_id=COMPANY_ID,
                                role_id=role.id,
                                assigned_by=actor_id,
                            )
                        )
                    if await session.get(UserBranch, (user.id, branch.id)) is None:
                        session.add(
                            UserBranch(
                                user_id=user.id,
                                company_id=COMPANY_ID,
                                branch_id=branch.id,
                                assigned_by=actor_id,
                                is_default=True,
                                is_active=True,
                            )
                        )

                driver = await session.scalar(
                    select(DriverModel).where(
                        DriverModel.company_id == COMPANY_ID,
                        DriverModel.employee_id == employee.id,
                        DriverModel.deleted_at.is_(None),
                    )
                )
                if driver is None:
                    driver = DriverModel(
                        company_id=COMPANY_ID,
                        employee_id=employee.id,
                        branch_id=branch.id,
                        license_class=driver_seed.license_class,
                        status="active",
                        created_by=actor_id,
                        updated_by=actor_id,
                    )
                    session.add(driver)
                    await session.flush()
                    audit(
                        "CREATE",
                        "drivers",
                        driver.id,
                        branch.id,
                        {
                            "employee_id": str(employee.id),
                            "branch_id": str(branch.id),
                            "license_class": driver.license_class,
                        },
                    )
                    created["drivers"] += 1

                # Assign only free pairs: never take over an assignment made by a user.
                vehicle = vehicles[driver_seed.vehicle]
                busy = await session.scalar(
                    select(func.count())
                    .select_from(VehicleDriverAssignmentModel)
                    .where(
                        VehicleDriverAssignmentModel.ends_at.is_(None),
                        (VehicleDriverAssignmentModel.vehicle_id == vehicle.id)
                        | (VehicleDriverAssignmentModel.driver_id == driver.id),
                    )
                )
                if (
                    busy
                    or vehicle.status == "retired"
                    or vehicle.deleted_at is not None
                    or driver.status != "active"
                    or driver.branch_id != vehicle.branch_id
                ):
                    continue
                link = VehicleDriverAssignmentModel(
                    company_id=COMPANY_ID,
                    vehicle_id=vehicle.id,
                    driver_id=driver.id,
                    starts_at=datetime.now(UTC),
                    assigned_by=actor_id,
                )
                session.add(link)
                await session.flush()
                audit(
                    "ASSIGN_DRIVER",
                    "fleet_vehicles",
                    vehicle.id,
                    branch.id,
                    {"driver_id": str(driver.id), "assignment_id": str(link.id)},
                    compliance_override=OVERRIDE_REASON,
                )
                created["assignments"] += 1

        await session.commit()
    print(
        f"Flota de Grupo Lorena lista: {len(FLEET)} sucursales; nuevos: "
        f"{created['vehicles']} vehículos, {created['drivers']} conductores, "
        f"{created['users']} usuarios y {created['assignments']} asignaciones."
    )


def main() -> None:
    asyncio.run(seed())


if __name__ == "__main__":
    main()
