"""Safely rehearse ERS-B03 revision 0086 on a restored database copy."""

from __future__ import annotations

import os
from urllib.parse import urlsplit, urlunsplit

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

SOURCE_DATABASE = "erp_db"
TARGET_DATABASE = "erp_ers_b03_rehearsal_20261019"
SOURCE_REVISION = "0085"
TARGET_REVISION = "0086"

source_url = os.environ.get("DATABASE_URL_SYNC")
if not source_url:
    raise SystemExit("DATABASE_URL_SYNC no está configurada; no se ejecutó la migración.")
parsed = urlsplit(source_url)
if parsed.path != f"/{SOURCE_DATABASE}":
    raise SystemExit("Origen inesperado; solo se permite derivar la conexión desde erp_db.")
target_url = urlunsplit(parsed._replace(path=f"/{TARGET_DATABASE}"))

engine = create_engine(target_url)
with engine.connect() as connection:
    database_name, revision = connection.execute(
        text(
            "SELECT current_database(), "
            "(SELECT version_num FROM alembic_version LIMIT 1)"
        )
    ).one()
if database_name != TARGET_DATABASE or revision != SOURCE_REVISION:
    raise SystemExit(
        f"Ensayo cancelado: base={database_name}, revisión={revision}; "
        f"se esperaba {TARGET_DATABASE}/{SOURCE_REVISION}."
    )

os.environ["DATABASE_URL_SYNC"] = target_url
config = Config("/app/alembic.ini")
config.set_main_option("sqlalchemy.url", target_url)
command.upgrade(config, TARGET_REVISION)

with engine.connect() as connection:
    database_name, revision = connection.execute(
        text(
            "SELECT current_database(), "
            "(SELECT version_num FROM alembic_version LIMIT 1)"
        )
    ).one()
if database_name != TARGET_DATABASE or revision != TARGET_REVISION:
    raise SystemExit("El ensayo no quedó en la revisión 0086 esperada.")
print(f"Rehearsal passed: {database_name} {revision}")
engine.dispose()
