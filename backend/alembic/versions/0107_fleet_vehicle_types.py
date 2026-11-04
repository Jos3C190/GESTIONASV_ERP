"""Vehicle types managed by each company, unplated units and tractor/trailer couplings.

Revision ID: 0107
Revises: 0106
"""

from alembic import op
from sqlalchemy import text

revision = "0107"
down_revision = "0106"
branch_labels = None
depends_on = None

_PERMISSION = "fleet:manage_types"
_ORIGINAL_KINDS = (
    "refrigerated",
    "cargo_van",
    "dry_box",
    "pickup",
    "flatbed",
    "compact_van",
    "curtain_side",
    "semi_trailer",
    "tanker",
)

_LIGHT = "{liviana,pesada,pesada_t}"
_LIGHT_OR_CAR = "{particular,liviana,pesada,pesada_t}"
_HEAVY = "{pesada,pesada_t}"
_ARTICULATED = "{pesada_t}"
_NONE = "{}"

# code, name, plural, licenses, image, plate, capacity, meter, fuel, can_tow, towable
_TYPES = (
    ("refrigerated", "Refrigerado", "Refrigerados", _HEAVY, "refrigerated", 1, 1, "km", 1, 0, 0),
    ("cargo_van", "Furgón", "Furgones", _LIGHT, "cargo_van", 1, 1, "km", 1, 0, 0),
    ("dry_box", "Carga seca", "Carga seca", _HEAVY, "dry_box", 1, 1, "km", 1, 0, 0),
    ("pickup", "Pickup", "Pickups", _LIGHT_OR_CAR, "pickup", 1, 1, "km", 1, 0, 0),
    ("flatbed", "Plataforma", "Plataformas", _HEAVY, "flatbed", 1, 1, "km", 1, 0, 0),
    (
        "compact_van",
        "Panel compacto",
        "Paneles compactos",
        _LIGHT,
        "compact_van",
        1,
        1,
        "km",
        1,
        0,
        0,
    ),
    (
        "curtain_side",
        "Con lona",
        "Camiones con lona",
        _HEAVY,
        "curtain_side",
        1,
        1,
        "km",
        1,
        0,
        0,
    ),
    (
        "semi_trailer",
        "Tráiler",
        "Tráileres",
        _ARTICULATED,
        "semi_trailer",
        1,
        1,
        "km",
        1,
        0,
        0,
    ),
    ("tanker", "Cisterna", "Cisternas", _ARTICULATED, "tanker", 1, 1, "km", 1, 0, 0),
    ("motorcycle", "Motocicleta", "Motocicletas", "{motocicleta}", None, 1, 0, "km", 1, 0, 0),
    ("microbus", "Microbús", "Microbuses", _HEAVY, None, 1, 0, "km", 1, 0, 0),
    ("dump_truck", "Camión de volteo", "Camiones de volteo", _HEAVY, None, 1, 1, "km", 1, 0, 0),
    ("tractor", "Cabezal", "Cabezales", _ARTICULATED, None, 1, 0, "km", 1, 1, 0),
    ("trailer", "Remolque", "Remolques", _NONE, None, 1, 1, "km", 0, 0, 1),
    ("forklift", "Montacargas", "Montacargas", _NONE, None, 0, 0, "hours", 1, 0, 0),
)


def _sql(value: object) -> str:
    return "NULL" if value is None else "'" + str(value).replace("'", "''") + "'"


def _values() -> str:
    rows = []
    for position, item in enumerate(_TYPES):
        code, name, plural, licenses, image, plate, capacity, meter, fuel, tows, towable = item
        rows.append(
            f"({_sql(code)}, {_sql(name)}, {_sql(plural)}, {_sql(licenses)}::text[], "
            f"{_sql(image)}, {bool(plate)}, {bool(capacity)}, {_sql(meter)}, {bool(fuel)}, "
            f"{bool(tows)}, {bool(towable)}, {position})"
        )
    return ",\n            ".join(rows)


def upgrade() -> None:
    op.execute("""
        CREATE TABLE fleet_vehicle_types (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          company_id uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
          code varchar(24) NOT NULL,
          name varchar(60) NOT NULL,
          plural varchar(60) NOT NULL,
          license_classes text[] NOT NULL DEFAULT '{}',
          base_image varchar(24),
          requires_plate boolean NOT NULL DEFAULT true,
          requires_capacity boolean NOT NULL DEFAULT true,
          meter_unit varchar(8) NOT NULL DEFAULT 'km',
          fuel_applicable boolean NOT NULL DEFAULT true,
          can_tow boolean NOT NULL DEFAULT false,
          is_towable boolean NOT NULL DEFAULT false,
          is_system boolean NOT NULL DEFAULT false,
          is_active boolean NOT NULL DEFAULT true,
          sort_order integer NOT NULL DEFAULT 100,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT uq_fleet_vehicle_types_company_code UNIQUE (company_id, code),
          CONSTRAINT ck_fleet_vehicle_types_meter CHECK (meter_unit IN ('km', 'hours')),
          CONSTRAINT ck_fleet_vehicle_types_tow CHECK (NOT (can_tow AND is_towable))
        )
    """)
    op.execute("""
        CREATE UNIQUE INDEX uq_fleet_vehicle_types_company_name
        ON fleet_vehicle_types (company_id, lower(name))
    """)
    op.execute(f"""
        CREATE FUNCTION seed_fleet_vehicle_types(target uuid) RETURNS void AS $$
        BEGIN
          INSERT INTO fleet_vehicle_types (
            company_id, code, name, plural, license_classes, base_image, requires_plate,
            requires_capacity, meter_unit, fuel_applicable, can_tow, is_towable, is_system,
            sort_order
          )
          SELECT target, v.code, v.name, v.plural, v.licenses, v.image, v.plate, v.capacity,
                 v.meter, v.fuel, v.tows, v.towable, true, v.position
          FROM (VALUES
            {_values()}
          ) AS v(code, name, plural, licenses, image, plate, capacity, meter, fuel, tows,
                 towable, position)
          ON CONFLICT (company_id, code) DO NOTHING;
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("SELECT seed_fleet_vehicle_types(id) FROM companies")
    op.execute("""
        CREATE FUNCTION seed_fleet_vehicle_types_for_company() RETURNS trigger AS $$
        BEGIN
          PERFORM seed_fleet_vehicle_types(NEW.id);
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER trg_companies_seed_fleet_vehicle_types
        AFTER INSERT ON companies FOR EACH ROW
        EXECUTE FUNCTION seed_fleet_vehicle_types_for_company()
    """)

    op.execute("ALTER TABLE fleet_vehicles DROP CONSTRAINT ck_fleet_vehicles_kind")
    op.execute("""
        ALTER TABLE fleet_vehicles
        ADD CONSTRAINT fk_fleet_vehicles_kind_company
        FOREIGN KEY (company_id, kind)
        REFERENCES fleet_vehicle_types (company_id, code) ON DELETE RESTRICT
    """)
    op.execute("ALTER TABLE fleet_vehicles ALTER COLUMN plate DROP NOT NULL")
    op.execute("ALTER TABLE fleet_vehicles ALTER COLUMN capacity_kg DROP NOT NULL")
    op.execute("ALTER TABLE fleet_vehicles DROP CONSTRAINT ck_fleet_vehicles_fuel_type")
    op.execute("""
        ALTER TABLE fleet_vehicles ADD CONSTRAINT ck_fleet_vehicles_fuel_type
        CHECK (fuel_type IN ('diesel', 'gasoline', 'lpg', 'electric', 'hybrid', 'none'))
    """)

    op.execute("""
        CREATE TABLE fleet_vehicle_couplings (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          company_id uuid NOT NULL REFERENCES companies(id) ON DELETE RESTRICT,
          tractor_id uuid NOT NULL,
          trailer_id uuid NOT NULL,
          started_at timestamptz NOT NULL DEFAULT now(),
          ended_at timestamptz,
          created_by uuid REFERENCES users(id) ON DELETE SET NULL,
          ended_by uuid REFERENCES users(id) ON DELETE SET NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT fk_fleet_couplings_tractor FOREIGN KEY (company_id, tractor_id)
            REFERENCES fleet_vehicles (company_id, id) ON DELETE RESTRICT,
          CONSTRAINT fk_fleet_couplings_trailer FOREIGN KEY (company_id, trailer_id)
            REFERENCES fleet_vehicles (company_id, id) ON DELETE RESTRICT,
          CONSTRAINT ck_fleet_couplings_distinct CHECK (tractor_id <> trailer_id)
        )
    """)
    op.execute("""
        CREATE UNIQUE INDEX uq_fleet_couplings_open_tractor
        ON fleet_vehicle_couplings (tractor_id) WHERE ended_at IS NULL
    """)
    op.execute("""
        CREATE UNIQUE INDEX uq_fleet_couplings_open_trailer
        ON fleet_vehicle_couplings (trailer_id) WHERE ended_at IS NULL
    """)

    op.execute(f"""
        INSERT INTO permissions (id, code, description, module, created_at)
        VALUES (gen_random_uuid(), '{_PERMISSION}',
                'Administrar los tipos de vehículo de la empresa', 'fleet', now())
        ON CONFLICT DO NOTHING
    """)
    op.execute(f"""
        INSERT INTO role_permissions (role_id, permission_id, created_at)
        SELECT r.id, p.id, now() FROM roles r CROSS JOIN permissions p
        WHERE p.code = '{_PERMISSION}' AND p.deleted_at IS NULL AND r.deleted_at IS NULL
          AND r.name IN ('SUPER_ADMIN', 'ADMINISTRADOR DE OPERACIONES')
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    bind = op.get_bind()
    original = ", ".join(f"'{kind}'" for kind in _ORIGINAL_KINDS)
    blocked = bind.execute(
        text(f"""
            SELECT count(*) FROM fleet_vehicles
            WHERE kind NOT IN ({original}) OR plate IS NULL OR capacity_kg IS NULL
               OR fuel_type = 'none'
        """)
    ).scalar()
    if blocked:
        raise RuntimeError(
            f"Hay {blocked} vehículos que solo existen con tipos de vehículo administrables."
        )
    op.execute(f"""
        DELETE FROM role_permissions WHERE permission_id IN
          (SELECT id FROM permissions WHERE code = '{_PERMISSION}');
        DELETE FROM permissions WHERE code = '{_PERMISSION}';
    """)
    op.execute("DROP TABLE fleet_vehicle_couplings")
    op.execute("ALTER TABLE fleet_vehicles DROP CONSTRAINT ck_fleet_vehicles_fuel_type")
    op.execute("""
        ALTER TABLE fleet_vehicles ADD CONSTRAINT ck_fleet_vehicles_fuel_type
        CHECK (fuel_type IN ('diesel', 'gasoline', 'lpg', 'electric', 'hybrid'))
    """)
    op.execute("ALTER TABLE fleet_vehicles ALTER COLUMN capacity_kg SET NOT NULL")
    op.execute("ALTER TABLE fleet_vehicles ALTER COLUMN plate SET NOT NULL")
    op.execute("ALTER TABLE fleet_vehicles DROP CONSTRAINT fk_fleet_vehicles_kind_company")
    op.execute(f"""
        ALTER TABLE fleet_vehicles ADD CONSTRAINT ck_fleet_vehicles_kind
        CHECK (kind IN ({original}))
    """)
    op.execute("DROP TRIGGER trg_companies_seed_fleet_vehicle_types ON companies")
    op.execute("DROP FUNCTION seed_fleet_vehicle_types_for_company()")
    op.execute("DROP FUNCTION seed_fleet_vehicle_types(uuid)")
    op.execute("DROP TABLE fleet_vehicle_types")
