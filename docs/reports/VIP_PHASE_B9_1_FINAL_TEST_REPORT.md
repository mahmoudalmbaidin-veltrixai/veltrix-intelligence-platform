# VIP Phase B9.1 — Final Test Report

**Date:** 2026-08-04
**Branch:** `phase-b9/connection-semantic-finalization`
**Scope:** B9.1C slice (MySQL discovery, semantic re-publish, audit canonicalization)
layered on the full B9.1A/B9.1B suites.

---

## 1. Backend static gates

| Gate | Command | Result |
|------|---------|--------|
| Lint | `ruff check .` | ✅ All checks passed |
| Format | `ruff format --check .` | ✅ 243 files formatted |
| Types | `mypy src tests` | ✅ no issues in 217 source files |

## 2. Backend unit tests

```
pytest -m "not integration" -q
240 passed, 58 deselected in 3.91s
```

New unit coverage this slice — `tests/unit/test_mysql_discovery.py` (24 cases):
- `normalize_mysql_type` mapping across all MySQL type families + unknown fallback
- case-insensitivity
- `MySQLDiscoveryAdapter._allowed` object/type include/exclude filtering
- adapter registration in `MetadataDiscoveryAdapterRegistry`

## 3. Migrations (fresh isolated `vip_test`)

Database dropped with FORCE and recreated before migrating.

```
alembic upgrade head   → head 20260803_0019 (Dataset certification metadata, B9.1B)
alembic check          → No new upgrade operations detected
```

No additive migration was required for this slice (MySQL discovery, semantic
re-publish, and audit canonicalization introduce no schema changes).

## 4. Backend integration tests — run TWICE, both green

Environment: `DATABASE_URL=…/vip_test`, `REDIS_URL=redis://localhost:6379/15`,
`APP_ENV=test`, `RUN_INTEGRATION_TESTS=1`.

```
Integration run #1:  58 passed, 240 deselected in 46.50s
Integration run #2:  58 passed, 240 deselected in 45.86s
```

New integration coverage this slice — `tests/integration/test_semantic_republish.py`:
- `test_semantic_model_can_be_published_repeatedly` — publish v1 → edit → v2 →
  edit → v3; asserts three immutable `SemanticModelVersion` rows numbered
  [1,2,3], each with a frozen definition snapshot; a clean published model
  rejects re-publish with `SEMANTIC_MODEL_NOT_DRAFT`.
- `test_unauthorized_caller_cannot_publish_semantic_model` — an outsider with no
  membership/ACL is denied (`NOT_FOUND`), and no version row leaks.

## 5. Live MySQL discovery (real container — primary evidence)

Executed inside the `api` container against the real `mysql` service (profile
`connectors`), **not** mocked:

```
# Happy path
OK objects=1 truncated=False
  - vip_demo.customers [table] fields=4
    sample=[('id','int','integer'), ('name','varchar','string'), ('email','varchar','string')]

# Honest error path (bad credentials)
bad-creds -> DISCOVERY_FAILED status=502  (secret not echoed)
```

## 6. Frontend gates

| Gate | Command | Result |
|------|---------|--------|
| Types | `npm run typecheck` (vue-tsc) | ✅ pass |
| Lint | `npm run lint` (eslint) | ✅ pass |
| Format | `npm run format:check` (prettier) | ✅ all files styled |
| Unit | `npm run test` (vitest) | ✅ 45 files, 279 tests passed |
| Build | `npm run build` (vite) | ✅ built in 4.82s |

The audit URL contract (`apiClient.services-url.spec.ts`) now asserts
`/audit-events` resolves to a single `/api/v1/audit-events` under both host-only
and version-prefixed base forms.

## 7. Summary

| Suite | Count | Status |
|-------|-------|--------|
| Backend static (ruff/format/mypy) | 3 gates | ✅ |
| Backend unit | 240 | ✅ |
| Backend integration (×2) | 58 ×2 | ✅ |
| Frontend unit | 279 | ✅ |
| Frontend build | — | ✅ |
| Live MySQL discovery | happy + error | ✅ |

All gates green. No flaky results across the two integration runs.
