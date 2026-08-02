# VIP Enterprise Permissions — Test Report

## Totals

| Suite | Command | Result |
|-------|---------|--------|
| Backend unit | `pytest -m "not integration"` | **180 passed**, 30 deselected |
| Backend integration | `pytest -m integration` (vip_test) | **31 passed**, 180 deselected |
| Backend integration (repeat) | second run (auth changed) | **31 passed** (stable) |
| Frontend unit/component | `npm run test` (vitest) | **218 passed** (38 files) |
| Static — ruff | `ruff check src tests` | pass |
| Static — format | `ruff format --check` | 198 files formatted |
| Static — mypy | `mypy src tests` | no issues (198 files) |
| Migration parity | `alembic check` | No new upgrade operations |
| Frontend typecheck | `npm run typecheck` (vue-tsc) | pass |
| Frontend lint | `npm run lint` (eslint) | pass |
| Frontend format | `npm run format:check` (prettier) | pass |
| Frontend build | `npm run build` (vite) | built successfully |
| Browser (Playwright, live personas) | — | **not executed this session** (see Limitations) |
| Accessibility (axe/Playwright) | — | **not executed this session** |

## Key test files (permissions)

### Backend unit
- `tests/unit/test_authorization_precedence.py` — locks the full precedence order: suspended, explicit-deny-over-super-admin, super-admin-over-archived, ownership, allow, role grant, expired.
- `tests/unit/test_resource_access.py` — pure evaluator (allow/deny/expiry/rank).
- `tests/unit/test_resource_access_service.py` — meta/overlay/role-level helpers.

### Backend integration (vip_test)
- `test_resource_permissions.py` — user grant → view; group grant → edit inheritance; dashboard `_access` overlay; explicit-deny override; revoke + simulate.
- `test_custom_roles.py` — create/update/clone; duplicate-name; privilege ceiling; system-role protection; direct + group role assignment resolves into `AuthorizationContext`; archive removes effective permissions; bulk assign per-item outcomes; tenant isolation.
- `test_resource_guard_enforcement.py` **(new this slice)** — pipeline explicit-deny enforcement end-to-end: baseline read allowed; developer-level deny blocks developer but not viewer read; viewer-level deny blocks read; **expired deny ignored**.

### Frontend
- `src/modules/access/access.service.spec.ts` **(extended this slice)** — 12 tests: groups CRUD + version guards, membership, principal search, grant/revoke, effective/simulate, **resource search**, **permission catalog + role list filters**, **create/clone/archive/delete role guards**, **assign/bulk-assign/unassign**.
- Existing component/service specs across 38 files remain green (218 total).

## Coverage mapping to Phase Q checklist

| Requirement | Covered by |
|-------------|-----------|
| Custom role validation / catalog / resolution | `test_custom_roles.py`, `access.service.spec.ts` |
| User + group assignments | `test_custom_roles.py` |
| Resource allow / deny / expiration | `test_resource_permissions.py`, `test_resource_guard_enforcement.py` |
| Ownership / suspended / archived / super-admin | `test_authorization_precedence.py` |
| Bulk validation | `test_custom_roles.py` |
| Tenant / cross-workspace isolation | `test_custom_roles.py`, `test_resource_permissions.py` |
| Dashboard / pipeline enforcement | `test_resource_permissions.py`, `test_resource_guard_enforcement.py` |
| Dataset / connection / semantic enforcement | service-level `enforce_resource_guard` (same guard proven by pipeline E2E; unit-level evaluator tests) |
| Cache invalidation | N/A — caching disabled (documented) |

## Gaps (honest)
- **Dataset/connection/semantic** enforcement shares the identical, proven `enforce_resource_guard` path but has a dedicated E2E test only for **pipeline**; per-type E2E tests are a recommended follow-up.
- **Browser/accessibility** live persona runs (super-admin, org/workspace admin, editor, operator, viewer, explicit-deny, group-granted, custom-role-granted, suspended) were **not** executed this session; they are required before a full "COMPLETE" verdict.

---

## Dataset / Connection / Semantic slice — test results

| Gate | Result |
|------|--------|
| `ruff check .` | pass |
| `ruff format --check .` | 228 files formatted |
| `mypy src tests` | Success: 204 files, no issues |
| `pytest -m "not integration"` | **196 passed** |
| `alembic upgrade head` + `alembic check` (fresh vip_test) | clean, no new operations |
| `pytest -m integration` — run 1 | **35 passed** |
| `pytest -m integration` — run 2 | **35 passed** |
| `npm run typecheck` / `lint` / `format:check` | pass |
| `npm run test` | **266 passed** (42 files) |
| `npm run build` | built |
| Live Chromium (admin/owner) | connection/dataset/semantic details carry `access`; no secrets; controls + Share gated by effective access |

**New tests:**
- `tests/integration/test_resource_authorization_domains.py` — dataset/connection/
  semantic: ACL elevation (no broad permission), explicit deny → 403, stranger →
  404, group-grant elevation, collection visibility (viewer sees only granted;
  deny/stranger see none; owner sees all; totals correct), expiration ignored,
  connection secrets absent, sharing authority (manage vs viewer), and the semantic
  **execution chokepoint** (denied/stranger raise before the secret provider is
  touched).
- `src/shared/lib/resourceAccess.spec.ts` — 6 unit tests for the shared
  effective-access mapper + `resourceCan`/`resourceDenied`/`canManageAccess`.
