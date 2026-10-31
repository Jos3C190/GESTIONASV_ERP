"""Fleet vehicles, drivers, maintenance, fuel and fleet documents."""

from alembic import op

revision = "0098_fleet"
down_revision = "0097"
branch_labels = None
depends_on = None

_FLEET_PERMISSIONS = (
    ("fleet:read", "Consultar la flota", "fleet"),
    ("fleet:create", "Registrar vehículos", "fleet"),
    ("fleet:update", "Editar vehículos y su estado", "fleet"),
    ("fleet:delete", "Enviar vehículos a la papelera", "fleet"),
    ("fleet:restore", "Restaurar vehículos", "fleet"),
    ("fleet:manage_all", "Gestionar la flota de todas las sucursales desde casa matriz", "fleet"),
    ("fleet:maintenance", "Gestionar mantenimiento y odómetro", "fleet"),
    ("fleet:fuel", "Registrar cargas de combustible", "fleet"),
    ("fleet:gps", "Vincular dispositivos GPS a vehículos", "fleet"),
    (
        "fleet:compliance_override",
        "Autorizar despachos con documentos o licencias no vigentes",
        "fleet",
    ),
    ("fleet_documents:read", "Consultar documentos de vehículos", "fleet"),
    ("fleet_documents:upload", "Cargar documentos de vehículos", "fleet"),
    ("fleet_documents:update", "Editar documentos de vehículos", "fleet"),
    ("fleet_documents:download", "Descargar documentos de vehículos", "fleet"),
    ("drivers:read", "Consultar conductores", "drivers"),
    ("drivers:create", "Registrar conductores", "drivers"),
    ("drivers:update", "Editar y suspender conductores", "drivers"),
    ("drivers:delete", "Enviar conductores a la papelera", "drivers"),
    ("drivers:restore", "Restaurar conductores", "drivers"),
    ("drivers:assign", "Asignar conductores a vehículos", "drivers"),
    ("drivers:documents", "Gestionar licencias de conducir", "drivers"),
    ("tracking:read", "Consultar el seguimiento GPS", "tracking"),
    ("tracking:geofences", "Crear y eliminar geocercas del seguimiento GPS", "tracking"),
)

# Roles de negocio creados por el seed; si no existen en una base, no se toca nada.
_ROLE_GRANTS = {
    "ADMINISTRADOR DE OPERACIONES": tuple(code for code, _, _ in _FLEET_PERMISSIONS),
    "GERENTE DE SUCURSAL": (
        "fleet:read",
        "fleet:create",
        "fleet:update",
        "fleet:maintenance",
        "fleet:fuel",
        "fleet_documents:read",
        "fleet_documents:upload",
        "fleet_documents:update",
        "fleet_documents:download",
        "drivers:read",
        "drivers:create",
        "drivers:update",
        "drivers:assign",
        "drivers:documents",
        "tracking:read",
    ),
    "AUDITOR INTERNO": ("fleet:read", "fleet_documents:read", "drivers:read", "tracking:read"),
    "JEFE DE ALMACÉN": ("fleet:read", "drivers:read", "tracking:read"),
}

_FLEET_CATEGORIES = (
    ("circulation_card", "Tarjeta de circulación", "Documentos legales", True, True),
    ("insurance_policy", "Póliza de seguro", "Documentos legales", True, True),
    ("technical_inspection", "Revisión técnica", "Documentos legales", True, True),
    ("transport_permit", "Permiso de transporte", "Documentos legales", True, False),
    ("purchase_invoice", "Factura de compra", "Adquisición", False, False),
    ("fuel_receipt", "Comprobante de combustible", "Operación", False, False),
    ("maintenance_invoice", "Factura de mantenimiento", "Operación", False, False),
    ("accident_report", "Reporte de accidente", "Operación", False, False),
    ("other", "Otros", "General", False, False),
)


def _quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def upgrade() -> None:
    op.execute(
        "ALTER TABLE employees ADD CONSTRAINT uq_employees_company_id UNIQUE (company_id, id)"
    )

    op.execute("""
        CREATE TABLE fleet_vehicles (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          company_id uuid NOT NULL REFERENCES companies(id) ON DELETE RESTRICT,
          branch_id uuid NOT NULL,
          code varchar(32) NOT NULL,
          plate varchar(16) NOT NULL,
          vin varchar(32),
          kind varchar(24) NOT NULL,
          brand varchar(60) NOT NULL,
          model varchar(80) NOT NULL,
          year integer NOT NULL,
          color varchar(40),
          capacity_kg numeric(10,2) NOT NULL,
          fuel_type varchar(16) NOT NULL DEFAULT 'diesel',
          odometer_km numeric(12,1) NOT NULL DEFAULT 0,
          status varchar(16) NOT NULL DEFAULT 'active',
          gps_device_unique_id varchar(64),
          traccar_device_id integer,
          inventory_vehicle_id uuid,
          notes text,
          created_by uuid REFERENCES users(id) ON DELETE SET NULL,
          updated_by uuid REFERENCES users(id) ON DELETE SET NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          deleted_at timestamptz,
          deleted_by uuid REFERENCES users(id) ON DELETE SET NULL,
          deletion_reason text,
          CONSTRAINT uq_fleet_vehicles_company_id UNIQUE (company_id, id),
          CONSTRAINT fk_fleet_vehicles_branch_company FOREIGN KEY (branch_id, company_id)
            REFERENCES branches(id, company_id) ON DELETE RESTRICT,
          CONSTRAINT fk_fleet_vehicles_inventory_vehicle_company
            FOREIGN KEY (company_id, inventory_vehicle_id)
            REFERENCES inventory_vehicles(company_id, id) ON DELETE RESTRICT,
          CONSTRAINT ck_fleet_vehicles_kind CHECK (kind IN ('refrigerated','cargo_van','dry_box',
            'pickup','flatbed','compact_van','curtain_side','semi_trailer','tanker')),
          CONSTRAINT ck_fleet_vehicles_status
            CHECK (status IN ('active','maintenance','out_of_service','retired')),
          CONSTRAINT ck_fleet_vehicles_fuel_type
            CHECK (fuel_type IN ('diesel','gasoline','lpg','electric','hybrid')),
          CONSTRAINT ck_fleet_vehicles_year CHECK (year BETWEEN 1950 AND 2100),
          CONSTRAINT ck_fleet_vehicles_capacity CHECK (capacity_kg > 0),
          CONSTRAINT ck_fleet_vehicles_odometer CHECK (odometer_km >= 0),
          CONSTRAINT ck_fleet_vehicles_gps_pair
            CHECK ((gps_device_unique_id IS NULL) = (traccar_device_id IS NULL))
        );
        COMMENT ON TABLE fleet_vehicles IS 'Fleet vehicles with a single home branch.';
        CREATE INDEX ix_fleet_vehicles_deleted_at ON fleet_vehicles (deleted_at);
        CREATE UNIQUE INDEX uq_fleet_vehicles_company_code_visible
          ON fleet_vehicles (company_id, lower(code)) WHERE deleted_at IS NULL;
        CREATE UNIQUE INDEX uq_fleet_vehicles_company_plate_visible
          ON fleet_vehicles (company_id, upper(plate)) WHERE deleted_at IS NULL;
        CREATE UNIQUE INDEX uq_fleet_vehicles_company_vin_visible
          ON fleet_vehicles (company_id, upper(vin)) WHERE vin IS NOT NULL AND deleted_at IS NULL;
        CREATE UNIQUE INDEX uq_fleet_vehicles_gps_device_visible ON fleet_vehicles
          (gps_device_unique_id) WHERE gps_device_unique_id IS NOT NULL AND deleted_at IS NULL;
        CREATE UNIQUE INDEX uq_fleet_vehicles_inventory_vehicle
          ON fleet_vehicles (inventory_vehicle_id) WHERE inventory_vehicle_id IS NOT NULL;
        CREATE INDEX ix_fleet_vehicles_company_branch_status
          ON fleet_vehicles (company_id, branch_id, status);

        CREATE TABLE fleet_vehicle_photos (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          company_id uuid NOT NULL REFERENCES companies(id) ON DELETE RESTRICT,
          vehicle_id uuid NOT NULL,
          url varchar(2048) NOT NULL,
          public_id varchar(512) NOT NULL,
          caption varchar(200),
          position integer NOT NULL DEFAULT 0,
          uploaded_by uuid REFERENCES users(id) ON DELETE SET NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT fk_fleet_vehicle_photos_vehicle_company FOREIGN KEY (company_id, vehicle_id)
            REFERENCES fleet_vehicles(company_id, id) ON DELETE CASCADE
        );
        CREATE INDEX ix_fleet_vehicle_photos_vehicle ON fleet_vehicle_photos (vehicle_id, position);

        CREATE TABLE drivers (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          company_id uuid NOT NULL REFERENCES companies(id) ON DELETE RESTRICT,
          employee_id uuid NOT NULL,
          branch_id uuid NOT NULL,
          license_class varchar(16) NOT NULL,
          status varchar(16) NOT NULL DEFAULT 'active',
          status_reason text,
          notes text,
          created_by uuid REFERENCES users(id) ON DELETE SET NULL,
          updated_by uuid REFERENCES users(id) ON DELETE SET NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          deleted_at timestamptz,
          deleted_by uuid REFERENCES users(id) ON DELETE SET NULL,
          deletion_reason text,
          CONSTRAINT uq_drivers_company_id UNIQUE (company_id, id),
          CONSTRAINT fk_drivers_employee_company FOREIGN KEY (company_id, employee_id)
            REFERENCES employees(company_id, id) ON DELETE RESTRICT,
          CONSTRAINT fk_drivers_branch_company FOREIGN KEY (branch_id, company_id)
            REFERENCES branches(id, company_id) ON DELETE RESTRICT,
          CONSTRAINT ck_drivers_license_class
            CHECK (license_class IN ('particular','liviana','pesada','pesada_t','motocicleta')),
          CONSTRAINT ck_drivers_status CHECK (status IN ('active','suspended','inactive'))
        );
        COMMENT ON TABLE drivers IS
          'Driver profiles; every driver is an employee of the same company.';
        CREATE INDEX ix_drivers_deleted_at ON drivers (deleted_at);
        CREATE UNIQUE INDEX uq_drivers_company_employee_visible
          ON drivers (company_id, employee_id) WHERE deleted_at IS NULL;
        CREATE INDEX ix_drivers_company_branch_status ON drivers (company_id, branch_id, status);

        CREATE TABLE vehicle_driver_assignments (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          company_id uuid NOT NULL REFERENCES companies(id) ON DELETE RESTRICT,
          vehicle_id uuid NOT NULL,
          driver_id uuid NOT NULL,
          starts_at timestamptz NOT NULL DEFAULT now(),
          ends_at timestamptz,
          assigned_by uuid REFERENCES users(id) ON DELETE SET NULL,
          ended_by uuid REFERENCES users(id) ON DELETE SET NULL,
          end_reason text,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT fk_vehicle_driver_assignments_vehicle_company
            FOREIGN KEY (company_id, vehicle_id)
            REFERENCES fleet_vehicles(company_id, id) ON DELETE RESTRICT,
          CONSTRAINT fk_vehicle_driver_assignments_driver_company
            FOREIGN KEY (company_id, driver_id)
            REFERENCES drivers(company_id, id) ON DELETE RESTRICT,
          CONSTRAINT ck_vehicle_driver_assignments_dates
            CHECK (ends_at IS NULL OR ends_at >= starts_at)
        );
        CREATE UNIQUE INDEX uq_vehicle_driver_assignments_open_vehicle
          ON vehicle_driver_assignments (vehicle_id) WHERE ends_at IS NULL;
        CREATE UNIQUE INDEX uq_vehicle_driver_assignments_open_driver
          ON vehicle_driver_assignments (driver_id) WHERE ends_at IS NULL;
        CREATE INDEX ix_vehicle_driver_assignments_driver
          ON vehicle_driver_assignments (driver_id, starts_at);

        CREATE TABLE fleet_odometer_readings (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          company_id uuid NOT NULL REFERENCES companies(id) ON DELETE RESTRICT,
          vehicle_id uuid NOT NULL,
          reading_km numeric(12,1) NOT NULL,
          read_at timestamptz NOT NULL,
          source varchar(16) NOT NULL,
          notes text,
          recorded_by uuid REFERENCES users(id) ON DELETE SET NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT fk_fleet_odometer_readings_vehicle_company
            FOREIGN KEY (company_id, vehicle_id)
            REFERENCES fleet_vehicles(company_id, id) ON DELETE CASCADE,
          CONSTRAINT ck_fleet_odometer_readings_positive CHECK (reading_km >= 0),
          CONSTRAINT ck_fleet_odometer_readings_source
            CHECK (source IN ('manual','fuel','maintenance','gps'))
        );
        CREATE INDEX ix_fleet_odometer_readings_vehicle_time
          ON fleet_odometer_readings (vehicle_id, read_at);

        CREATE TABLE fleet_maintenance_plans (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          company_id uuid NOT NULL REFERENCES companies(id) ON DELETE RESTRICT,
          vehicle_id uuid NOT NULL,
          name varchar(120) NOT NULL,
          interval_km integer,
          interval_days integer,
          last_service_km numeric(12,1),
          last_service_on date,
          is_active boolean NOT NULL DEFAULT true,
          created_by uuid REFERENCES users(id) ON DELETE SET NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT uq_fleet_maintenance_plans_company_id UNIQUE (company_id, id),
          CONSTRAINT fk_fleet_maintenance_plans_vehicle_company
            FOREIGN KEY (company_id, vehicle_id)
            REFERENCES fleet_vehicles(company_id, id) ON DELETE CASCADE,
          CONSTRAINT ck_fleet_maintenance_plans_interval
            CHECK (interval_km IS NOT NULL OR interval_days IS NOT NULL),
          CONSTRAINT ck_fleet_maintenance_plans_positive
            CHECK ((interval_km IS NULL OR interval_km > 0)
              AND (interval_days IS NULL OR interval_days > 0))
        );
        CREATE UNIQUE INDEX uq_fleet_maintenance_plans_vehicle_name
          ON fleet_maintenance_plans (vehicle_id, lower(name)) WHERE is_active IS TRUE;

        CREATE TABLE fleet_maintenance_orders (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          company_id uuid NOT NULL REFERENCES companies(id) ON DELETE RESTRICT,
          vehicle_id uuid NOT NULL,
          plan_id uuid,
          kind varchar(16) NOT NULL,
          status varchar(16) NOT NULL DEFAULT 'scheduled',
          title varchar(160) NOT NULL,
          description text,
          workshop varchar(160),
          scheduled_on date,
          started_at timestamptz,
          completed_at timestamptz,
          odometer_km numeric(12,1),
          cost numeric(12,2),
          cancel_reason text,
          created_by uuid REFERENCES users(id) ON DELETE SET NULL,
          closed_by uuid REFERENCES users(id) ON DELETE SET NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT fk_fleet_maintenance_orders_vehicle_company
            FOREIGN KEY (company_id, vehicle_id)
            REFERENCES fleet_vehicles(company_id, id) ON DELETE RESTRICT,
          CONSTRAINT fk_fleet_maintenance_orders_plan_company FOREIGN KEY (company_id, plan_id)
            REFERENCES fleet_maintenance_plans(company_id, id) ON DELETE RESTRICT,
          CONSTRAINT ck_fleet_maintenance_orders_kind CHECK (kind IN ('preventive','corrective')),
          CONSTRAINT ck_fleet_maintenance_orders_status
            CHECK (status IN ('scheduled','in_progress','completed','cancelled')),
          CONSTRAINT ck_fleet_maintenance_orders_cost CHECK (cost IS NULL OR cost >= 0),
          CONSTRAINT ck_fleet_maintenance_orders_completion CHECK (status <> 'completed'
            OR (completed_at IS NOT NULL AND odometer_km IS NOT NULL))
        );
        CREATE INDEX ix_fleet_maintenance_orders_vehicle_status
          ON fleet_maintenance_orders (vehicle_id, status);

        CREATE TABLE fleet_fuel_logs (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          company_id uuid NOT NULL REFERENCES companies(id) ON DELETE RESTRICT,
          vehicle_id uuid NOT NULL,
          driver_id uuid,
          filled_at timestamptz NOT NULL,
          liters numeric(10,3) NOT NULL,
          total_amount numeric(12,2) NOT NULL,
          odometer_km numeric(12,1) NOT NULL,
          full_tank boolean NOT NULL DEFAULT true,
          station varchar(160),
          receipt_document_id uuid REFERENCES document_records(id) ON DELETE SET NULL,
          recorded_by uuid REFERENCES users(id) ON DELETE SET NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT fk_fleet_fuel_logs_vehicle_company FOREIGN KEY (company_id, vehicle_id)
            REFERENCES fleet_vehicles(company_id, id) ON DELETE RESTRICT,
          CONSTRAINT fk_fleet_fuel_logs_driver_company FOREIGN KEY (company_id, driver_id)
            REFERENCES drivers(company_id, id) ON DELETE RESTRICT,
          CONSTRAINT ck_fleet_fuel_logs_liters CHECK (liters > 0),
          CONSTRAINT ck_fleet_fuel_logs_amount CHECK (total_amount >= 0),
          CONSTRAINT ck_fleet_fuel_logs_odometer CHECK (odometer_km >= 0)
        );
        CREATE INDEX ix_fleet_fuel_logs_vehicle_time ON fleet_fuel_logs (vehicle_id, filled_at);

        ALTER TABLE inventory_transfers
          ADD COLUMN driver_id uuid,
          ADD COLUMN compliance_override_by uuid REFERENCES users(id) ON DELETE SET NULL,
          ADD COLUMN compliance_override_reason text,
          ADD CONSTRAINT fk_inventory_transfers_driver_company FOREIGN KEY (company_id, driver_id)
            REFERENCES drivers(company_id, id) ON DELETE RESTRICT,
          ADD CONSTRAINT ck_inventory_transfers_compliance_override
            CHECK ((compliance_override_by IS NULL) = (compliance_override_reason IS NULL));
    """)

    # Documentos: nuevo módulo de flota y reglas de vencimiento/obligatoriedad por categoría.
    op.execute("""
        ALTER TABLE document_categories
          ADD COLUMN requires_expiry boolean NOT NULL DEFAULT false,
          ADD COLUMN compliance_required boolean NOT NULL DEFAULT false,
          ADD CONSTRAINT ck_document_categories_compliance_expiry
            CHECK (requires_expiry OR NOT compliance_required);
        ALTER TABLE document_categories DROP CONSTRAINT ck_document_categories_module;
        ALTER TABLE document_categories ADD CONSTRAINT ck_document_categories_module
          CHECK (module IN ('general','employees','fleet'));
        ALTER TABLE document_records DROP CONSTRAINT ck_document_records_module;
        ALTER TABLE document_records ADD CONSTRAINT ck_document_records_module
          CHECK (module IN ('general','employees','fleet'));
        ALTER TABLE document_records DROP CONSTRAINT ck_document_records_owner;
        ALTER TABLE document_records ADD CONSTRAINT ck_document_records_owner CHECK (
          (module = 'general' AND owner_type IS NULL AND owner_id IS NULL)
          OR (module = 'employees' AND owner_type = 'employee' AND owner_id IS NOT NULL)
          OR (module = 'fleet' AND owner_type = 'vehicle' AND owner_id IS NOT NULL));
    """)
    fleet_values = ",\n".join(
        f"({_quote(code)},{_quote(name)},{_quote(group)},{order},{str(expiry).lower()},"
        f"{str(required).lower()})"
        for order, (code, name, group, expiry, required) in enumerate(_FLEET_CATEGORIES, start=1)
    )
    op.execute(f"""
        INSERT INTO document_categories (id, company_id, module, code, name, group_name,
          sort_order, is_active, requires_expiry, compliance_required, created_at, updated_at)
        SELECT gen_random_uuid(), c.id, 'fleet', v.code, v.name, v.group_name, v.sort_order, true,
          v.requires_expiry, v.compliance_required, now(), now()
        FROM companies c
        CROSS JOIN (VALUES {fleet_values})
          AS v(code, name, group_name, sort_order, requires_expiry, compliance_required)
        ON CONFLICT (company_id, module, code) DO NOTHING;

        INSERT INTO document_categories (id, company_id, module, code, name, group_name,
          sort_order, is_active, requires_expiry, compliance_required, created_at, updated_at)
        SELECT gen_random_uuid(), c.id, 'employees', 'driver_license', 'Licencia de conducir',
          'Conducción', 49, true, true, true, now(), now()
        FROM companies c
        ON CONFLICT (company_id, module, code) DO UPDATE
          SET requires_expiry = true, compliance_required = true;
    """)

    permission_values = ",\n".join(
        f"(gen_random_uuid(),{_quote(code)},{_quote(description)},{_quote(module)},now())"
        for code, description, module in _FLEET_PERMISSIONS
    )
    all_codes = ",".join(_quote(code) for code, _, _ in _FLEET_PERMISSIONS)
    op.execute(f"""
        INSERT INTO permissions (id, code, description, module, created_at)
        VALUES {permission_values}
        ON CONFLICT DO NOTHING;
        INSERT INTO role_permissions (role_id, permission_id, created_at)
        SELECT r.id, p.id, now() FROM roles r CROSS JOIN permissions p
        WHERE r.name = 'SUPER_ADMIN' AND r.is_system IS TRUE AND r.company_id IS NULL
          AND r.deleted_at IS NULL AND p.deleted_at IS NULL AND p.code IN ({all_codes})
        ON CONFLICT DO NOTHING;
    """)
    for role, codes in _ROLE_GRANTS.items():
        role_codes = ",".join(_quote(code) for code in codes)
        op.execute(f"""
            INSERT INTO role_permissions (role_id, permission_id, created_at)
            SELECT r.id, p.id, now() FROM roles r CROSS JOIN permissions p
            WHERE r.name = {_quote(role)} AND r.deleted_at IS NULL AND p.deleted_at IS NULL
              AND p.code IN ({role_codes})
            ON CONFLICT DO NOTHING;
        """)

    # Flota es la fuente de los vehículos: cada vehículo de inventario existente obtiene su
    # ficha en la sucursal donde está su almacén de tránsito, con datos por completar.
    op.execute("""
        INSERT INTO fleet_vehicles (company_id, branch_id, code, plate, kind, brand, model, year,
          capacity_kg, status, inventory_vehicle_id, notes, created_by)
        SELECT iv.company_id, w.branch_id, iv.code, upper(left(iv.code, 16)), 'cargo_van',
          'Por definir', iv.name, EXTRACT(YEAR FROM now())::int, 1000,
          CASE WHEN iv.status = 'active' THEN 'active' ELSE 'out_of_service' END,
          iv.id, 'Ficha creada automáticamente desde el catálogo de vehículos de traslados.',
          iv.created_by_id
        FROM inventory_vehicles iv
        JOIN warehouses w ON w.id = iv.transit_warehouse_id AND w.company_id = iv.company_id;
    """)


def downgrade() -> None:
    # Los registros de flota son historia operativa; no se eliminan silenciosamente.
    raise RuntimeError("0098 no admite downgrade: elimine los datos de flota manualmente.")
