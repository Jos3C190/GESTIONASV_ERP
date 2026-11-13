"""Transport at preparation, partial reception and a register of transfer discrepancies.

Revision ID: 0116
Revises: 0115
"""

from alembic import op
from sqlalchemy import text

revision = "0116"
down_revision = "0115"
branch_labels = None
depends_on = None

_NEW_COMMANDS = (
    "close_reception",
    "discrepancy_adjust",
    "discrepancy_claim",
    "discrepancy_release",
    "discrepancy_found",
    "discrepancy_dismiss",
    "resolve_discrepancy",
    "origin_count",
)
_STATUS_BEFORE = (
    "status IN ('preparation','pending_approval','approved','in_transit','received',"
    "'closed_with_adjustment','incident','cancelled')"
)
_STATUS_AFTER = (
    "status IN ('preparation','pending_approval','approved','in_transit','partially_received',"
    "'discrepancy','received','closed_with_adjustment','incident','cancelled')"
)
_ACTION_BEFORE = (
    "action IN ('create','update','cancel','dispatch','receive','incident','resolve',"
    "'resolve_adjustment','return','submit','approve','reject','withdraw')"
)
_ACTION_AFTER = (
    "action IN ('create','update','cancel','dispatch','receive','incident','resolve',"
    "'resolve_adjustment','return','submit','approve','reject','withdraw',"
    "'close_reception','discrepancy_adjust','discrepancy_claim','discrepancy_release',"
    "'discrepancy_found','discrepancy_dismiss','resolve_discrepancy','origin_count')"
)
_SUBSTITUTION_CODES = (
    "'vehicle_unfit','vehicle_unavailable','driver_unfit','driver_unavailable',"
    "'load_change','other'"
)
_DAMAGE_TYPES = (
    "'broken','crushed','wet','contaminated','packaging','tampered','temperature','other'"
)


def upgrade() -> None:
    op.execute("ALTER TABLE inventory_transfers DROP CONSTRAINT ck_inventory_transfers_status")
    op.execute(
        f"ALTER TABLE inventory_transfers ADD CONSTRAINT ck_inventory_transfers_status "
        f"CHECK ({_STATUS_AFTER})"
    )
    op.execute("""
        ALTER TABLE inventory_transfers
            ADD COLUMN approved_vehicle_id uuid,
            ADD COLUMN approved_driver_id uuid,
            ADD COLUMN assignment_substitution_code varchar(24),
            ADD COLUMN assignment_substitution_reason text,
            ADD COLUMN assignment_substitution_by_id uuid,
            ADD COLUMN assignment_substitution_at timestamptz,
            ADD COLUMN closed_at timestamptz
    """)
    op.execute(f"""
        ALTER TABLE inventory_transfers
            ADD CONSTRAINT fk_inventory_transfers_approved_vehicle_company
                FOREIGN KEY (company_id, approved_vehicle_id)
                REFERENCES inventory_vehicles (company_id, id) ON DELETE RESTRICT,
            ADD CONSTRAINT fk_inventory_transfers_approved_driver_company
                FOREIGN KEY (company_id, approved_driver_id)
                REFERENCES drivers (company_id, id) ON DELETE RESTRICT,
            ADD CONSTRAINT fk_inventory_transfers_substitution_by
                FOREIGN KEY (assignment_substitution_by_id)
                REFERENCES users (id) ON DELETE RESTRICT,
            ADD CONSTRAINT ck_inventory_transfers_assignment_substitution
                CHECK (
                    (assignment_substitution_code IS NULL
                     AND assignment_substitution_reason IS NULL
                     AND assignment_substitution_by_id IS NULL
                     AND assignment_substitution_at IS NULL)
                    OR
                    (assignment_substitution_code IN ({_SUBSTITUTION_CODES})
                     AND assignment_substitution_reason IS NOT NULL
                     AND char_length(btrim(assignment_substitution_reason)) >= 10
                     AND assignment_substitution_by_id IS NOT NULL
                     AND assignment_substitution_at IS NOT NULL)
                )
    """)
    op.execute("""
        UPDATE inventory_transfers
        SET closed_at = COALESCE(received_at, updated_at)
        WHERE status IN ('received', 'closed_with_adjustment', 'cancelled')
    """)
    # Until now a transfer received in part stayed "in transit"; it is "partially received".
    op.execute("""
        UPDATE inventory_transfers AS t
        SET status = 'partially_received'
        WHERE t.status = 'in_transit'
          AND EXISTS (
            SELECT 1 FROM inventory_transfer_details AS d
            WHERE d.company_id = t.company_id AND d.transfer_id = t.id
              AND d.quantity_received > 0)
    """)

    op.execute("""
        ALTER TABLE inventory_transfer_details
            ADD COLUMN quantity_received_damaged numeric(18,6) NOT NULL DEFAULT 0,
            ADD COLUMN quantity_surplus numeric(18,6) NOT NULL DEFAULT 0,
            ADD CONSTRAINT ck_inventory_transfer_details_condition_quantities
                CHECK (quantity_received_damaged >= 0 AND quantity_surplus >= 0
                       AND quantity_received_damaged <= quantity_received)
    """)
    op.execute("""
        ALTER TABLE inventory_transfer_demand_allocations
            ADD COLUMN quantity_damaged numeric(18,6) NOT NULL DEFAULT 0,
            ADD CONSTRAINT ck_transfer_demand_allocations_damaged
                CHECK (quantity_damaged >= 0 AND quantity_damaged <= quantity_received)
    """)
    op.execute("""
        ALTER TABLE inventory_transfer_receipts
            ADD COLUMN condition varchar(8) NOT NULL DEFAULT 'good',
            ADD CONSTRAINT ck_inventory_transfer_receipts_condition
                CHECK (condition IN ('good','damaged')),
            ADD CONSTRAINT uq_inventory_transfer_receipts_company_id UNIQUE (company_id, id)
    """)

    op.execute(f"""
        CREATE TABLE inventory_transfer_discrepancies (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL,
            transfer_id uuid NOT NULL,
            transfer_detail_id uuid NOT NULL,
            kind varchar(16) NOT NULL,
            status varchar(16) NOT NULL DEFAULT 'open',
            source varchar(24) NOT NULL,
            quantity numeric(18,6) NOT NULL,
            damage_type varchar(16),
            notes text NOT NULL,
            evidence_reference varchar(500),
            location_id uuid,
            handling_unit_id uuid,
            receipt_id uuid,
            command_id uuid,
            incident_id uuid,
            opened_by_id uuid NOT NULL,
            opened_at timestamptz NOT NULL,
            claim_reference text,
            claimed_by_id uuid,
            claimed_at timestamptz,
            resolution varchar(16),
            resolution_notes text,
            resolved_by_id uuid,
            resolved_at timestamptz,
            origin_count_required boolean NOT NULL DEFAULT false,
            origin_counted_by_id uuid,
            origin_counted_at timestamptz,
            origin_count_notes text,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_inventory_transfer_discrepancies_company_id UNIQUE (company_id, id),
            CONSTRAINT uq_inventory_transfer_discrepancies_transfer_identity
                UNIQUE (company_id, transfer_id, id),
            CONSTRAINT fk_inventory_transfer_discrepancies_transfer
                FOREIGN KEY (company_id, transfer_id)
                REFERENCES inventory_transfers (company_id, id) ON DELETE RESTRICT,
            CONSTRAINT fk_inventory_transfer_discrepancies_detail
                FOREIGN KEY (company_id, transfer_detail_id)
                REFERENCES inventory_transfer_details (company_id, id) ON DELETE RESTRICT,
            CONSTRAINT fk_inventory_transfer_discrepancies_location
                FOREIGN KEY (location_id) REFERENCES locations (id) ON DELETE RESTRICT,
            CONSTRAINT fk_inventory_transfer_discrepancies_handling_unit
                FOREIGN KEY (company_id, handling_unit_id)
                REFERENCES inventory_handling_units (company_id, id) ON DELETE RESTRICT,
            CONSTRAINT fk_inventory_transfer_discrepancies_receipt
                FOREIGN KEY (company_id, receipt_id)
                REFERENCES inventory_transfer_receipts (company_id, id) ON DELETE RESTRICT,
            CONSTRAINT fk_inventory_transfer_discrepancies_command
                FOREIGN KEY (company_id, command_id)
                REFERENCES inventory_transfer_commands (company_id, id) ON DELETE RESTRICT,
            CONSTRAINT fk_inventory_transfer_discrepancies_incident
                FOREIGN KEY (company_id, transfer_id, incident_id)
                REFERENCES inventory_transfer_incidents (company_id, transfer_id, id)
                ON DELETE RESTRICT,
            CONSTRAINT fk_inventory_transfer_discrepancies_opened_by
                FOREIGN KEY (opened_by_id) REFERENCES users (id) ON DELETE RESTRICT,
            CONSTRAINT fk_inventory_transfer_discrepancies_claimed_by
                FOREIGN KEY (claimed_by_id) REFERENCES users (id) ON DELETE RESTRICT,
            CONSTRAINT fk_inventory_transfer_discrepancies_resolved_by
                FOREIGN KEY (resolved_by_id) REFERENCES users (id) ON DELETE RESTRICT,
            CONSTRAINT fk_inventory_transfer_discrepancies_origin_counted_by
                FOREIGN KEY (origin_counted_by_id) REFERENCES users (id) ON DELETE RESTRICT,
            CONSTRAINT ck_inventory_transfer_discrepancies_kind
                CHECK (kind IN ('shortage','surplus','damage')),
            CONSTRAINT ck_inventory_transfer_discrepancies_status
                CHECK (status IN ('open','in_claim','resolved','cancelled')),
            CONSTRAINT ck_inventory_transfer_discrepancies_source
                CHECK (source IN ('receipt','reception_close','incident')),
            CONSTRAINT ck_inventory_transfer_discrepancies_quantity CHECK (quantity > 0),
            CONSTRAINT ck_inventory_transfer_discrepancies_notes
                CHECK (char_length(btrim(notes)) >= 5),
            CONSTRAINT ck_inventory_transfer_discrepancies_damage_type
                CHECK ((kind = 'damage') = (damage_type IS NOT NULL)
                       AND (damage_type IS NULL OR damage_type IN ({_DAMAGE_TYPES}))),
            CONSTRAINT ck_inventory_transfer_discrepancies_location
                CHECK (kind = 'shortage' OR location_id IS NOT NULL),
            CONSTRAINT ck_inventory_transfer_discrepancies_resolution
                CHECK (resolution IS NULL
                       OR (kind = 'shortage' AND resolution IN ('written_off','found'))
                       OR (kind = 'damage' AND resolution IN ('written_off','released'))
                       OR (kind = 'surplus' AND resolution IN ('regularized','dismissed'))),
            CONSTRAINT ck_inventory_transfer_discrepancies_claim
                CHECK (((claim_reference IS NULL) = (claimed_by_id IS NULL))
                       AND ((claimed_by_id IS NULL) = (claimed_at IS NULL))
                       AND (claimed_at IS NULL OR kind = 'damage')),
            CONSTRAINT ck_inventory_transfer_discrepancies_lifecycle
                CHECK (
                    (status = 'open' AND resolution IS NULL AND resolved_by_id IS NULL
                     AND resolved_at IS NULL AND claimed_at IS NULL)
                    OR (status = 'in_claim' AND kind = 'damage' AND resolution IS NULL
                        AND resolved_by_id IS NULL AND resolved_at IS NULL
                        AND claimed_at IS NOT NULL)
                    OR (status = 'resolved' AND resolved_by_id IS NOT NULL
                        AND resolved_at IS NOT NULL
                        AND resolution IN ('written_off','released','regularized'))
                    OR (status = 'cancelled' AND resolved_by_id IS NOT NULL
                        AND resolved_at IS NOT NULL AND resolution IN ('found','dismissed'))
                ),
            CONSTRAINT ck_inventory_transfer_discrepancies_origin_count
                CHECK (((origin_counted_by_id IS NULL) = (origin_counted_at IS NULL))
                       AND (origin_counted_at IS NULL OR origin_count_required)
                       AND (NOT origin_count_required OR kind <> 'damage'))
        )
    """)
    op.execute("""
        CREATE INDEX ix_inventory_transfer_discrepancies_transfer
            ON inventory_transfer_discrepancies (company_id, transfer_id, status)
    """)
    op.execute("""
        CREATE UNIQUE INDEX uq_inventory_transfer_discrepancies_open_shortage
            ON inventory_transfer_discrepancies (company_id, transfer_detail_id)
            WHERE kind = 'shortage' AND status = 'open'
    """)
    op.execute("""
        CREATE INDEX ix_inventory_transfer_discrepancies_origin_count
            ON inventory_transfer_discrepancies (company_id, transfer_id)
            WHERE origin_count_required AND origin_counted_at IS NULL
    """)

    op.execute("ALTER TABLE inventory_adjustments ADD COLUMN transfer_discrepancy_id uuid")
    op.execute(
        "ALTER TABLE inventory_adjustments DROP CONSTRAINT ck_inventory_adjustments_transfer_context"
    )
    op.execute("""
        ALTER TABLE inventory_adjustments
            ADD CONSTRAINT ck_inventory_adjustments_transfer_context
                CHECK ((transfer_id IS NULL AND transfer_incident_id IS NULL)
                       OR (transfer_id IS NOT NULL
                           AND ((transfer_incident_id IS NOT NULL)
                                <> (transfer_discrepancy_id IS NOT NULL)))),
            ADD CONSTRAINT fk_inventory_adjustments_discrepancy_company
                FOREIGN KEY (company_id, transfer_discrepancy_id)
                REFERENCES inventory_transfer_discrepancies (company_id, id) ON DELETE RESTRICT,
            ADD CONSTRAINT fk_inventory_adjustments_discrepancy_transfer
                FOREIGN KEY (company_id, transfer_id, transfer_discrepancy_id)
                REFERENCES inventory_transfer_discrepancies (company_id, transfer_id, id)
                ON DELETE RESTRICT
    """)
    op.execute("""
        CREATE UNIQUE INDEX uq_inventory_adjustments_active_discrepancy
            ON inventory_adjustments (company_id, transfer_discrepancy_id)
            WHERE transfer_discrepancy_id IS NOT NULL AND status <> 'cancelled'
    """)

    op.execute(
        "ALTER TABLE inventory_transfer_commands "
        "DROP CONSTRAINT ck_inventory_transfer_commands_action"
    )
    op.execute(
        f"ALTER TABLE inventory_transfer_commands ADD CONSTRAINT "
        f"ck_inventory_transfer_commands_action CHECK ({_ACTION_AFTER})"
    )


def downgrade() -> None:
    blocked = (
        op.get_bind()
        .execute(
            text("""
                SELECT
                    (SELECT count(*) FROM inventory_transfer_discrepancies)
                  + (SELECT count(*) FROM inventory_transfers
                     WHERE status = 'discrepancy' OR assignment_substitution_code IS NOT NULL)
                  + (SELECT count(*) FROM inventory_transfer_details
                     WHERE quantity_received_damaged > 0 OR quantity_surplus > 0)
                  + (SELECT count(*) FROM inventory_transfer_receipts WHERE condition <> 'good')
            """)
        )
        .scalar()
    )
    if blocked:
        raise RuntimeError(
            f"Hay {blocked} registros de recepción parcial, discrepancias o sustituciones de "
            "transporte que se perderían al volver a la versión anterior."
        )
    # What is only partially received (nothing else attached) goes back to "in transit".
    op.execute("UPDATE inventory_transfers SET status = 'in_transit' WHERE status = 'partially_received'")
    commands = ", ".join(f"'{action}'" for action in _NEW_COMMANDS)
    op.execute(f"DELETE FROM inventory_transfer_commands WHERE action IN ({commands})")
    op.execute(
        "ALTER TABLE inventory_transfer_commands "
        "DROP CONSTRAINT ck_inventory_transfer_commands_action"
    )
    op.execute(
        f"ALTER TABLE inventory_transfer_commands ADD CONSTRAINT "
        f"ck_inventory_transfer_commands_action CHECK ({_ACTION_BEFORE})"
    )

    op.execute("DROP INDEX uq_inventory_adjustments_active_discrepancy")
    op.execute("""
        ALTER TABLE inventory_adjustments
            DROP CONSTRAINT fk_inventory_adjustments_discrepancy_transfer,
            DROP CONSTRAINT fk_inventory_adjustments_discrepancy_company,
            DROP CONSTRAINT ck_inventory_adjustments_transfer_context
    """)
    op.execute("""
        ALTER TABLE inventory_adjustments
            ADD CONSTRAINT ck_inventory_adjustments_transfer_context
                CHECK ((transfer_id IS NULL AND transfer_incident_id IS NULL)
                       OR (transfer_id IS NOT NULL AND transfer_incident_id IS NOT NULL)),
            DROP COLUMN transfer_discrepancy_id
    """)
    op.execute("DROP TABLE inventory_transfer_discrepancies")

    op.execute("""
        ALTER TABLE inventory_transfer_receipts
            DROP CONSTRAINT uq_inventory_transfer_receipts_company_id,
            DROP CONSTRAINT ck_inventory_transfer_receipts_condition,
            DROP COLUMN condition
    """)
    op.execute("""
        ALTER TABLE inventory_transfer_demand_allocations
            DROP CONSTRAINT ck_transfer_demand_allocations_damaged,
            DROP COLUMN quantity_damaged
    """)
    op.execute("""
        ALTER TABLE inventory_transfer_details
            DROP CONSTRAINT ck_inventory_transfer_details_condition_quantities,
            DROP COLUMN quantity_surplus,
            DROP COLUMN quantity_received_damaged
    """)

    op.execute("""
        ALTER TABLE inventory_transfers
            DROP CONSTRAINT ck_inventory_transfers_assignment_substitution,
            DROP CONSTRAINT fk_inventory_transfers_substitution_by,
            DROP CONSTRAINT fk_inventory_transfers_approved_driver_company,
            DROP CONSTRAINT fk_inventory_transfers_approved_vehicle_company
    """)
    op.execute("""
        ALTER TABLE inventory_transfers
            DROP COLUMN closed_at,
            DROP COLUMN assignment_substitution_at,
            DROP COLUMN assignment_substitution_by_id,
            DROP COLUMN assignment_substitution_reason,
            DROP COLUMN assignment_substitution_code,
            DROP COLUMN approved_driver_id,
            DROP COLUMN approved_vehicle_id
    """)
    op.execute("ALTER TABLE inventory_transfers DROP CONSTRAINT ck_inventory_transfers_status")
    op.execute(
        f"ALTER TABLE inventory_transfers ADD CONSTRAINT ck_inventory_transfers_status "
        f"CHECK ({_STATUS_BEFORE})"
    )
