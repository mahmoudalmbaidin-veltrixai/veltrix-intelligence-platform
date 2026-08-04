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

## 6a. Supply-chain gate (pip-audit) — cryptography CVE fix

The initial PR CI run failed **only** at `pip-audit -r requirements.lock`
(`backend-static-and-unit`); backend-integration, backend-container, frontend
static/unit, and browser all passed. The audit flagged three freshly-disclosed
2026 CVEs in the pinned `cryptography==48.0.1`:

```
cryptography 48.0.1  CVE-2026-69248  fix 49.0.0
cryptography 48.0.1  CVE-2026-69247  fix 50.0.0
cryptography 48.0.1  CVE-2026-69249  fix 49.0.0
```

These CVEs were published **after** the lock was pinned; the constraint
`cryptography>=48.0.1,<49` in `pyproject.toml` actively excluded the fix, so the
base branch fails identically on any re-run — this is a pre-existing, repo-wide
supply-chain issue, **not** introduced by the B9.1C code.

**Fix (isolated commit):** `pyproject.toml` → `cryptography>=50.0.0,<51`;
`requirements.lock` → `cryptography==50.0.0` (covers all three CVEs).

Re-validated with cryptography 50.0.0 installed:
- `pip-audit -r requirements.lock` → **No known vulnerabilities found**
- ruff ✓ · ruff format ✓ · mypy ✓
- connection-security unit tests ✓ (encryption/decryption unaffected)
- 240 unit ✓ · **58 integration ×2 both green** ✓

## 6b. Round 2 — gating, semantic audit, UX, live persona matrix

**Backend — semantic modeling audit trail** (`test_semantic_audit.py`, integration):
- `test_semantic_modeling_changes_are_audited` — the ten event types
  (dimension/measure/metric/KPI create/update/delete + `semantic_model.validated`)
  all persist against the parent model with actor/org/workspace/resource/entity,
  a correlation id, and before/after snapshots; asserts no secret or raw SQL is
  captured.
- `test_invalid_validation_is_audited_as_failure` — a model with no
  dimensions/metrics audits `semantic_model.validated` with `outcome=failure`.

**Backend — governance policy** (`test_governance_policies.py`) re-passes with the
new `insights`/`billing` capability keys and the trimmed default entitlements.

**Live Chromium — semantic persona matrix** (`tests/e2e/semantic-personas.spec.ts`,
chrome-desktop, against the seeded governance personas + a real semantic model):
```
ok  semantic personas render from backend-resolved effective access
ok  audit access and placeholder gating are persona-scoped
2 passed
```
- Manager/Owner holds the `manage` capability level and `can_manage_access`.
- Editor tops at `edit` (never `manage`); Viewer is read-only; the restricted
  persona is fail-closed (403/404 on detail + archive).
- Audit Center reachable with real events for a manager; the placeholder
  entitlements (`report_studio`/`insights`/`marketplace`/`billing`) are absent
  from `/authorization/context`, their nav is hidden, and audit read is denied
  for the restricted persona.

**Live Chromium — placeholder gating + smoke** (`tests/e2e/route-smoke.spec.ts`):
```
ok  disabled AI preview routes remain inaccessible in production navigation
ok  placeholder modules never render their surface in live mode
ok  all router destinations render an intentional nonblank surface ...
3 passed
```

**Accessibility + governance** (`accessibility.spec.ts`, `governance.spec.ts`,
chrome-desktop + chrome-high-dpi): `39 passed` — zero critical/serious axe
violations across protected routes (including `/developer` → the reframed upgrade
wall), and the persona nav/API fail-closed matrix intact.

The exhaustive semantic capability ladder (ACL elevation, group grants, expiry,
cross-tenant denial, and `execute_query` authorization for Studio/Explore/
dashboard paths) remains proven by
`tests/integration/test_resource_authorization_domains.py`.

> Note: the local live runs re-seed the demo personas with a known password and
> revoke the two placeholder entitlements (`report_studio`, `marketplace`) that
> older org rows still carried, so the running DB matches the new defaults. CI
> seeds a fresh database from the new code, so this state is the default there.

## 7. Summary

| Suite | Count | Status |
|-------|-------|--------|
| Backend static (ruff/format/mypy) | 3 gates | ✅ |
| Backend unit | 240 | ✅ |
| Backend integration (×2) | 60 ×2 | ✅ |
| Frontend typecheck/lint/format | 3 gates | ✅ |
| Frontend unit | 279 | ✅ |
| Frontend build | — | ✅ |
| Live MySQL discovery | happy + error | ✅ |
| Live Chromium — persona matrix + gating | 5 | ✅ |
| Accessibility + governance (axe) | 39 | ✅ |

(Backend unit 240 includes the 24-case MySQL discovery unit test; integration 60
= 58 + the 2 new semantic-audit tests. Confirmed by the gate run in §2–§4.)

All gates green. No flaky results across the two integration runs.
