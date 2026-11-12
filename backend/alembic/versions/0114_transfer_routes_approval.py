"""Transfers between branches and back to headquarters, with approval and per-company rules.

Revision ID: 0114
Revises: 0113
"""

from alembic import op
from sqlalchemy import text

revision = "0114"
down_revision = "0113"
branch_labels = None
depends_on = None

_PERMISSIONS = (
    ("inventory:transfer_approve", "Aprobar o rechazar traslados entre sucursales"),
    ("inventory:transfer_settings", "Configurar las rutas y aprobaciones de traslados"),
)
_NEW_COMMANDS = ("submit", "approve", "reject", "withdraw")
_STATUS_BEFORE = (
    "status IN ('preparation','in_transit','received','closed_with_adjustment','incident','cancelled')"
)
_STATUS_AFTER = (
    "status IN ('preparation','pending_approval','approved','in_transit','received',"
    "'closed_with_adjustment','incident','cancelled')"
)
_ACTION_BEFORE = (
    "action IN ('create','update','cancel','dispatch','receive','incident','resolve',"
    "'resolve_adjustment','return')"
)
_ACTION_AFTER = (
    "action IN ('create','update','cancel','dispatch','receive','incident','resolve',"
    "'resolve_adjustment','return','submit','approve','reject','withdraw')"
)


def upgrade() -> None:
    op.execute("""
        CREATE TABLE inventory_transfer_settings (
            company_id uuid PRIMARY KEY REFERENCES companies (id) ON DELETE CASCADE,
            allow_branch_to_branch boolean NOT NULL DEFAULT false,
            allow_branch_to_central boolean NOT NULL DEFAULT false,
            require_approval boolean NOT NULL DEFAULT true,
            updated_by uuid REFERENCES users (id) ON DELETE SET NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        ALTER TABLE inventory_transfers
            ADD COLUMN route_type varchar(24) NOT NULL DEFAULT 'central_distribution',
            ADD COLUMN requires_approval boolean NOT NULL DEFAULT false,
            ADD COLUMN approval_round integer NOT NULL DEFAULT 0,
            ADD COLUMN submitted_by_id uuid,
            ADD COLUMN submitted_at timestamptz,
            ADD COLUMN approved_by_id uuid,
            ADD COLUMN approved_at timestamptz,
            ADD COLUMN rejected_by_id uuid,
            ADD COLUMN rejected_at timestamptz,
            ADD COLUMN rejection_reason text
    """)
    op.execute("ALTER TABLE inventory_transfers DROP CONSTRAINT ck_inventory_transfers_status")
    op.execute(
        f"ALTER TABLE inventory_transfers ADD CONSTRAINT ck_inventory_transfers_status "
        f"CHECK ({_STATUS_AFTER})"
    )
    op.execute("""
        ALTER TABLE inventory_transfers
            ADD CONSTRAINT ck_inventory_transfers_route_type
                CHECK (route_type IN ('central_distribution','branch_to_branch','branch_to_central')),
            ADD CONSTRAINT ck_inventory_transfers_approval_round CHECK (approval_round >= 0),
            ADD CONSTRAINT ck_inventory_transfers_submitted_pair
                CHECK ((submitted_by_id IS NULL) = (submitted_at IS NULL)),
            ADD CONSTRAINT ck_inventory_transfers_approved_pair
                CHECK ((approved_by_id IS NULL) = (approved_at IS NULL)),
            ADD CONSTRAINT ck_inventory_transfers_rejected_pair
                CHECK ((rejected_by_id IS NULL) = (rejected_at IS NULL)),
            ADD CONSTRAINT ck_inventory_transfers_rejection_reason
                CHECK (rejection_reason IS NULL OR (rejected_by_id IS NOT NULL
                       AND char_length(btrim(rejection_reason)) >= 5)),
            ADD CONSTRAINT ck_inventory_transfers_approval_state
                CHECK (status NOT IN ('pending_approval','approved') OR
                       (route_type <> 'central_distribution' AND requires_approval
                        AND submitted_by_id IS NOT NULL AND approval_round >= 1)),
            ADD CONSTRAINT ck_inventory_transfers_approved_state
                CHECK (status <> 'approved' OR approved_by_id IS NOT NULL)
    """)
    op.execute(
        "ALTER TABLE inventory_transfer_commands "
        "DROP CONSTRAINT ck_inventory_transfer_commands_action"
    )
    op.execute(
        f"ALTER TABLE inventory_transfer_commands ADD CONSTRAINT "
        f"ck_inventory_transfer_commands_action CHECK ({_ACTION_AFTER})"
    )
    op.execute("""
        CREATE INDEX ix_inventory_transfers_origin
            ON inventory_transfers (company_id, origin_warehouse_id, status)
    """)
    op.execute("""
        CREATE INDEX ix_inventory_transfers_pending_approval
            ON inventory_transfers (company_id, origin_warehouse_id)
            WHERE status = 'pending_approval'
    """)
    for code, description in _PERMISSIONS:
        op.execute(f"""
            INSERT INTO permissions (id, code, description, module, created_at)
            VALUES (gen_random_uuid(), '{code}', '{description}', 'inventory', now())
            ON CONFLICT DO NOTHING
        """)
        op.execute(f"""
            INSERT INTO role_permissions (role_id, permission_id, created_at)
            SELECT r.id, p.id, now() FROM roles r CROSS JOIN permissions p
            WHERE r.name = 'SUPER_ADMIN' AND r.is_system IS TRUE AND r.company_id IS NULL
              AND r.deleted_at IS NULL AND p.deleted_at IS NULL AND p.code = '{code}'
            ON CONFLICT DO NOTHING
        """)


def downgrade() -> None:
    blocked = (
        op.get_bind()
        .execute(
            text("""
                SELECT count(*) FROM inventory_transfers
                WHERE status IN ('pending_approval','approved')
                   OR route_type <> 'central_distribution'
            """)
        )
        .scalar()
    )
    if blocked:
        raise RuntimeError(
            f"Hay {blocked} traslados con rutas entre sucursales o aprobaciones "
            "que se perderían al volver a la versión anterior."
        )
    commands = ", ".join(f"'{action}'" for action in _NEW_COMMANDS)
    op.execute(f"DELETE FROM inventory_transfer_commands WHERE action IN ({commands})")
    op.execute("DROP INDEX ix_inventory_transfers_pending_approval")
    op.execute("DROP INDEX ix_inventory_transfers_origin")
    op.execute(
        "ALTER TABLE inventory_transfer_commands "
        "DROP CONSTRAINT ck_inventory_transfer_commands_action"
    )
    op.execute(
        f"ALTER TABLE inventory_transfer_commands ADD CONSTRAINT "
        f"ck_inventory_transfer_commands_action CHECK ({_ACTION_BEFORE})"
    )
    op.execute("""
        ALTER TABLE inventory_transfers
            DROP CONSTRAINT ck_inventory_transfers_approved_state,
            DROP CONSTRAINT ck_inventory_transfers_approval_state,
            DROP CONSTRAINT ck_inventory_transfers_rejection_reason,
            DROP CONSTRAINT ck_inventory_transfers_rejected_pair,
            DROP CONSTRAINT ck_inventory_transfers_approved_pair,
            DROP CONSTRAINT ck_inventory_transfers_submitted_pair,
            DROP CONSTRAINT ck_inventory_transfers_approval_round,
            DROP CONSTRAINT ck_inventory_transfers_route_type,
            DROP CONSTRAINT ck_inventory_transfers_status
    """)
    op.execute(
        f"ALTER TABLE inventory_transfers ADD CONSTRAINT ck_inventory_transfers_status "
        f"CHECK ({_STATUS_BEFORE})"
    )
    op.execute("""
        ALTER TABLE inventory_transfers
            DROP COLUMN rejection_reason,
            DROP COLUMN rejected_at,
            DROP COLUMN rejected_by_id,
            DROP COLUMN approved_at,
            DROP COLUMN approved_by_id,
            DROP COLUMN submitted_at,
            DROP COLUMN submitted_by_id,
            DROP COLUMN approval_round,
            DROP COLUMN requires_approval,
            DROP COLUMN route_type
    """)
    op.execute("DROP TABLE inventory_transfer_settings")
    for code, _ in _PERMISSIONS:
        op.execute(f"""
            DELETE FROM role_permissions WHERE permission_id IN
              (SELECT id FROM permissions WHERE code = '{code}');
            DELETE FROM permissions WHERE code = '{code}';
        """)
