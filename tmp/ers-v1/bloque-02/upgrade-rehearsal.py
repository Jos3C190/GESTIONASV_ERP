import os
from urllib.parse import urlsplit, urlunsplit
from alembic import command
from alembic.config import Config

target = "erp_ers_b02_rehearsal_20261018"
source = os.environ.get("DATABASE_URL_SYNC")
if not source:
    raise SystemExit("DATABASE_URL_SYNC is unavailable")
parsed = urlsplit(source)
if parsed.path != "/erp_db":
    raise SystemExit("Refusing migration: configured source is not erp_db")
os.environ["DATABASE_URL_SYNC"] = urlunsplit(parsed._replace(path=f"/{target}"))
print(f"Applying migration 0085 to isolated database {target}")
command.upgrade(Config("/app/alembic.ini"), "0085")