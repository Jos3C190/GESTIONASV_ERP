"""Repair the old .invalid operator placeholder without changing authentication or grants.

Preview by default. --apply updates only the email and appends a mandatory audit
record in the same transaction. Unrelated addresses and users are never changed.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid

from app.infrastructure.db.session import async_session_factory
from app.infrastructure.models.audit import AuditLog
from app.infrastructure.models.organization import UserCompany
from app.infrastructure.models.rbac import Role, UserRole
from app.infrastructure.models.user import User
from scripts.provision_warehouse_operator import operator_email
from sqlalchemy import func, select


async def repair(args) -> dict[str, object]:
    company_id = uuid.UUID(str(args.company_id))
    email = operator_email(args.username, args.email)
    async with async_session_factory() as session, session.begin():
        actor = await session.scalar(
            select(User).where(
                User.username == args.actor_username,
                User.is_superuser.is_(True),
                User.is_active.is_(True),
                User.deleted_at.is_(None),
            )
        )
        if actor is None:
            raise ValueError("Se requiere un administrador activo para registrar la corrección.")
        user = await session.scalar(
            select(User)
            .join(UserCompany, UserCompany.user_id == User.id)
            .where(
                UserCompany.company_id == company_id,
                User.username == args.username,
                User.is_superuser.is_(False),
                User.deleted_at.is_(None),
            )
            .with_for_update(of=User)
        )
        if user is None:
            raise ValueError("El usuario operativo no existe en la empresa indicada.")
        has_role = await session.scalar(
            select(UserRole.role_id)
            .join(Role, Role.id == UserRole.role_id)
            .where(
                UserRole.user_id == user.id,
                UserRole.company_id == company_id,
                Role.company_id == company_id,
                Role.name == "BODEGUERO PRINCIPAL",
                Role.deleted_at.is_(None),
            )
        )
        if has_role is None:
            raise ValueError("La cuenta no tiene el rol de bodeguero principal.")
        if user.email == email:
            return {"username": user.username, "changed": False, "email": email}
        expected = f"{args.username}@gestionasv.invalid"
        if user.email != expected:
            raise ValueError(
                "El correo actual no es el marcador inválido original; revise la cuenta."
            )
        conflict = await session.scalar(
            select(User.id).where(func.lower(User.email) == email.casefold(), User.id != user.id)
        )
        if conflict:
            raise ValueError("El correo ya está asociado a otra cuenta.")
        result = {
            "username": user.username,
            "email_before": user.email,
            "email": email,
            "changed": bool(args.apply),
        }
        if not args.apply:
            return result
        old_email = user.email
        user.email = email
        session.add(
            AuditLog(
                user_id=actor.id,
                company_id=company_id,
                action="UPDATE",
                resource_type="users",
                resource_id=str(user.id),
                before_state={"email": old_email},
                after_state={"email": email},
                status="success",
                metadata_={
                    "source": "repair_warehouse_operator_email",
                    "authorization": "explicit_user_request",
                    "reason": "El marcador .invalid impedía cargar el perfil autenticado.",
                },
            )
        )
        await session.flush()
        return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("company-id", "username", "actor-username"):
        parser.add_argument(f"--{name}", required=True)
    parser.add_argument("--email")
    parser.add_argument("--apply", action="store_true")
    sys.stdout.write(json.dumps(asyncio.run(repair(parser.parse_args()))) + "\n")


if __name__ == "__main__":
    main()
