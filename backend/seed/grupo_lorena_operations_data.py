"""Pure data of the Grupo Lorena operations seed, with its own consistency checks.

Everything here is invented for development: people, plates, invoices and prices.
The orchestration lives in :mod:`seed.seed_grupo_lorena_operations`; this module
has no database access so the unit tests can validate it in isolation.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal

from seed.seed_grupo_lorena import BRANCHES, DEPARTMENTS, EMPLOYEES, HEADQUARTERS
from seed.seed_grupo_lorena_fleet import (
    ALPHANUMERIC_PLATE_YEAR,
    DEFAULT_LICENSE_CLASSES,
    FLEET,
    PLATE_2011,
    PLATE_ALPHANUMERIC,
    PLATE_CLASS_BY_KIND,
    BranchFleetSeed,
    DriverSeed,
    VehicleSeed,
)

SOURCE = "seed_grupo_lorena_operations"
#: Every document of the purchase cycle carries ``Ref. GLOPS-...`` in its notes;
#: a rerun finds it by that reference and continues from its current state.
MARKER_PREFIX = "GLOPS"


def marker(key: str) -> str:
    return f"Ref. {MARKER_PREFIX}-{key}"


D = Decimal
ZERO = Decimal(0)
VAT_RATE = Decimal(13)

# --------------------------------------------------------------------------- roles

ROLES: Mapping[str, tuple[str, tuple[str, ...]]] = {
    "SOLICITANTE DE COMPRAS": (
        "Registra y envía solicitudes de compra de su sucursal.",
        (
            "purchase_requests:read",
            "purchase_requests:create",
            "products:read",
            "branches.view",
            "warehouses.view",
        ),
    ),
    "ANALISTA DE COMPRAS": (
        "Consolida demanda, solicita cotizaciones y prepara órdenes de compra.",
        (
            "purchase_requests:read",
            "purchase_requests:manage",
            "purchase_quotations:read",
            "purchase_quotations:manage",
            "purchase_orders:read",
            "purchase_orders:manage",
            "purchases:read",
            "retaceos:read",
            "suppliers:read",
            "products:read",
            "inventory:read",
            "branches.view",
            "warehouses.view",
        ),
    ),
    "JEFE DE COMPRAS": (
        "Aprueba solicitudes y órdenes, adjudica ofertas y administra proveedores.",
        (
            "purchase_requests:read",
            "purchase_requests:approve",
            "purchase_requests:manage",
            "purchase_quotations:read",
            "purchase_quotations:manage",
            "purchase_quotations:select",
            "purchase_orders:read",
            "purchase_orders:approve",
            "purchase_orders:send",
            "purchases:read",
            "retaceos:read",
            "suppliers:read",
            "suppliers:manage",
            "products:read",
            "inventory:read",
            "branches.view",
            "warehouses.view",
        ),
    ),
    "CONTABILIDAD DE COSTOS": (
        "Elabora, verifica y cierra retaceos; consulta la valoración del inventario.",
        (
            "retaceos:read",
            "retaceos:manage",
            "retaceos:calculate",
            "retaceos:verify",
            "inventory:read",
            "inventory:valuation",
            "purchases:read",
            "purchase_orders:read",
            "suppliers:read",
            "products:read",
            "branches.view",
            "warehouses.view",
        ),
    ),
    "APROBADOR DE TRASLADOS": (
        "Aprueba los traslados entre tiendas, que en Grupo Lorena requieren aprobación.",
        ("inventory:read", "inventory:transfer_approve", "branches.view", "warehouses.view"),
    ),
    "RECEPCIÓN DE BODEGA CENTRAL": (
        "Recibe compras, verifica cantidades, etiqueta y ubica la mercadería.",
        (
            "purchases:read",
            "purchases:manage",
            "purchases:receive",
            "purchases:verify",
            "purchase_orders:read",
            "inventory:read",
            "inventory:receive",
            "inventory:move",
            "inventory:warehouse_receipts",
            "locations.view",
            "locations.labels",
            "branches.view",
            "warehouses.view",
        ),
    ),
}

STORE_MANAGERS: Mapping[str, str] = {
    str(employee["branch"]): str(employee["username"])
    for employee in EMPLOYEES
    if employee.get("position") == "Gerente de Sucursal"
}
CENTRAL_MANAGER = "rigoberto.cardona"
REGIONAL_WAREHOUSE_MANAGER = "diana.campos"
#: Coordinador de Distribución. Store-to-store transfers require approval in this company
#: (central distributions do not); without this grant only the superadmin could approve them.
TRANSFER_APPROVER = "ricardo.portillo"

#: Additive role grants to accounts created by the base seed (never revoked here).
EXTRA_ROLE_GRANTS: tuple[tuple[str, str], ...] = (
    *((username, "SOLICITANTE DE COMPRAS") for username in STORE_MANAGERS.values()),
    (CENTRAL_MANAGER, "SOLICITANTE DE COMPRAS"),
    (CENTRAL_MANAGER, "RECEPCIÓN DE BODEGA CENTRAL"),
    (TRANSFER_APPROVER, "APROBADOR DE TRASLADOS"),
)

# --------------------------------------------------------------------------- staff


@dataclass(frozen=True, slots=True)
class StaffSeed:
    code: str
    first: str
    last: str
    branch: str
    department: str
    position: str
    shift: str = "mañana"
    username: str | None = None
    role: str | None = None


SHIFTS = frozenset({"mañana", "tarde", "noche"})
DRIVER_POSITION = "Repartidor"

HQ_STAFF: tuple[StaffSeed, ...] = (
    StaffSeed(
        "GL-0201",
        "Lissette Abigail",
        "Rodas Funes",
        HEADQUARTERS,
        "Compras y Abastecimiento",
        "Jefa de Compras",
        username="lissette.rodas",
        role="JEFE DE COMPRAS",
    ),
    StaffSeed(
        "GL-0202",
        "Gerardo Antonio",
        "Melara Castro",
        HEADQUARTERS,
        "Compras y Abastecimiento",
        "Analista de Compras",
        username="gerardo.melara",
        role="ANALISTA DE COMPRAS",
    ),
    StaffSeed(
        "GL-0203",
        "Sandra Elizabeth",
        "Pineda Ayala",
        HEADQUARTERS,
        "Finanzas y Contabilidad",
        "Contadora de Costos",
        username="sandra.pineda",
        role="CONTABILIDAD DE COSTOS",
    ),
    StaffSeed(
        "GL-0204",
        "Hugo Ernesto",
        "Alfaro Linares",
        HEADQUARTERS,
        "Finanzas y Contabilidad",
        "Jefe de Contabilidad",
        username="hugo.alfaro",
        role="CONTABILIDAD DE COSTOS",
    ),
)


def _store(branch: str, start: int, *people: tuple[str, str, str, str, str]) -> list[StaffSeed]:
    return [
        StaffSeed(f"GL-{start + offset:04d}", first, last, branch, department, position, shift)
        for offset, (first, last, department, position, shift) in enumerate(people)
    ]


SALES = "Servicio al Cliente"
PRODUCTION = "Producción"
LOGISTICS = "Logística y Distribución"

STORE_STAFF: tuple[StaffSeed, ...] = tuple(
    _store(
        "LOR-SM-01",
        101,
        ("Yesenia Marisol", "Ventura Chávez", SALES, "Cajera", "mañana"),
        ("Edgardo Antonio", "Rivera Lemus", PRODUCTION, "Panadero", "mañana"),
        ("Carolina Beatriz", "Mejía Urquilla", PRODUCTION, "Pastelera Decoradora", "tarde"),
        ("Walter Alexander", "Guzmán Batres", LOGISTICS, "Auxiliar de Bodega", "mañana"),
        ("Luis Alonso", "Amaya Turcios", LOGISTICS, DRIVER_POSITION, "tarde"),
    )
    + _store(
        "LOR-USU-01",
        111,
        ("Karen Lisseth", "Hernández Ramos", SALES, "Cajera", "tarde"),
        ("José Roberto", "Martínez Bonilla", PRODUCTION, "Panadero", "mañana"),
        ("Iris Yamileth", "Cruz Portillo", PRODUCTION, "Pastelera Decoradora", "mañana"),
        ("Mario Alberto", "Reyes Saravia", LOGISTICS, "Auxiliar de Bodega", "mañana"),
        ("Jonathan Ernesto", "Arévalo Molina", LOGISTICS, DRIVER_POSITION, "tarde"),
    )
    + _store(
        "LOR-JIQ-01",
        121,
        ("Glenda Maritza", "Campos Aguilar", SALES, "Cajera", "mañana"),
        ("Santos Ernesto", "Rodríguez Ortiz", PRODUCTION, "Panadero", "mañana"),
        ("Dina Elizabeth", "Lovo Henríquez", PRODUCTION, "Pastelera Decoradora", "tarde"),
        ("Bryan Alexis", "Mendoza Rivas", LOGISTICS, "Auxiliar de Bodega", "tarde"),
    )
    + _store(
        "LOR-LU-01",
        131,
        ("Ingrid Yessenia", "Márquez Zelaya", SALES, "Cajera", "mañana"),
        ("Rafael Antonio", "Sorto Romero", PRODUCTION, "Panadero", "mañana"),
        ("Ana Cecilia", "Flores Gálvez", PRODUCTION, "Pastelera Decoradora", "tarde"),
        ("Óscar Mauricio", "Umaña Villatoro", LOGISTICS, "Auxiliar de Bodega", "mañana"),
        ("Ever Josué", "Pérez Canales", LOGISTICS, DRIVER_POSITION, "tarde"),
    )
    + _store(
        "LOR-SRL-01",
        141,
        ("Marta Alicia", "Benítez Ayala", SALES, "Cajera", "tarde"),
        ("Carlos Humberto", "Díaz Majano", PRODUCTION, "Panadero", "mañana"),
        ("Rosa Elena", "Argueta Vásquez", PRODUCTION, "Pastelera Decoradora", "mañana"),
        ("Fredy Alexander", "Guevara Sánchez", LOGISTICS, "Auxiliar de Bodega", "mañana"),
    )
    + _store(
        "LOR-GOT-01",
        151,
        ("Lorena Guadalupe", "Chicas Romero", SALES, "Cajera", "mañana"),
        ("Juan Carlos", "Villalta Argueta", PRODUCTION, "Panadero", "mañana"),
        ("Sonia Marisela", "Majano Fuentes", PRODUCTION, "Pastelera Decoradora", "tarde"),
        ("Elías Benjamín", "Portillo Cruz", LOGISTICS, "Auxiliar de Bodega", "tarde"),
    )
    + _store(
        "LOR-ET-01",
        161,
        ("Evelyn Yamileth", "Torres Membreño", SALES, "Cajera", "tarde"),
        ("Nelson Enrique", "Salgado Pineda", PRODUCTION, "Panadero", "mañana"),
        ("Brenda Carolina", "Ramos Ventura", LOGISTICS, "Auxiliar de Bodega", "mañana"),
    )
)


#: Departments the seed opens in a branch before hiring into it (create-only).
def required_department_openings() -> set[tuple[str, str]]:
    return {(person.branch, person.department) for person in (*HQ_STAFF, *STORE_STAFF)}


# --------------------------------------------------------------------------- fleet

PLATE_CLASS: Mapping[str, str] = {**PLATE_CLASS_BY_KIND, "motorcycle": "M"}
LICENSE_CLASSES: Mapping[str, frozenset[str]] = {
    **DEFAULT_LICENSE_CLASSES,
    "motorcycle": frozenset({"motocicleta"}),
}
MOTORCYCLE_NOTE = "Motocicleta con caja térmica para entregas a domicilio de pedidos pequeños."
PICKUP_NOTE = "Pickup para entregas de pedidos de pastel a eventos y abastecimiento local."

#: Store delivery vehicles; the repartidor of each store drives it.
EXTRA_FLEET: tuple[BranchFleetSeed, ...] = (
    BranchFleetSeed(
        "LOR-SM-01",
        vehicles=(
            VehicleSeed(
                "VEH-SM-03",
                "M 2A4-B17",
                "motorcycle",
                "Honda",
                "XR150L",
                2025,
                "20",
                "gasoline",
                "3150.0",
                MOTORCYCLE_NOTE,
            ),
        ),
        drivers=(
            DriverSeed(
                "GL-0105",
                "Luis Alonso",
                "Amaya Turcios",
                "luis.amaya",
                "motocicleta",
                "VEH-SM-03",
            ),
        ),
        documents=True,
    ),
    BranchFleetSeed(
        "LOR-USU-01",
        vehicles=(
            VehicleSeed(
                "VEH-USU-03",
                "M 412-068",
                "motorcycle",
                "Suzuki",
                "GN125",
                2023,
                "20",
                "gasoline",
                "18420.0",
                MOTORCYCLE_NOTE,
            ),
        ),
        drivers=(
            DriverSeed(
                "GL-0115",
                "Jonathan Ernesto",
                "Arévalo Molina",
                "jonathan.arevalo",
                "motocicleta",
                "VEH-USU-03",
            ),
        ),
        documents=True,
    ),
    BranchFleetSeed(
        "LOR-LU-01",
        vehicles=(
            VehicleSeed(
                "VEH-LU-03",
                "P 318-275",
                "pickup",
                "Toyota",
                "Hilux 2.4 4x2",
                2022,
                "900",
                "diesel",
                "46830.0",
                PICKUP_NOTE,
            ),
        ),
        drivers=(
            DriverSeed(
                "GL-0135",
                "Ever Josué",
                "Pérez Canales",
                "ever.perez",
                "liviana",
                "VEH-LU-03",
            ),
        ),
        documents=True,
    ),
)


def plate_problem(vehicle: VehicleSeed, classes: Mapping[str, str] = PLATE_CLASS) -> str | None:
    """Same rules as the fleet seed, extended with the motorcycle class ``M``."""
    alphanumeric = vehicle.year >= ALPHANUMERIC_PLATE_YEAR
    match = (PLATE_ALPHANUMERIC if alphanumeric else PLATE_2011).match(vehicle.plate)
    if match is None:
        return f"{vehicle.code} ({vehicle.year}) tiene una placa con formato incorrecto"
    expected = classes.get(vehicle.kind)
    if expected is None or match["cls"] != expected:
        return f"{vehicle.code} es {vehicle.kind}: su placa debe ser clase {expected}"
    return None


# --------------------------------------------------------------------------- locations


@dataclass(frozen=True, slots=True)
class Limits:
    certified_weight: Decimal
    operational_weight: Decimal
    certified_volume: Decimal
    operational_volume: Decimal
    length: Decimal
    width: Decimal
    height: Decimal

    def payload(self) -> dict[str, str]:
        return {
            "certified_max_weight_kg": str(self.certified_weight),
            "operational_max_weight_kg": str(self.operational_weight),
            "certified_usable_volume_m3": str(self.certified_volume),
            "operational_usable_volume_m3": str(self.operational_volume),
            "usable_length_m": str(self.length),
            "usable_width_m": str(self.width),
            "usable_height_m": str(self.height),
        }


@dataclass(frozen=True, slots=True)
class LocationBlock:
    key: str
    label: str
    area: str | None
    aisles: tuple[str, ...]
    racks: tuple[str, ...]
    levels: tuple[str, ...]
    positions: tuple[str, ...]
    location_type: str
    profile: str
    limits: Limits | None = None
    group: str | None = None

    @property
    def storage_eligible(self) -> bool:
        return self.location_type not in {"receiving", "quality", "packing", "shipping"}

    @property
    def size(self) -> int:
        return len(self.aisles) * len(self.racks) * len(self.levels) * len(self.positions)

    def coordinates(self) -> list[dict[str, str]]:
        return [
            {"aisle": aisle, "rack": rack, "level": level, "position": position}
            | ({"area": self.area} if self.area else {})
            for aisle in self.aisles
            for rack in self.racks
            for level in self.levels
            for position in self.positions
        ]


@dataclass(frozen=True, slots=True)
class GroupSeed:
    code: str
    name: str
    group_type: str
    profile: str
    limits: Limits


def _r(first: int, last: int) -> tuple[str, ...]:
    return tuple(f"{number:02d}" for number in range(first, last + 1))


CENTRAL_WAREHOUSE = "BOD-CENTRAL-01"
CENTRAL_SCHEME = {
    "name": "Bodega central Z/A/R/N/P",
    "separator": "-",
    "segments": [
        {"key": "area", "label": "Zona", "prefix": "", "width": 0, "required": False},
        {"key": "aisle", "label": "Pasillo", "prefix": "A", "width": 2},
        {"key": "rack", "label": "Rack", "prefix": "R", "width": 2},
        {"key": "level", "label": "Nivel", "prefix": "N", "width": 2},
        {"key": "position", "label": "Posición", "prefix": "P", "width": 2},
    ],
}
DRY_PALLET = Limits(D("1200"), D("1000"), D("1.8"), D("1.5"), D("1.2"), D("1.0"), D("1.5"))
COLD_PALLET = Limits(D("600"), D("500"), D("0.9"), D("0.75"), D("1.2"), D("0.8"), D("0.95"))
CENTRAL_GROUPS: tuple[GroupSeed, ...] = (
    GroupSeed(
        "CAMARA-FRIA-01",
        "Cámara fría de mantequillas y coberturas (2 °C a 8 °C)",
        "cold_chamber",
        "cold",
        Limits(D("7200"), D("6000"), D("10.8"), D("9"), D("6"), D("4"), D("2.8")),
    ),
)
CENTRAL_BLOCKS: tuple[LocationBlock, ...] = (
    LocationBlock(
        "REC",
        "Andén de recepción",
        "REC",
        ("01",),
        ("01",),
        ("01",),
        _r(1, 3),
        "receiving",
        "transit",
    ),
    LocationBlock(
        "CAL",
        "Cuarentena y control de calidad",
        "CAL",
        ("01",),
        ("01",),
        ("01",),
        _r(1, 2),
        "quality",
        "transit",
    ),
    LocationBlock(
        "SEC",
        "Racks de secos",
        "SEC",
        _r(1, 3),
        _r(1, 4),
        _r(1, 3),
        _r(1, 2),
        "standard",
        "rack",
        DRY_PALLET,
    ),
    LocationBlock(
        "FRI",
        "Cámara fría",
        "FRI",
        ("01",),
        _r(1, 2),
        _r(1, 3),
        _r(1, 2),
        "standard",
        "cold",
        COLD_PALLET,
        group="CAMARA-FRIA-01",
    ),
    LocationBlock(
        "EMP",
        "Empaque y consolidación de pedidos",
        "EMP",
        ("01",),
        ("01",),
        ("01",),
        _r(1, 2),
        "packing",
        "transit",
    ),
    LocationBlock(
        "DES",
        "Andén de despacho a tiendas",
        "DES",
        ("01",),
        ("01",),
        ("01",),
        _r(1, 4),
        "shipping",
        "transit",
    ),
)
STORE_SHELF = Limits(D("400"), D("320"), D("0.8"), D("0.7"), D("1.5"), D("0.6"), D("0.9"))
STORE_COLD = Limits(D("150"), D("120"), D("0.4"), D("0.35"), D("0.9"), D("0.6"), D("0.75"))
STORE_SHELVES = LocationBlock(
    "EST",
    "Estantería de secos y empaques",
    None,
    ("01",),
    _r(1, 2),
    _r(1, 4),
    ("01",),
    "standard",
    "general_mixed",
    STORE_SHELF,
)
STORE_COLD_BLOCK = LocationBlock(
    "REF",
    "Refrigerador de mantequillas y rellenos",
    None,
    ("02",),
    ("01",),
    _r(1, 3),
    ("01",),
    "standard",
    "cold",
    STORE_COLD,
)
#: Store warehouses that only have the three base locations get this layout.
STORE_LAYOUT_THRESHOLD = 3

# --------------------------------------------------------------------------- inventory


@dataclass(frozen=True, slots=True)
class ProductSetup:
    sku: str
    #: Base unit used when the seed has to create the inventory item.
    base_unit: str
    #: Base units contained in one purchase unit.
    per_purchase_unit: Decimal
    packaging_code: str | None
    packaging_name: str | None
    packaging_type: str
    #: Measured gross weight and volume of one purchase unit.
    unit_weight_kg: Decimal
    unit_volume_m3: Decimal
    #: Purchase units per pallet and where the pallet is stored.
    pallet_units: int
    zone: str


PRODUCTS: Mapping[str, ProductSetup] = {
    setup.sku: setup
    for setup in (
        ProductSetup(
            "PRD-HAR-003",
            "KILOGRAM",
            D("1"),
            None,
            None,
            "bag",
            D("1.008"),
            D("0.0018"),
            750,
            "SEC",
        ),
        ProductSetup(
            "PRD-LAC-002",
            "UNIT",
            D("1"),
            "CJ-MANT-10KG",
            "Caja de compra de mantequilla 10 kg",
            "box",
            D("10.5"),
            D("0.03"),
            24,
            "FRI",
        ),
        ProductSetup(
            "PRD-AZU-004",
            "KILOGRAM",
            D("10"),
            "CJ-AZU-10KG",
            "Caja de azúcar glass 10 kg",
            "box",
            D("10.3"),
            D("0.03"),
            40,
            "SEC",
        ),
        ProductSetup(
            "PRD-LEV-005",
            "UNIT",
            D("2"),
            "CJ-LEV-2X500",
            "Caja de levadura 2 x 500 g",
            "box",
            D("1.08"),
            D("0.006"),
            120,
            "SEC",
        ),
        ProductSetup(
            "PRD-CHO-006",
            "KILOGRAM",
            D("5"),
            "CJ-CHO-5KG",
            "Caja de cobertura 5 kg",
            "box",
            D("5.2"),
            D("0.0075"),
            60,
            "FRI",
        ),
        ProductSetup(
            "PRD-REL-007",
            "KILOGRAM",
            D("4"),
            "CUB-REL-4KG",
            "Cubeta de relleno 4 kg",
            "container",
            D("4.3"),
            D("0.0045"),
            60,
            "SEC",
        ),
        ProductSetup(
            "PRD-MAR-008",
            "KILOGRAM",
            D("15"),
            "CJ-MAR-15KG",
            "Caja de margarina 15 kg",
            "box",
            D("15.4"),
            D("0.0216"),
            48,
            "SEC",
        ),
        ProductSetup(
            "PRD-EMP-009",
            "UNIT",
            D("25"),
            "FAR-CAJ-25",
            "Fardo de 25 cajas para pastel",
            "package",
            D("5"),
            D("0.019"),
            60,
            "SEC",
        ),
        ProductSetup(
            "PRD-EMP-010",
            "UNIT",
            D("100"),
            "CJ-BOL-100",
            "Caja de 100 bolsas",
            "box",
            D("8.3"),
            D("0.02"),
            60,
            "SEC",
        ),
        ProductSetup(
            "PRD-CAF-011",
            "KILOGRAM",
            D("1"),
            "CJ-CAF-1KG",
            "Bolsa de café 1 kg en caja",
            "box",
            D("1.05"),
            D("0.0035"),
            120,
            "SEC",
        ),
        ProductSetup(
            "PRD-JAR-012",
            "UNIT",
            D("1"),
            "CJ-JAR-1L",
            "Botella de jarabe 1 L en caja",
            "box",
            D("1.2"),
            D("0.0013"),
            120,
            "SEC",
        ),
    )
}
PALLET_TARE_KG = D("20")
ZONE_LIMITS: Mapping[str, Limits] = {"SEC": DRY_PALLET, "FRI": COLD_PALLET}


def pallet_measures(sku: str, purchase_units: Decimal) -> tuple[Decimal, Decimal]:
    """Gross weight (with pallet) and volume of a pallet holding ``purchase_units``."""
    setup = PRODUCTS[sku]
    weight = (setup.unit_weight_kg * purchase_units + PALLET_TARE_KG).quantize(D("0.001"))
    volume = (setup.unit_volume_m3 * purchase_units).quantize(D("0.0001"))
    return weight, volume


def pallets(sku: str, purchase_units: Decimal) -> list[Decimal]:
    """Split a received quantity (purchase units) into whole pallets, largest first."""
    size = D(PRODUCTS[sku].pallet_units)
    result: list[Decimal] = []
    remaining = purchase_units
    while remaining > 0:
        portion = min(size, remaining)
        result.append(portion)
        remaining -= portion
    return result


# --------------------------------------------------------------------------- suppliers

IMPORT_SUPPLIER = {
    "code": "PROV-IMP-001",
    "name": "Chocolatera del Grijalva",
    "legal_name": "Chocolatera del Grijalva, S.A. de C.V. (ficticio)",
    "country": 8,  # México
    "address": "Parque industrial, Villahermosa, Tabasco, México",
    "phone": "+52 993 000 0000",
    "default_currency_code": "USD",
    "supplier_status": "approved",
    "external_reference": "Proveedor de demostración",
}

# --------------------------------------------------------------------------- purchases


@dataclass(frozen=True, slots=True)
class RequestSeed:
    key: str
    branch: str
    requester: str
    lines: tuple[tuple[str, Decimal], ...]
    justification: str
    #: ``approved`` (default), ``submitted`` or ``draft``.
    state: str = "approved"
    required_in_days: int = 7


@dataclass(frozen=True, slots=True)
class QuoteSeed:
    supplier: str
    prices: Mapping[str, Decimal]
    payment_terms: str
    delivery_days: int
    tax_rate: Decimal = VAT_RATE
    #: False leaves the RFQ sent and waiting for the supplier.
    respond: bool = True
    notes: str = ""


@dataclass(frozen=True, slots=True)
class ExpenseSeed:
    category: str
    amount: Decimal
    reference: str
    description: str
    days_ago: int = 2


@dataclass(frozen=True, slots=True)
class RetaceoSeed:
    freight: Decimal = ZERO
    dai: Decimal = ZERO
    origin_country: str | None = None
    import_policy: str | None = None
    notes: str = "Compra local: sin DAI."


@dataclass(frozen=True, slots=True)
class ReceiptSeed:
    invoice: str
    invoice_days_ago: int
    retaceo: RetaceoSeed
    #: Quantities received per SKU when the delivery is partial.
    partial: Mapping[str, Decimal] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class OrderSeed:
    supplier: str
    #: ``pending_approval``, ``sent`` or ``received``.
    state: str
    expected_in_days: int
    planned: tuple[tuple[str, Decimal, str], ...] = ()
    actual: tuple[ExpenseSeed, ...] = ()
    receipt: ReceiptSeed | None = None


@dataclass(frozen=True, slots=True)
class ConsolidationSeed:
    key: str
    title: str
    requests: tuple[RequestSeed, ...]
    quotes: tuple[QuoteSeed, ...]
    awards: Mapping[str, str]
    orders: tuple[OrderSeed, ...]
    close: bool = True


AWARD_REASON = "Mejor costo total con plazo de entrega y condiciones de pago aceptables."

CONSOLIDATIONS: tuple[ConsolidationSeed, ...] = (
    ConsolidationSeed(
        key="A",
        title="Consolidado quincenal de secos y grasas para panificación",
        requests=(
            RequestSeed(
                "A-SM",
                "LOR-SM-01",
                "mauricio.hernandez",
                (
                    ("PRD-HAR-003", D("750")),
                    ("PRD-AZU-004", D("20")),
                    ("PRD-MAR-008", D("16")),
                    ("PRD-LAC-002", D("12")),
                    ("PRD-LEV-005", D("10")),
                ),
                "Producción de pan dulce y pasteles de la segunda quincena; existencias para 4 días.",
            ),
            RequestSeed(
                "A-USU",
                "LOR-USU-01",
                "karla.argueta",
                (
                    ("PRD-HAR-003", D("500")),
                    ("PRD-AZU-004", D("12")),
                    ("PRD-MAR-008", D("10")),
                    ("PRD-LAC-002", D("8")),
                    ("PRD-LEV-005", D("6")),
                ),
                "Reposición quincenal; aumentan los pedidos de pasteles por fin de mes.",
            ),
            RequestSeed(
                "A-JIQ",
                "LOR-JIQ-01",
                "fernando.benitez",
                (
                    ("PRD-HAR-003", D("250")),
                    ("PRD-AZU-004", D("8")),
                    ("PRD-MAR-008", D("6")),
                    ("PRD-LEV-005", D("4")),
                ),
                "Consumo normal de panadería; la harina disponible alcanza para una semana.",
            ),
            RequestSeed(
                "A-GOT",
                "LOR-GOT-01",
                "veronica.chicas",
                (
                    ("PRD-HAR-003", D("250")),
                    ("PRD-AZU-004", D("10")),
                    ("PRD-LAC-002", D("6")),
                    ("PRD-LEV-005", D("4")),
                ),
                "Reposición para producción de semita y quesadilla del fin de semana.",
            ),
            RequestSeed(
                "A-HQ",
                HEADQUARTERS,
                CENTRAL_MANAGER,
                (
                    ("PRD-HAR-003", D("750")),
                    ("PRD-MAR-008", D("16")),
                    ("PRD-LAC-002", D("10")),
                ),
                "Existencia de seguridad de la bodega central para despachos urgentes a tiendas.",
            ),
        ),
        quotes=(
            QuoteSeed(
                "PROV-001",
                {"PRD-HAR-003": D("0.74"), "PRD-LEV-005": D("9.60")},
                "30 días crédito",
                2,
            ),
            QuoteSeed(
                "PROV-003",
                {"PRD-HAR-003": D("0.78"), "PRD-AZU-004": D("12.40")},
                "Contado contra entrega",
                1,
            ),
            QuoteSeed("PROV-004", {"PRD-LEV-005": D("9.15")}, "15 días crédito", 3),
            QuoteSeed(
                "PROV-007",
                {"PRD-MAR-008": D("30.90"), "PRD-LAC-002": D("61.50")},
                "30 días crédito",
                2,
            ),
            QuoteSeed(
                "PROV-002",
                {"PRD-LAC-002": D("58.75"), "PRD-MAR-008": D("32.10")},
                "15 días crédito",
                2,
            ),
        ),
        awards={
            "PRD-HAR-003": "PROV-001",
            "PRD-AZU-004": "PROV-003",
            "PRD-LEV-005": "PROV-004",
            "PRD-MAR-008": "PROV-007",
            "PRD-LAC-002": "PROV-002",
        },
        orders=(
            OrderSeed(
                "PROV-001",
                "received",
                2,
                actual=(
                    ExpenseSeed(
                        "Manejo y descarga",
                        D("35.00"),
                        "REC-CARGA-0412",
                        "Cuadrilla para descarga de 100 sacos de harina",
                        1,
                    ),
                ),
                receipt=ReceiptSeed(
                    "CCF-HES-0018734",
                    1,
                    RetaceoSeed(notes="Compra local: entrega en bodega sin flete; sin DAI."),
                ),
            ),
            OrderSeed(
                "PROV-003",
                "received",
                1,
                receipt=ReceiptSeed(
                    "CCF-AEV-0009921",
                    1,
                    RetaceoSeed(D("22.50"), notes="Flete local San Miguel; sin DAI."),
                ),
            ),
            OrderSeed("PROV-004", "sent", 3),
            OrderSeed(
                "PROV-007",
                "received",
                2,
                receipt=ReceiptSeed("CCF-GMR-0031107", 0, RetaceoSeed()),
            ),
            OrderSeed(
                "PROV-002",
                "received",
                2,
                receipt=ReceiptSeed(
                    "CCF-DLC-0052260",
                    0,
                    RetaceoSeed(D("30.00"), notes="Flete refrigerado local; sin DAI."),
                ),
            ),
        ),
    ),
    ConsolidationSeed(
        key="B",
        title="Consolidado mensual de empaques y cafetería",
        requests=(
            RequestSeed(
                "B-LU",
                "LOR-LU-01",
                "elena.quintanilla",
                (
                    ("PRD-EMP-009", D("24")),
                    ("PRD-EMP-010", D("20")),
                    ("PRD-CAF-011", D("30")),
                    ("PRD-JAR-012", D("12")),
                ),
                "Empaques y cafetería del mes; temporada de pedidos de pastel en La Unión.",
            ),
            RequestSeed(
                "B-SRL",
                "LOR-SRL-01",
                "oscar.villatoro",
                (
                    ("PRD-EMP-009", D("20")),
                    ("PRD-EMP-010", D("16")),
                    ("PRD-CAF-011", D("24")),
                    ("PRD-JAR-012", D("8")),
                ),
                "Consumo mensual de cafetería y empaque de mostrador.",
            ),
            RequestSeed(
                "B-ET",
                "LOR-ET-01",
                "carlos.amaya",
                (
                    ("PRD-EMP-009", D("16")),
                    ("PRD-EMP-010", D("12")),
                    ("PRD-CAF-011", D("18")),
                    ("PRD-JAR-012", D("6")),
                ),
                "Reposición mensual; quedan existencias para 5 días.",
            ),
            RequestSeed(
                "B-SM",
                "LOR-SM-01",
                "mauricio.hernandez",
                (
                    ("PRD-EMP-009", D("30")),
                    ("PRD-EMP-010", D("32")),
                    ("PRD-CAF-011", D("48")),
                    ("PRD-JAR-012", D("10")),
                ),
                "Alta rotación de cafetería y pedidos para llevar en Roosevelt.",
            ),
        ),
        quotes=(
            QuoteSeed(
                "PROV-008",
                {"PRD-EMP-009": D("13.60"), "PRD-EMP-010": D("6.90")},
                "30 días crédito",
                4,
            ),
            QuoteSeed("PROV-009", {"PRD-EMP-010": D("6.35")}, "30 días crédito", 5),
            QuoteSeed("PROV-010", {"PRD-CAF-011": D("11.40")}, "15 días crédito", 2),
            QuoteSeed(
                "PROV-012",
                {"PRD-CAF-011": D("11.95"), "PRD-JAR-012": D("9.10")},
                "Contado contra entrega",
                1,
            ),
            QuoteSeed("PROV-011", {"PRD-JAR-012": D("8.70")}, "30 días crédito", 3),
        ),
        awards={
            "PRD-EMP-009": "PROV-008",
            "PRD-EMP-010": "PROV-009",
            "PRD-CAF-011": "PROV-010",
            "PRD-JAR-012": "PROV-011",
        },
        orders=(
            OrderSeed(
                "PROV-008",
                "received",
                4,
                receipt=ReceiptSeed("CCF-ECC-0007745", 1, RetaceoSeed()),
            ),
            OrderSeed(
                "PROV-009",
                "received",
                5,
                receipt=ReceiptSeed(
                    "CCF-BEB-0002318",
                    0,
                    RetaceoSeed(notes="Entrega parcial: 60 de 80 cajas; sin flete ni DAI."),
                    partial={"PRD-EMP-010": D("60")},
                ),
            ),
            OrderSeed(
                "PROV-010",
                "received",
                2,
                receipt=ReceiptSeed("CCF-CTA-0011452", 0, RetaceoSeed()),
            ),
            OrderSeed("PROV-011", "pending_approval", 3),
        ),
    ),
    ConsolidationSeed(
        key="C",
        title="Consolidado de coberturas y rellenos para temporada navideña",
        requests=(
            RequestSeed(
                "C-SM",
                "LOR-SM-01",
                "mauricio.hernandez",
                (("PRD-CHO-006", D("40")), ("PRD-REL-007", D("20"))),
                "Pasteles de chocolate y empanadas de guayaba para pedidos de diciembre.",
                required_in_days=14,
            ),
            RequestSeed(
                "C-USU",
                "LOR-USU-01",
                "karla.argueta",
                (("PRD-CHO-006", D("24")), ("PRD-REL-007", D("16"))),
                "Temporada navideña: tortas y brazos gitanos de chocolate.",
                required_in_days=14,
            ),
            RequestSeed(
                "C-HQ",
                HEADQUARTERS,
                CENTRAL_MANAGER,
                (("PRD-CHO-006", D("56")), ("PRD-REL-007", D("24"))),
                "Existencia central para cubrir las demás tiendas durante diciembre.",
                required_in_days=14,
            ),
        ),
        quotes=(
            QuoteSeed(
                "PROV-IMP-001",
                {"PRD-CHO-006": D("24.80")},
                "50 % anticipado y 50 % contra documentos de embarque",
                12,
                tax_rate=D("0"),
                notes="Precio FOB Villahermosa; el flete y el seguro se contratan aparte.",
            ),
            QuoteSeed("PROV-005", {"PRD-CHO-006": D("29.40")}, "30 días crédito", 3),
            QuoteSeed("PROV-006", {"PRD-REL-007": D("16.00")}, "15 días crédito", 2),
        ),
        awards={"PRD-CHO-006": "PROV-IMP-001", "PRD-REL-007": "PROV-006"},
        orders=(
            OrderSeed(
                "PROV-IMP-001",
                "received",
                12,
                planned=(
                    ("Agente aduanal", D("185.00"), "Trámite de póliza de importación"),
                    ("Almacenamiento", D("60.00"), "Almacenaje en aduana terrestre"),
                    ("Manejo y descarga", D("45.00"), "Descarga en bodega central"),
                ),
                actual=(
                    ExpenseSeed(
                        "Agente aduanal",
                        D("192.50"),
                        "AA-2026-11-0457",
                        "Honorarios de agente aduanal, póliza de importación",
                        4,
                    ),
                    ExpenseSeed(
                        "Almacenamiento",
                        D("64.00"),
                        "ALM-ADU-88214",
                        "Almacenaje de dos días en aduana terrestre",
                        3,
                    ),
                    ExpenseSeed(
                        "Manejo y descarga",
                        D("48.00"),
                        "REC-CARGA-0418",
                        "Descarga y estiba en cámara fría de la bodega central",
                        1,
                    ),
                ),
                receipt=ReceiptSeed(
                    "INV-CDG-2026-0871",
                    6,
                    RetaceoSeed(
                        freight=D("385.00"),
                        # 15 % sobre el valor CIF: (2,976.00 FOB + 385.00 flete y seguro).
                        dai=D("504.15"),
                        origin_country="México",
                        import_policy="4-12-2026-108733",
                        notes="Importación: DAI 15 % sobre valor CIF; IVA de importación no es costo.",
                    ),
                ),
            ),
            OrderSeed(
                "PROV-006",
                "received",
                2,
                receipt=ReceiptSeed(
                    "CCF-RFA-0004489",
                    0,
                    RetaceoSeed(D("18.00"), notes="Flete local; sin DAI."),
                ),
            ),
        ),
    ),
    ConsolidationSeed(
        key="D",
        title="Reposición extraordinaria de cafetería en Jiquilisco",
        requests=(
            RequestSeed(
                "D-JIQ",
                "LOR-JIQ-01",
                "fernando.benitez",
                (("PRD-CAF-011", D("12")), ("PRD-JAR-012", D("4"))),
                "Se agotó el café por un evento institucional atendido por la sucursal.",
                required_in_days=3,
            ),
        ),
        quotes=(
            QuoteSeed(
                "PROV-012",
                {"PRD-CAF-011": D("11.95"), "PRD-JAR-012": D("9.10")},
                "Contado contra entrega",
                1,
                respond=False,
            ),
        ),
        awards={},
        orders=(),
        close=False,
    ),
)

#: Requests that stay outside a consolidation, in earlier states.
LOOSE_REQUESTS: tuple[RequestSeed, ...] = (
    RequestSeed(
        "E-ET",
        "LOR-ET-01",
        "carlos.amaya",
        (("PRD-LEV-005", D("4")), ("PRD-AZU-004", D("6"))),
        "Reposición de levadura y azúcar glass antes del fin de semana.",
        state="submitted",
        required_in_days=5,
    ),
    RequestSeed(
        "E-GOT",
        "LOR-GOT-01",
        "veronica.chicas",
        (("PRD-EMP-009", D("10")),),
        "Cajas para pastel de la promoción de diciembre (borrador en revisión).",
        state="draft",
        required_in_days=10,
    ),
)

# --------------------------------------------------------------------------- transfers


@dataclass(frozen=True, slots=True)
class TransferSeed:
    key: str
    destination: str
    vehicle: str
    #: Base units (kg or units) of each product: whole pallets, because a labelled
    #: pallet can only be split while it is still in quarantine.
    lines: tuple[tuple[str, Decimal], ...]
    #: ``received`` (dispatched and received at the store) or ``preparation``.
    state: str
    notes: str


TRANSFERS: tuple[TransferSeed, ...] = (
    TransferSeed(
        "TRA-1",
        "BOD-SM-01",
        "VEH-HQ-03",
        (("PRD-HAR-003", D("250")), ("PRD-AZU-004", D("100"))),
        "received",
        "Reposición semanal de secos y café para Pastelería Lorena Roosevelt.",
    ),
    TransferSeed(
        "TRA-2",
        "BOD-USU-01",
        "VEH-HQ-01",
        (("PRD-LAC-002", D("12")), ("PRD-CHO-006", D("300"))),
        "preparation",
        "Mantequilla y cobertura para la producción navideña de Usulután (cadena de frío).",
    ),
)


def transfer_demand() -> dict[str, Decimal]:
    totals: dict[str, Decimal] = {}
    for transfer in TRANSFERS:
        for sku, quantity in transfer.lines:
            totals[sku] = totals.get(sku, D("0")) + quantity
    return totals


# --------------------------------------------------------------------------- checks


def demand(seed: ConsolidationSeed) -> Counter[str]:
    totals: Counter[str] = Counter()
    for request in seed.requests:
        for sku, quantity in request.lines:
            totals[sku] += quantity  # type: ignore[assignment]
    return totals


def received_quantities() -> dict[str, Decimal]:
    """Purchase units of each SKU that the receipts put into the central warehouse."""
    result: dict[str, Decimal] = {}
    for seed in CONSOLIDATIONS:
        totals = demand(seed)
        for order in seed.orders:
            if order.receipt is None:
                continue
            for sku, supplier in seed.awards.items():
                if supplier == order.supplier:
                    quantity = order.receipt.partial.get(sku, D(totals[sku]))
                    result[sku] = result.get(sku, D("0")) + quantity
    return result


def validate_operations_seed() -> None:  # noqa: C901 - one flat list of invariants
    """Fail fast if the invented data is duplicated or physically impossible."""
    from app.application.fleet.compliance import license_issue
    from app.application.rbac.catalogue import ALL_PERMISSION_CODES

    people = (*HQ_STAFF, *STORE_STAFF)
    existing_codes = {str(employee["code"]) for employee in EMPLOYEES} | {
        driver.code for item in FLEET for driver in item.drivers
    }
    codes = [person.code for person in people]
    if len(codes) != len(set(codes)) or existing_codes & set(codes):
        raise ValueError("Códigos de empleado duplicados en el seed de operaciones.")
    names = [f"{person.first} {person.last}" for person in people]
    if len(names) != len(set(names)):
        raise ValueError("Nombres de empleados duplicados en el seed de operaciones.")
    existing_users = {str(e["username"]) for e in EMPLOYEES if e.get("username")} | {
        driver.username for item in FLEET for driver in item.drivers
    }
    usernames = [p.username for p in HQ_STAFF if p.username] + [
        driver.username for item in EXTRA_FLEET for driver in item.drivers
    ]
    if len(usernames) != len(set(usernames)) or existing_users & set(usernames):
        raise ValueError("Usuarios duplicados en el seed de operaciones.")
    departments = {name for name, _parent, _description in DEPARTMENTS}
    branches = {branch.code for branch in BRANCHES} | {HEADQUARTERS}
    for person in people:
        if person.department not in departments or person.branch not in branches:
            raise ValueError(f"{person.code} tiene sucursal o departamento desconocido.")
        if person.shift not in SHIFTS:
            raise ValueError(f"{person.code} tiene un turno desconocido.")
        if person.role is not None and person.role not in ROLES:
            raise ValueError(f"{person.code} tiene un rol desconocido.")
    unknown = {code for _d, perms in ROLES.values() for code in perms} - ALL_PERMISSION_CODES
    if unknown:
        raise ValueError(f"Permisos desconocidos: {sorted(unknown)}")

    staff_by_code = {person.code: person for person in STORE_STAFF}
    vehicles = [vehicle for item in (*FLEET, *EXTRA_FLEET) for vehicle in item.vehicles]
    for label, values in (
        ("códigos de vehículo", [vehicle.code for vehicle in vehicles]),
        ("placas", [vehicle.plate for vehicle in vehicles]),
    ):
        if len(values) != len(set(values)):
            raise ValueError(f"Hay {label} duplicados.")
    for item in EXTRA_FLEET:
        kinds = {vehicle.code: vehicle.kind for vehicle in item.vehicles}
        for vehicle in item.vehicles:
            if problem := plate_problem(vehicle):
                raise ValueError(problem)
        for driver in item.drivers:
            person = staff_by_code.get(driver.code)
            if person is None or person.position != DRIVER_POSITION or person.branch != item.branch:
                raise ValueError(f"{driver.code} no es repartidor de {item.branch}.")
            if (person.first, person.last) != (driver.first, driver.last):
                raise ValueError(f"El nombre de {driver.code} no coincide con su ficha.")
            if license_issue(driver.license_class, kinds[driver.vehicle], LICENSE_CLASSES):
                raise ValueError(
                    f"La licencia de {driver.code} no permite {kinds[driver.vehicle]}."
                )
    drivers = {driver.code for item in EXTRA_FLEET for driver in item.drivers}
    if {p.code for p in STORE_STAFF if p.position == DRIVER_POSITION} != drivers:
        raise ValueError("Solo los repartidores con vehículo asignado pueden ser conductores.")

    _validate_purchases()
    _validate_capacity()
    received = received_quantities()
    for transfer in TRANSFERS:
        for sku, quantity in transfer.lines:
            sizes = {
                portion * PRODUCTS[sku].per_purchase_unit for portion in pallets(sku, received[sku])
            }
            if quantity not in sizes:
                raise ValueError(f"{transfer.key}: {sku} debe trasladarse en palés completos.")
    for sku, quantity in transfer_demand().items():
        if quantity > received.get(sku, D("0")) * PRODUCTS[sku].per_purchase_unit:
            raise ValueError(f"Los traslados piden más {sku} del que se recibió.")


def _validate_purchases() -> None:  # noqa: C901 - flat list of invariants
    keys = [r.key for s in CONSOLIDATIONS for r in s.requests] + [r.key for r in LOOSE_REQUESTS]
    if len(keys) != len(set(keys)):
        raise ValueError("Claves de solicitud duplicadas.")
    managers = {**STORE_MANAGERS, HEADQUARTERS: CENTRAL_MANAGER}
    for seed in CONSOLIDATIONS:
        for request in (*seed.requests, *LOOSE_REQUESTS):
            if managers.get(request.branch) != request.requester:
                raise ValueError(f"{request.key}: el solicitante no dirige {request.branch}.")
            skus = [sku for sku, _quantity in request.lines]
            if len(skus) != len(set(skus)) or set(skus) - set(PRODUCTS):
                raise ValueError(f"{request.key}: productos repetidos o desconocidos.")
        totals = demand(seed)
        quoted = {(quote.supplier, sku) for quote in seed.quotes for sku in quote.prices}
        for sku, supplier in seed.awards.items():
            if (supplier, sku) not in quoted:
                raise ValueError(f"{seed.key}: {supplier} no cotizó {sku}.")
        if seed.close and set(seed.awards) != set(totals):
            raise ValueError(f"{seed.key}: un consolidado cerrado debe adjudicar toda su demanda.")
        if {order.supplier for order in seed.orders} - set(seed.awards.values()):
            raise ValueError(f"{seed.key}: hay órdenes para proveedores sin adjudicación.")
        for order in seed.orders:
            if (order.receipt is not None) != (order.state == "received"):
                raise ValueError(f"{seed.key}: solo las órdenes recibidas llevan recepción.")
            for sku, quantity in (order.receipt.partial if order.receipt else {}).items():
                if seed.awards.get(sku) != order.supplier or not 0 < quantity < totals[sku]:
                    raise ValueError(f"{seed.key}: recepción parcial incoherente de {sku}.")


def _validate_capacity() -> None:
    zone_positions = {block.key: block.size for block in CENTRAL_BLOCKS}
    used: Counter[str] = Counter()
    for sku, quantity in received_quantities().items():
        setup = PRODUCTS[sku]
        limits = ZONE_LIMITS[setup.zone]
        for portion in pallets(sku, quantity):
            weight, volume = pallet_measures(sku, portion)
            if weight > limits.operational_weight or volume > limits.operational_volume:
                raise ValueError(f"Un palé de {sku} excede la capacidad de {setup.zone}.")
            used[setup.zone] += 1
    for zone, count in used.items():
        if count > zone_positions[zone]:
            raise ValueError(f"La zona {zone} no tiene posiciones para {count} palés.")
    for group in CENTRAL_GROUPS:
        members = [block for block in CENTRAL_BLOCKS if block.group == group.code]
        for metric in ("operational_weight", "operational_volume"):
            total = sum(
                (getattr(block.limits, metric) * block.size for block in members if block.limits),
                D("0"),
            )
            if total > getattr(group.limits, metric):
                raise ValueError(f"Las posiciones de {group.code} exceden su capacidad.")
