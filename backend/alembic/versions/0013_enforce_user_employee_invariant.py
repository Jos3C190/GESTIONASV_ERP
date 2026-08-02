"""Enforce one active employee record for every active user.

Revision ID: 0013
Revises: 0012
"""

from __future__ import annotations

from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO employees (
            id, company_id, employee_code, first_name, last_name,
            user_id, status, created_at, updated_at
        )
        SELECT
            gen_random_uuid(),
            COALESCE(
                (SELECT uc.company_id FROM user_companies uc
                 WHERE uc.user_id = u.id
                 ORDER BY uc.is_default DESC, uc.assigned_at ASC LIMIT 1),
                (SELECT c.id FROM companies c
                 WHERE c.is_active IS TRUE ORDER BY c.created_at ASC LIMIT 1)
            ),
            'USR-' || upper(substr(replace(u.id::text, '-', ''), 1, 12)),
            u.username,
            'Usuario',
            u.id,
            'activo',
            now(),
            now()
        FROM users u
        WHERE u.deleted_at IS NULL
          AND NOT EXISTS (
              SELECT 1 FROM employees e
              WHERE e.user_id = u.id AND e.deleted_at IS NULL
          )
          AND EXISTS (SELECT 1 FROM companies c WHERE c.is_active IS TRUE)
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION assert_user_has_employee(target_user_id uuid)
        RETURNS void AS $$
        BEGIN
            IF target_user_id IS NOT NULL
               AND EXISTS (
                   SELECT 1 FROM users u
                   WHERE u.id = target_user_id AND u.deleted_at IS NULL
               )
               AND NOT EXISTS (
                   SELECT 1 FROM employees e
                   WHERE e.user_id = target_user_id AND e.deleted_at IS NULL
               )
            THEN
                RAISE EXCEPTION 'active user % requires an active employee record', target_user_id
                    USING ERRCODE = '23514';
            END IF;
        END;
        $$ LANGUAGE plpgsql;

        CREATE OR REPLACE FUNCTION enforce_user_employee_on_user()
        RETURNS trigger AS $$
        BEGIN
            PERFORM assert_user_has_employee(NEW.id);
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE OR REPLACE FUNCTION enforce_user_employee_on_employee()
        RETURNS trigger AS $$
        BEGIN
            PERFORM assert_user_has_employee(OLD.user_id);
            IF TG_OP <> 'DELETE' THEN
                PERFORM assert_user_has_employee(NEW.user_id);
            END IF;
            RETURN COALESCE(NEW, OLD);
        END;
        $$ LANGUAGE plpgsql;

        CREATE CONSTRAINT TRIGGER users_require_employee
        AFTER INSERT OR UPDATE OF deleted_at ON users
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION enforce_user_employee_on_user();

        CREATE CONSTRAINT TRIGGER employee_preserves_user
        AFTER UPDATE OF user_id, deleted_at OR DELETE ON employees
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION enforce_user_employee_on_employee();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS employee_preserves_user ON employees")
    op.execute("DROP TRIGGER IF EXISTS users_require_employee ON users")
    op.execute("DROP FUNCTION IF EXISTS enforce_user_employee_on_employee()")
    op.execute("DROP FUNCTION IF EXISTS enforce_user_employee_on_user()")
    op.execute("DROP FUNCTION IF EXISTS assert_user_has_employee(uuid)")
