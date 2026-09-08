"""Test suite for the ERP backend.

Layout:
- unit/         — pure-Python, no DB, no network (fast).
- integration/  — real Postgres (via the docker-compose `db` service or a
                  throwaway container spawned by the test profile).
- e2e/          — full FastAPI app via httpx.AsyncClient (no DB by default,
                  uses in-memory fakes / overrides).

Run:
    uv run pytest -ra --cov=app
"""
