"""Punto de venta: cajas, turnos, efectivo, arqueo ciego, depósitos, PIN de supervisor y roles.

Revision ID: 0146
Revises: 0145

Bloque V6a.

- ``pos_registers``: la caja. Pertenece a una sucursal y usa un punto de venta fiscal de esa
  sucursal (uno a uno); las llaves compuestas impiden ligarla a un punto de venta de otra.
- ``pos_shifts``: el turno de un cajero en una caja. Un solo turno sin cerrar por caja y por cajero.
  Estados: ``open`` (vende), ``counted`` (contó; espera al supervisor), ``recount`` (el supervisor
  pidió recontar) y ``closed`` (aprobado, inmutable). Quien aprueba nunca es el cajero.
- ``pos_cash_movements``: entradas, salidas y retiros a caja fuerte del turno; solo se agrega. El
  fondo inicial es el del turno (``opening_float``, igual a su conteo de apertura).
- ``pos_shift_counts`` y ``pos_shift_count_lines``: conteos por denominación (apertura y cierre);
  un recuento crea otro conteo y el anterior queda como historia. Solo se agregan.
- ``pos_deposits`` y ``pos_deposit_shifts``: el depósito bancario de turnos cerrados.
- ``pos_supervisor_pins``: PIN de autorización en caja (Argon2id) con bloqueo por intentos.

Permisos ``pos:*`` y las plantillas de rol ``CAJERO`` y ``SUPERVISOR_TIENDA``.
"""

from alembic import op
from sqlalchemy import text

revision = "0146"
down_revision = "0145"
branch_labels = None
depends_on = None

_PERMISSIONS = (
    ("pos:sell", "Vender en el punto de venta con su turno abierto"),
    ("pos:shift_open", "Abrir su turno de caja"),
    ("pos:shift_close", "Contar y entregar su turno de caja"),
    ("pos:cash_movements", "Registrar entradas, salidas y retiros de efectivo de su turno"),
    ("pos:reprint", "Reimprimir los tiquetes de su turno"),
    ("pos:supervise", "Autorizar en caja, aprobar cierres y ver los turnos de la sucursal"),
    ("pos:registers_manage", "Configurar las cajas del punto de venta"),
    ("pos:showcase", "Pasar productos a vitrina y contar la vitrina"),
    ("pos:reports", "Ver los informes de caja (X, Z y por cajero)"),
    ("pos:deposits", "Registrar los depósitos bancarios de los turnos"),
)

_CASHIER = ("pos:sell", "pos:shift_open", "pos:shift_close", "pos:cash_movements", "pos:reprint")
_SUPERVISOR = (*_CASHIER, "pos:supervise", "pos:showcase", "pos:reports", "pos:deposits")
_ROLES = (
    ("CAJERO", "Cajero: vende y cobra en el punto de venta con su propio turno", _CASHIER),
    (
        "SUPERVISOR_TIENDA",
        "Supervisor de tienda: autoriza en caja, aprueba cierres, vitrina y depósitos",
        _SUPERVISOR,
    ),
)

_TABLES = (
    "pos_deposit_shifts",
    "pos_deposits",
    "pos_shift_count_lines",
    "pos_shift_counts",
    "pos_cash_movements",
    "pos_shifts",
    "pos_registers",
    "pos_supervisor_pins",
)


def upgrade() -> None:
    op.execute("""
        ALTER TABLE fiscal_establishments
          ADD CONSTRAINT uq_fiscal_establishments_company_id_branch UNIQUE (company_id, id, branch_id);
        ALTER TABLE fiscal_points_of_sale
          ADD CONSTRAINT uq_fiscal_points_of_sale_company_establishment
            UNIQUE (company_id, establishment_id, id);

        CREATE TABLE pos_registers (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL REFERENCES companies (id) ON DELETE RESTRICT,
            branch_id uuid NOT NULL,
            establishment_id uuid NOT NULL,
            point_of_sale_id uuid NOT NULL,
            code varchar(20) NOT NULL CHECK (code ~ '^[A-Z0-9][A-Z0-9-]{1,19}$'),
            name varchar(80) NOT NULL CHECK (char_length(btrim(name)) >= 2),
            opening_float numeric(12, 2) NOT NULL DEFAULT 0
                CHECK (opening_float >= 0 AND opening_float <= 10000),
            cash_out_approval_threshold numeric(12, 2) NOT NULL DEFAULT 20
                CHECK (cash_out_approval_threshold >= 0),
            cash_drawer_limit numeric(12, 2) CHECK (cash_drawer_limit > 0),
            is_active boolean NOT NULL DEFAULT true,
            version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
            created_by_id uuid NOT NULL REFERENCES users (id) ON DELETE RESTRICT,
            updated_by_id uuid NOT NULL REFERENCES users (id) ON DELETE RESTRICT,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_pos_registers_company_id UNIQUE (company_id, id),
            CONSTRAINT uq_pos_registers_company_id_branch UNIQUE (company_id, id, branch_id),
            CONSTRAINT uq_pos_registers_code UNIQUE (company_id, code),
            CONSTRAINT uq_pos_registers_point_of_sale UNIQUE (company_id, point_of_sale_id),
            CONSTRAINT fk_pos_registers_branch FOREIGN KEY (branch_id, company_id)
                REFERENCES branches (id, company_id) ON DELETE RESTRICT,
            CONSTRAINT fk_pos_registers_establishment
                FOREIGN KEY (company_id, establishment_id, branch_id)
                REFERENCES fiscal_establishments (company_id, id, branch_id) ON DELETE RESTRICT,
            CONSTRAINT fk_pos_registers_point_of_sale
                FOREIGN KEY (company_id, establishment_id, point_of_sale_id)
                REFERENCES fiscal_points_of_sale (company_id, establishment_id, id)
                ON DELETE RESTRICT
        );

        CREATE TABLE pos_shifts (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL REFERENCES companies (id) ON DELETE RESTRICT,
            branch_id uuid NOT NULL,
            register_id uuid NOT NULL,
            cashier_id uuid NOT NULL REFERENCES users (id) ON DELETE RESTRICT,
            number integer NOT NULL CHECK (number >= 1),
            status varchar(10) NOT NULL DEFAULT 'open'
                CHECK (status IN ('open', 'counted', 'recount', 'closed')),
            opening_float numeric(12, 2) NOT NULL CHECK (opening_float >= 0),
            opened_at timestamptz NOT NULL DEFAULT now(),
            counted_at timestamptz,
            recount_reason varchar(300),
            closed_at timestamptz,
            approved_by_id uuid REFERENCES users (id) ON DELETE RESTRICT,
            approval_notes varchar(300),
            expected_cash numeric(12, 2),
            counted_cash numeric(12, 2) CHECK (counted_cash >= 0),
            cash_difference numeric(12, 2),
            expected_card numeric(12, 2),
            declared_card numeric(12, 2) CHECK (declared_card >= 0),
            expected_transfer numeric(12, 2),
            declared_transfer numeric(12, 2) CHECK (declared_transfer >= 0),
            retained_float numeric(12, 2) CHECK (retained_float >= 0),
            cash_to_deposit numeric(12, 2) CHECK (cash_to_deposit >= 0),
            version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
            idempotency_key varchar(120) NOT NULL CHECK (char_length(idempotency_key) >= 8),
            CONSTRAINT uq_pos_shifts_company_id UNIQUE (company_id, id),
            CONSTRAINT uq_pos_shifts_company_id_branch UNIQUE (company_id, id, branch_id),
            CONSTRAINT uq_pos_shifts_number UNIQUE (company_id, number),
            CONSTRAINT uq_pos_shifts_idempotency UNIQUE (company_id, idempotency_key),
            CONSTRAINT fk_pos_shifts_register FOREIGN KEY (company_id, register_id, branch_id)
                REFERENCES pos_registers (company_id, id, branch_id) ON DELETE RESTRICT,
            CONSTRAINT ck_pos_shifts_counted CHECK (
                (status = 'open') = (counted_at IS NULL AND counted_cash IS NULL)
            ),
            CONSTRAINT ck_pos_shifts_recount CHECK (
                (status = 'recount') = (recount_reason IS NOT NULL)
            ),
            CONSTRAINT ck_pos_shifts_closed CHECK (
                (status = 'closed') = (
                    closed_at IS NOT NULL AND approved_by_id IS NOT NULL
                    AND expected_cash IS NOT NULL AND cash_difference IS NOT NULL
                    AND expected_card IS NOT NULL AND expected_transfer IS NOT NULL
                    AND retained_float IS NOT NULL AND cash_to_deposit IS NOT NULL
                )
            ),
            CONSTRAINT ck_pos_shifts_declared CHECK (
                (counted_cash IS NULL) = (declared_card IS NULL AND declared_transfer IS NULL)
            ),
            CONSTRAINT ck_pos_shifts_difference CHECK (
                cash_difference IS NULL OR cash_difference = counted_cash - expected_cash
            ),
            CONSTRAINT ck_pos_shifts_deposit CHECK (
                cash_to_deposit IS NULL OR cash_to_deposit + retained_float = counted_cash
            ),
            CONSTRAINT ck_pos_shifts_approver CHECK (approved_by_id IS NULL OR approved_by_id <> cashier_id),
            CONSTRAINT ck_pos_shifts_dates CHECK (
                (counted_at IS NULL OR counted_at >= opened_at)
                AND (closed_at IS NULL OR closed_at >= counted_at)
            )
        );
        CREATE UNIQUE INDEX uq_pos_shifts_register_unclosed ON pos_shifts (company_id, register_id)
            WHERE status <> 'closed';
        CREATE UNIQUE INDEX uq_pos_shifts_cashier_unclosed ON pos_shifts (company_id, cashier_id)
            WHERE status <> 'closed';
        CREATE INDEX ix_pos_shifts_branch_status ON pos_shifts (company_id, branch_id, status, opened_at DESC);

        CREATE FUNCTION guard_pos_shift_closed() RETURNS trigger AS $$
        BEGIN
          IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION 'POS shifts are never deleted' USING ERRCODE = '23514';
          END IF;
          IF OLD.status = 'closed' THEN
            RAISE EXCEPTION 'A closed POS shift is immutable' USING ERRCODE = '23514';
          END IF;
          RETURN NEW;
        END; $$ LANGUAGE plpgsql;
        CREATE TRIGGER trg_pos_shifts_closed_immutable BEFORE UPDATE OR DELETE ON pos_shifts
          FOR EACH ROW EXECUTE FUNCTION guard_pos_shift_closed();

        CREATE TABLE pos_cash_movements (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL REFERENCES companies (id) ON DELETE RESTRICT,
            shift_id uuid NOT NULL,
            kind varchar(10) NOT NULL CHECK (kind IN ('cash_in', 'cash_out', 'safe_drop')),
            amount numeric(12, 2) NOT NULL CHECK (amount > 0),
            reason varchar(200) NOT NULL CHECK (char_length(btrim(reason)) >= 5),
            reference varchar(60),
            authorized_by_id uuid REFERENCES users (id) ON DELETE RESTRICT,
            created_by_id uuid NOT NULL REFERENCES users (id) ON DELETE RESTRICT,
            created_at timestamptz NOT NULL DEFAULT now(),
            idempotency_key varchar(120) NOT NULL CHECK (char_length(idempotency_key) >= 8),
            CONSTRAINT uq_pos_cash_movements_idempotency UNIQUE (company_id, idempotency_key),
            CONSTRAINT fk_pos_cash_movements_shift FOREIGN KEY (company_id, shift_id)
                REFERENCES pos_shifts (company_id, id) ON DELETE RESTRICT,
            CONSTRAINT ck_pos_cash_movements_authorizer CHECK (
                authorized_by_id IS NULL OR authorized_by_id <> created_by_id
            )
        );
        CREATE INDEX ix_pos_cash_movements_shift ON pos_cash_movements (company_id, shift_id, created_at);

        CREATE TABLE pos_shift_counts (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL REFERENCES companies (id) ON DELETE RESTRICT,
            shift_id uuid NOT NULL,
            kind varchar(8) NOT NULL CHECK (kind IN ('opening', 'closing')),
            sequence smallint NOT NULL CHECK (sequence >= 1),
            cash_total numeric(12, 2) NOT NULL CHECK (cash_total >= 0),
            card_total numeric(12, 2) CHECK (card_total >= 0),
            transfer_total numeric(12, 2) CHECK (transfer_total >= 0),
            notes varchar(300),
            counted_by_id uuid NOT NULL REFERENCES users (id) ON DELETE RESTRICT,
            counted_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_pos_shift_counts_company_id UNIQUE (company_id, id),
            CONSTRAINT uq_pos_shift_counts_sequence UNIQUE (company_id, shift_id, kind, sequence),
            CONSTRAINT fk_pos_shift_counts_shift FOREIGN KEY (company_id, shift_id)
                REFERENCES pos_shifts (company_id, id) ON DELETE RESTRICT,
            CONSTRAINT ck_pos_shift_counts_kind CHECK (
                (kind = 'opening' AND sequence = 1 AND card_total IS NULL AND transfer_total IS NULL)
                OR (kind = 'closing' AND card_total IS NOT NULL AND transfer_total IS NOT NULL)
            )
        );

        CREATE TABLE pos_shift_count_lines (
            company_id uuid NOT NULL,
            count_id uuid NOT NULL,
            form varchar(4) NOT NULL CHECK (form IN ('coin', 'bill')),
            denomination numeric(6, 2) NOT NULL,
            quantity integer NOT NULL CHECK (quantity >= 0 AND quantity <= 100000),
            PRIMARY KEY (company_id, count_id, form, denomination),
            CONSTRAINT fk_pos_shift_count_lines_count FOREIGN KEY (company_id, count_id)
                REFERENCES pos_shift_counts (company_id, id) ON DELETE RESTRICT,
            CONSTRAINT ck_pos_shift_count_lines_denomination CHECK (
                (form = 'coin' AND denomination IN (0.01, 0.05, 0.10, 0.25, 0.50, 1.00))
                OR (form = 'bill' AND denomination IN (1, 2, 5, 10, 20, 50, 100))
            )
        );

        CREATE TABLE pos_deposits (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL REFERENCES companies (id) ON DELETE RESTRICT,
            branch_id uuid NOT NULL,
            number integer NOT NULL CHECK (number >= 1),
            deposited_on date NOT NULL,
            bank_name varchar(80) NOT NULL CHECK (char_length(btrim(bank_name)) >= 2),
            account_reference varchar(40) NOT NULL CHECK (char_length(btrim(account_reference)) >= 2),
            slip_number varchar(40) NOT NULL CHECK (char_length(btrim(slip_number)) >= 2),
            expected_amount numeric(12, 2) NOT NULL CHECK (expected_amount > 0),
            deposited_amount numeric(12, 2) NOT NULL CHECK (deposited_amount > 0),
            difference numeric(12, 2) NOT NULL,
            notes varchar(300),
            created_by_id uuid NOT NULL REFERENCES users (id) ON DELETE RESTRICT,
            created_at timestamptz NOT NULL DEFAULT now(),
            idempotency_key varchar(120) NOT NULL CHECK (char_length(idempotency_key) >= 8),
            CONSTRAINT uq_pos_deposits_company_id UNIQUE (company_id, id),
            CONSTRAINT uq_pos_deposits_number UNIQUE (company_id, number),
            CONSTRAINT uq_pos_deposits_slip UNIQUE (company_id, bank_name, slip_number),
            CONSTRAINT uq_pos_deposits_idempotency UNIQUE (company_id, idempotency_key),
            CONSTRAINT fk_pos_deposits_branch FOREIGN KEY (branch_id, company_id)
                REFERENCES branches (id, company_id) ON DELETE RESTRICT,
            CONSTRAINT ck_pos_deposits_difference CHECK (difference = deposited_amount - expected_amount),
            CONSTRAINT ck_pos_deposits_notes CHECK (
                difference = 0 OR char_length(btrim(coalesce(notes, ''))) >= 5
            )
        );

        CREATE TABLE pos_deposit_shifts (
            company_id uuid NOT NULL,
            deposit_id uuid NOT NULL,
            shift_id uuid NOT NULL,
            branch_id uuid NOT NULL,
            amount numeric(12, 2) NOT NULL CHECK (amount > 0),
            PRIMARY KEY (company_id, deposit_id, shift_id),
            CONSTRAINT uq_pos_deposit_shifts_shift UNIQUE (company_id, shift_id),
            CONSTRAINT fk_pos_deposit_shifts_deposit FOREIGN KEY (company_id, deposit_id)
                REFERENCES pos_deposits (company_id, id) ON DELETE RESTRICT,
            CONSTRAINT fk_pos_deposit_shifts_shift FOREIGN KEY (company_id, shift_id, branch_id)
                REFERENCES pos_shifts (company_id, id, branch_id) ON DELETE RESTRICT
        );

        CREATE TABLE pos_supervisor_pins (
            user_id uuid PRIMARY KEY REFERENCES users (id) ON DELETE CASCADE,
            pin_hash varchar(255) NOT NULL,
            failed_attempts smallint NOT NULL DEFAULT 0 CHECK (failed_attempts >= 0),
            locked_until timestamptz,
            updated_at timestamptz NOT NULL DEFAULT now()
        );

        CREATE FUNCTION guard_pos_append_only() RETURNS trigger AS $$
        BEGIN
          RAISE EXCEPTION 'POS cash records are append-only' USING ERRCODE = '23514';
        END; $$ LANGUAGE plpgsql;
        CREATE TRIGGER trg_pos_cash_movements_append_only BEFORE UPDATE OR DELETE ON pos_cash_movements
          FOR EACH ROW EXECUTE FUNCTION guard_pos_append_only();
        CREATE TRIGGER trg_pos_shift_counts_append_only BEFORE UPDATE OR DELETE ON pos_shift_counts
          FOR EACH ROW EXECUTE FUNCTION guard_pos_append_only();
        CREATE TRIGGER trg_pos_shift_count_lines_append_only
          BEFORE UPDATE OR DELETE ON pos_shift_count_lines
          FOR EACH ROW EXECUTE FUNCTION guard_pos_append_only();
        CREATE TRIGGER trg_pos_deposits_append_only BEFORE UPDATE OR DELETE ON pos_deposits
          FOR EACH ROW EXECUTE FUNCTION guard_pos_append_only();
        CREATE TRIGGER trg_pos_deposit_shifts_append_only BEFORE UPDATE OR DELETE ON pos_deposit_shifts
          FOR EACH ROW EXECUTE FUNCTION guard_pos_append_only();
    """)
    for code, description in _PERMISSIONS:
        op.execute(f"""
            INSERT INTO permissions (id, code, description, module, created_at)
            VALUES (gen_random_uuid(), '{code}', '{description}', 'pos', now())
            ON CONFLICT DO NOTHING
        """)
        op.execute(f"""
            INSERT INTO role_permissions (role_id, permission_id, created_at)
            SELECT r.id, p.id, now() FROM roles r CROSS JOIN permissions p
            WHERE r.name = 'SUPER_ADMIN' AND r.is_system IS TRUE AND r.company_id IS NULL
              AND r.deleted_at IS NULL AND p.deleted_at IS NULL AND p.code = '{code}'
            ON CONFLICT DO NOTHING
        """)
    for name, description, codes in _ROLES:
        op.execute(f"""
            INSERT INTO roles (id, company_id, name, description, is_system, created_at, updated_at)
            SELECT gen_random_uuid(), NULL, '{name}', '{description}', true, now(), now()
            WHERE NOT EXISTS (
                SELECT 1 FROM roles
                WHERE company_id IS NULL AND lower(name) = lower('{name}') AND deleted_at IS NULL
            )
        """)
        listed = ", ".join(f"'{code}'" for code in codes)
        op.execute(f"""
            INSERT INTO role_permissions (role_id, permission_id, created_at)
            SELECT r.id, p.id, now() FROM roles r CROSS JOIN permissions p
            WHERE r.name = '{name}' AND r.company_id IS NULL AND r.deleted_at IS NULL
              AND p.deleted_at IS NULL AND p.code IN ({listed})
            ON CONFLICT DO NOTHING
        """)


def downgrade() -> None:
    bind = op.get_bind()
    used = sum(
        bind.execute(text(f"SELECT count(*) FROM {table}")).scalar() or 0
        for table in ("pos_registers", "pos_supervisor_pins")
    )
    assigned = (
        bind.execute(
            text(
                "SELECT count(*) FROM user_roles ur JOIN roles r ON r.id = ur.role_id "
                "WHERE r.company_id IS NULL AND r.name IN ('CAJERO', 'SUPERVISOR_TIENDA')"
            )
        ).scalar()
        or 0
    )
    if used or assigned:
        raise RuntimeError(
            f"Hay {used} cajas o PIN de supervisor y {assigned} asignaciones de los roles del punto "
            "de venta; la migración 0146 no los borra. Respáldalos antes de revertir."
        )
    op.execute("""
        DELETE FROM role_permissions WHERE role_id IN (
            SELECT id FROM roles WHERE company_id IS NULL AND name IN ('CAJERO', 'SUPERVISOR_TIENDA')
        );
        DELETE FROM roles WHERE company_id IS NULL AND name IN ('CAJERO', 'SUPERVISOR_TIENDA');
    """)
    for code, _ in _PERMISSIONS:
        op.execute(f"""
            DELETE FROM role_permissions WHERE permission_id IN
              (SELECT id FROM permissions WHERE code = '{code}');
            DELETE FROM permissions WHERE code = '{code}';
        """)
    for table in _TABLES:
        op.execute(f"DROP TABLE {table}")
    op.execute("""
        DROP FUNCTION guard_pos_append_only();
        DROP FUNCTION guard_pos_shift_closed();
        ALTER TABLE fiscal_points_of_sale DROP CONSTRAINT uq_fiscal_points_of_sale_company_establishment;
        ALTER TABLE fiscal_establishments DROP CONSTRAINT uq_fiscal_establishments_company_id_branch;
    """)
