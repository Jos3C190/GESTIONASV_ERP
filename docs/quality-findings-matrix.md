# Quality remediation matrix

This ledger contains only findings that were explicitly identified or
reproduced in the repository and local validation. No unverified findings or
placeholder rows are included.

The status values are: `Pendiente de validacion`, `En progreso`, and
`Cerrado`. A finding is closed only when its root cause, remediation, and
regression evidence are documented.

| ID | Finding | Severity | Area | Remediation | Status | Evidence |
|---|---|---|---|---|---|---|
| P1 | RBAC permissions absent from Alembic | P1 | 0044_purchase_requests.py / 0045_reconcile_purchase_request_permissions.py | Crear permisos idempotentemente y reconciliar SUPER_ADMIN, incluyendo bases que ya ejecutaron 0044. | Cerrado | `tests/integration/test_purchase_request_migration.py`: 5 passed; `0045` reconcilia permisos y grants en bases existentes. |
| P2 | Audit metadata causes strict Mypy failures | P2 | purchase_requests.py / audit_service.py | Use explicit Mapping[str, object] contract. | Cerrado | `mypy app`: no issues in 211 source files; purchase request tests included in backend suite. |
| W01 | Product identifier relationship warning | P2 | product_master.py | Correct relationship ownership/overlap. | Cerrado | `pytest -W error::sqlalchemy.exc.SAWarning`: no warning. |
| W02 | Product variant identifiers warning | P2 | product_variant.py | Correct relationship ownership/overlap. | Cerrado | `pytest -W error::sqlalchemy.exc.SAWarning`: no warning. |
| W03 | Variant attribute warning | P2 | product_variant.py | Correct relationship ownership/overlap. | Cerrado | `pytest -W error::sqlalchemy.exc.SAWarning`: no warning. |
| W04 | Variant value warning | P2 | product_variant.py | Correct relationship ownership/overlap. | Cerrado | `pytest -W error::sqlalchemy.exc.SAWarning`: no warning. |
| W05 | ORM mapper warning during application startup | P2 | SQLAlchemy mappings | Fail on SAWarning and test persistence. | Cerrado | Backend strict suite: 525 passed, 0 SAWarning. |
| W06 | ORM warning regression coverage | P2 | ORM integration tests | Add create/update/load/delete coverage. | Cerrado | Backend strict suite and purchase repository integration: 5 passed. |
| W07 | Warnings must not be globally filtered | P2 | pytest configuration | Keep strict warning policy. | Cerrado | Warning policy enforced in `scripts/run-tests.sh`; strict suite passes. |
| T01 | Purchase repository depends on canonical seed | P1 | test_purchase_request_repository.py | Create a typed self-contained ORM fixture. | Cerrado | Typed graph factory; isolated repository suite: 5 passed. |
| F01 | Frontend ESLint rejects process global | P2 | frontend/svelte.config.js | Use an explicit Node ESM environment import. | Cerrado | `pnpm lint` passed; production build uses adapter-node. |
| C01 | Supplier encryption key is blank in Compose | P1 | scripts/setup.sh / .env.example | Generate valid Base64URL 32-byte key locally and inject CI secret. | Cerrado | Setup generates Base64URL 32-byte key; Compose config validates with ephemeral key. |
| CI01 | Make test/lint omits quality gates | P1 | scripts/run-tests.sh / Makefile | Run strict pytest, OCR, Mypy, Ruff, ESLint and production build. | Cerrado | Runner includes backend/OCR/frontend tests, static checks and production build; Bash syntax validated. |

## Completion gate

All findings recorded in this matrix must be `Cerrado` with reproducible
evidence before merging into `develop`. Any additional finding must first be
added from a verifiable source with its identifier, root cause, remediation,
and validation evidence.

## Additional local regressions discovered during validation

- **E2E cleanup order** — fixed in `tests/e2e/conftest.py`; cleanup now removes
  purchase-request and location-batch rows before users while preserving the
  append-only audit log. Evidence: integration plus audit/employee E2E subset,
  `74 passed, 2 skipped` with `SAWarning` treated as an error.

- **Document services integration** — the two scenarios previously skipped by
  default were executed with `RUN_DOCUMENT_STORAGE_INTEGRATION=true` against
  the local RustFS/ClamAV stack. Evidence: `2 passed` with `SAWarning`
  treated as an error.
