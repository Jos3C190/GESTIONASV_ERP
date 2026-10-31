"""Use the configured local administrator without changing accounts or grants."""
import json
import os
from pathlib import Path

import httpx

with httpx.Client(base_url="http://localhost:8000/api/v1") as client:
    response = client.post("/auth/login", json={"login": os.environ.get("SUPER_ADMIN_USERNAME", "superadmin"), "password": os.environ.get("SUPER_ADMIN_PASSWORD", "")})
    if response.status_code == 200:
        target = Path("/tmp/block5-admin-auth.json")
        target.write_text(json.dumps(response.json()))
        target.chmod(0o600)
    print(f"Configured administrator login: {response.status_code}")
