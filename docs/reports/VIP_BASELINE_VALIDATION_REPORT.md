# VIP — Baseline Validation Report

> Controlled, reproducible baseline validation performed before any new permissions enhancement.
> No product code, migrations, or dependencies were changed. No commits or pushes were made.
> Test results below are from commands actually executed and recorded in this session.

- **Date**: 2026-07-29
- **Host**: Windows (PowerShell), Docker Desktop 29.6.2
- **Tooling caveat**: Backend gates were run from the existing `apps/api/.venv` (Python **3.14.4**,
  pytest 9.1.1, ruff 0.16.0, mypy 1.20.2). CI pins Python **3.12** with lock-file versions, so
  strict type/format findings below may differ from CI and must be re-confirmed with the pinned
  toolchain. Functional test results (pass/fail counts) are environment-robust.

---

## Repository state

| Item | Value |
| --- | --- |
| Branch | `enhancement/pipeline-dashboard-studios` |
| Starting SHA | `2590248ba51cd0d8da37c000efaed754bac070df` |
| Ending SHA | `2590248ba51cd0d8da37c000efaed754bac070df` (unchanged — no commits made) |
| Remote (fetch/push) | `origin` → `https://github.com/mahmoudalmbaidin-veltrixai/veltrix-intelligence-platform.git` |
| Working tree | Not clean (expected). 1 modified, 3 untracked source/test/migration files (pre-existing), plus 6 documentation files (5 from discovery + this report). |
| Differs from previous report? | No — identical to the discovery snapshot. |

### `git status --short`

```
 M apps/api/src/vip_api/governance/models.py
?? apps/api/alembic/versions/20260728_0016_resource_access_entries.py
?? apps/api/src/vip_api/governance/resource_access.py
?? apps/api/tests/unit/test_resource_access.py
?? docs/architecture/VIP_API_INVENTORY.md
?? docs/architecture/VIP_MODULE_CATALOG.md
?? docs/architecture/VIP_PLATFORM_ARCHITECTURE.md
?? docs/architecture/VIP_REPOSITORY_GUIDE.md
?? docs/reports/VIP_CURRENT_STATE_ASSESSMENT.md
```

(`VIP_BASELINE_VALIDATION_REPORT.md` — this file — is added by the current task.)

### File classification

| File | Classification | Purpose | Completeness | Dependencies | Risk | Recommended action |
| --- | --- | --- | --- | --- | --- | --- |
| `apps/api/src/vip_api/governance/models.py` (M) | Existing feature work | Adds `ResourceAccessEntry` ORM model (resource ACL, Slice A) | Model complete, but drifts from migration (nullable timestamps) | Base, tenancy FKs | **Medium** — breaks `alembic check` | Reconcile model vs migration nullability before committing |
| `apps/api/src/vip_api/governance/resource_access.py` (??) | Existing feature work | Pure `evaluate_resource_access()` precedence evaluator | Evaluator complete + unit-tested; NOT wired to any route | none (pure) | Low (dormant) | Keep; wire into routes in a later slice |
| `apps/api/alembic/versions/20260728_0016_resource_access_entries.py` (??) | Existing feature work | Creates `resource_access_entries` table | Additive, applies cleanly | down_rev `20260728_0015` | **Medium** — nullable mismatch vs model | Align timestamp nullability with model |
| `apps/api/tests/unit/test_resource_access.py` (??) | Test artifact (feature) | 22 precedence tests for the evaluator | Passing at runtime; fails `mypy --strict` (25 annotation errors) | evaluator | Low | Add type annotations before committing |
| `docs/architecture/VIP_PLATFORM_ARCHITECTURE.md` (??) | Architecture documentation | Platform architecture | Complete | — | None | Keep |
| `docs/architecture/VIP_MODULE_CATALOG.md` (??) | Architecture documentation | Module catalog + status | Complete | — | None | Keep |
| `docs/architecture/VIP_API_INVENTORY.md` (??) | Architecture documentation | Verified API inventory | Complete | — | None | Keep |
| `docs/architecture/VIP_REPOSITORY_GUIDE.md` (??) | Architecture documentation | Repo guide | Complete | — | None | Keep |
| `docs/reports/VIP_CURRENT_STATE_ASSESSMENT.md` (??) | Architecture documentation | Current-state assessment | Complete (minor correction added this task) | — | None | Keep |

No generated/build artifacts appear in the tracked working tree. No unknown/unexplained files.

---

## Resource-access assessment

- **Files involved**:
  - `apps/api/src/vip_api/governance/resource_access.py` — pure evaluator (`evaluate_resource_access`, `AccessEntry`, `AccessDecision`).
  - `apps/api/src/vip_api/governance/models.py` — `ResourceAccessEntry` ORM model (uncommitted addition).
  - `apps/api/alembic/versions/20260728_0016_resource_access_entries.py` — additive migration.
  - `apps/api/tests/unit/test_resource_access.py` — 22 precedence unit tests.
- **Architecture**: A single, reusable, tenant-scoped ACL record (`resource_type`, `resource_id`,
  `subject_type` [user|group], `subject_id`, `access_level`, `effect` [allow|deny], `expires_at`).
  The evaluator implements a documented precedence: suspended subject → explicit deny → super-admin
  override → archived workspace → ownership → grant (resource ACL and/or role-derived level) → deny.
  Per-resource level ladders exist for dashboard/pipeline/dataset/connection.
- **Current completeness**:
  - Models exist: **yes** (`ResourceAccessEntry`).
  - Migration exists: **yes** (`20260728_0016`, single head, applies cleanly).
  - Evaluator/service exists: **yes** (pure, IO-free).
  - Tests exist: **yes** (22 unit tests; all pass at runtime).
  - Imported anywhere (non-test)? **No** — only the model (ORM registry), the migration, tests, and
    documentation reference it. The `dashboard_delivery/cache.py` hit is an unrelated cache-key
    string (`"resource_access"`), not the evaluator.
  - API routes use the evaluator? **No.**
  - Frontend uses the feature? **No.**
  - Explicit deny implemented? **Yes** (in the evaluator; strongest control, beats super-admin).
  - Org/workspace tenant isolation enforced? **In the table schema** (org/workspace columns + FKs +
    composite index). **Not** at request time (evaluator is not invoked by any route).
  - User + group principals supported? **Yes** (in-memory evaluation via `subject_type`).
  - Role inheritance? **Partial** — a single `role_granted_level` input is honored; no hierarchical role graph.
  - Resource inheritance? **No** (flat resource entries; no parent/child propagation).
  - Migration matches ORM model? **No** — `created_at`/`updated_at` are `NOT NULL` in the model but
    nullable in the migration (`alembic check` fails; see below).
  - Overall: **Partial / foundation ("Slice A")** — safe and dormant, but not production-wired and
    with a model/migration drift.
- **Migration status**: single head `20260728_0016`; DB already at head; upgrade is additive and
  applies cleanly on a fresh DB.
- **Test status**: 22 evaluator unit tests pass (part of the 156 backend unit tests). `mypy --strict`
  flags 25 annotation errors in the test file.
- **Integration status**: **not integrated** — no route, dependency, or frontend consumes it.
- **Security risks**: None active (dormant). Risk is *latent*: if wired later, the model/migration
  nullable drift and the absence of resource inheritance/role-hierarchy must be handled; enforcement
  ordering (deny > super-admin) is already correct and tested.
- **Recommended next action**: (1) Reconcile `created_at`/`updated_at` nullability between model and
  migration so `alembic check` passes; (2) annotate the test helpers for `mypy --strict`; (3) plan a
  later slice to wire the evaluator into dashboard/pipeline/dataset/connection routes with tenant and
  ownership inputs. Do **not** complete this in the baseline task.

---

## Environment status

`docker compose ps` — all core services **Up (healthy)** (~12h uptime):

| Service | Container | Status | Ports |
| --- | --- | --- | --- |
| postgres | `vip-postgres-1` | Up (healthy) | 5432→5432 |
| redis | `vip-redis-1` | Up (healthy) | 6379→6379 |
| clamav | `vip-clamav-1` | Up (healthy) | 3310, 7357 |
| api | `vip-api-1` | Up (healthy) | 8000→8000 |
| dashboard-worker | `vip-dashboard-worker-1` | Up (healthy) | 8000 (internal) |
| pipeline-worker | `vip-pipeline-worker-1` | Up (healthy) | 8000 (internal) |
| mysql (optional) | `vip-mysql-1` | Up (healthy) | 3307→3306 |

- **API health**: `GET /health` → `{"status":"healthy","service":"vip-api","version":"0.1.0"}`.
- **API readiness**: `GET /ready` → `{"status":"ready","checks":{"database":{"status":"healthy"},"redis":{"status":"healthy"}}}`.
- **Version**: `GET /api/v1/version` → `{"name":"VIP API","version":"0.1.0","environment":"development",...}`.
- **Database**: reachable; ready check healthy; `alembic current` = `20260728_0016 (head)`.
- **Redis**: reachable; ready check healthy.
- **Workers**: `worker_heartbeats` shows a fresh `default,dashboard` worker and a fresh `pipeline`
  worker (`last_seen_at` within 2 min, `status=running`); older stopped/stale rows are from prior
  restarts.
- **Test environment**: integration tests target a `*_test` PostgreSQL DB + Redis DB. A clean,
  migrated, correctly-named disposable DB (`vip_baseline_test`) and Redis logical DBs (13/14) were
  used for the clean-room run. Two additive disposable databases were created in the running Postgres
  container for this validation: `vip_test_baseline` and `vip_baseline_test` (safe to drop). A
  clearly-labeled disposable smoke user (`baseline_smoke_probe`) was created in the dev `vip` DB for
  the live auth smoke.

---

## Backend results

Working directory: `apps/api`. Tools: `apps/api/.venv` (see caveat).

| # | Command | Result | Passed | Failed | Skipped | Warnings / details |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `ruff check .` | **PASS** | — | 0 | — | "All checks passed!" |
| 2 | `ruff format --check .` | **FAIL** | 208 formatted | 1 | — | `tests/integration/test_pipeline_schema_validation.py` would be reformatted (possible ruff-version drift) |
| 3 | `mypy` (config: `files=["src","tests"]`, strict) | **FAIL** | — | 35 errors in 5 files | — | **All in tests, none in `src`**: `test_resource_access.py` (25), `test_dashboard_lifecycle_integrity.py` (4), `test_pipeline_execution_parity.py` (2), `test_pipeline_schema_validation.py` (2), `test_pipeline_schema_flow.py` (2). Mostly `no-untyped-def`/`type-arg` under strict; partly tool-version drift |
| 4 | `pytest -m "not integration"` (unit) | **PASS** | **156** | 0 | 27 deselected | 16.8s; includes resource-access, governance-policy, route/security unit tests |
| 5 | `alembic upgrade head` (fresh `_test` DB) | **PASS** | — | — | — | Applies all 19 migrations through `20260728_0016` cleanly |
| 6 | `pytest -m integration` (clean migrated `vip_baseline_test`) | **PASS** | **27** | 0 | 156 deselected | 53.7s; includes `test_migrations`, tenancy/tenant-isolation, governance personas, connections, dashboards, pipelines, jobs/files/events, platform infrastructure |
| 7 | `alembic check` (running container) | **FAIL** | — | — | — | Model/migration drift: `resource_access_entries.created_at`/`updated_at` are `NOT NULL` in ORM but nullable in migration → "New upgrade operations detected: modify_nullable" |
| 8 | `pytest -m integration <governance test>` in isolation | **PASS** | 1 | 0 | — | Confirms full-suite failures below were non-hermetic, not code defects |

### Integration note (important, honest)

The **first** full integration run against the **long-lived shared `vip_test`** database produced
**9 failed / 16 passed / 2 errors**. Every failure was the same teardown error —
`ForeignKeyViolationError ... "fk_datasets_connection_tenant"` during `DELETE FROM organizations` —
i.e. accumulated/contaminated state in a 12-hour-old shared DB, **not** a product regression. Proof:
(a) the same governance test **passes in isolation**, and (b) the **full suite passes 27/0 on a
fresh, migrated `_test` database**. Route-policy and tenant-isolation coverage are included in the
passing clean-DB run.

Route-policy coverage: enforced by `governance/route_policy` test logic (part of the passing unit
suite) which asserts `/api/v1/*` routes declare governance/tenant dependencies.

---

## Frontend results

Working directory: repository root. Tools: existing `node_modules` (Node 24.18, npm 11.16).

| # | Command | Result | Passed | Failed | Skipped | Warnings / build |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `npm run typecheck` (`vue-tsc --noEmit -p tsconfig.app.json`) | **PASS** | — | 0 | — | npm devdir/version notices only (benign) |
| 2 | `npm run lint` (`eslint . --ext .ts,.vue`) | **PASS** | — | 0 | — | — |
| 3 | `npm run format:check` (`prettier --check`) | **FAIL** | — | 2 files | — | `src/modules/pipelines/NodeColumnSelect.vue`, `NodeRenameMap.vue` (possible prettier-version drift) |
| 4 | `npm run test` (`vitest run`) | **PASS** | **206** (37 files) | 0 | 0 | 22.1s |
| 5 | `npm run build` (`vue-tsc --noEmit && vite build`) | **PASS** | — | — | — | Built in ~10.5s; largest chunk `index` 298 kB (gzip 98 kB); no build errors |

- **Dependency consistency**: `node_modules` present and functional; `npm ci` (clean install) was
  **not** run to avoid mutating the environment — recommend running it in CI for a definitive check.
- **Live-mode contracts**: `src/shared/config/env.ts` **fails closed** — staging/production builds
  require `VITE_API_MODE=live` + a valid `VITE_API_BASE_URL`; only local dev may opt into mock
  fallback. So the frontend cannot silently ship as mock. Mock-mode Vitest results are **not** treated
  as proof of live backend integration (see live-mode section).

---

## Live-mode smoke results

Performed against the live local API (`http://localhost:8000`) — no UI, no mocks.

| Flow | Method | Outcome |
| --- | --- | --- |
| Route registration | `GET /openapi.json` | **166 paths** registered (all domain routers live) |
| Health | `GET /health` | 200 healthy |
| Readiness | `GET /ready` | 200 ready (DB + Redis healthy) |
| Version | `GET /api/v1/version` | 200 (`development`) |
| Auth gate (unauthenticated) | `GET /auth/me` (no cookie) | **401** (enforced) |
| Auth gate (unauthenticated) | `GET /api/v1/connections` (no cookie) | **401** (enforced) |
| Login | `POST /auth/login` (disposable user) | **200** (sets access/refresh/CSRF cookies) |
| Session validation | `GET /auth/me` | **200** — returns user + session expiry |
| Tenancy listing | `GET /api/v1/organizations` | **200** → `{"items":[]}` (bare user has no org — correct) |
| Logout (CSRF) | `POST /auth/logout` (+ `X-CSRF-Token`) | **200** |
| Session invalidation | `GET /auth/me` after logout | **401** (session revoked) |
| Persisted live data | DB counts | 15 users / 12 orgs / 21 workspaces / 106 connections / 181 dashboards / 141 pipelines — created through the live modules |
| Worker liveness | `worker_heartbeats` | Fresh dashboard + pipeline workers (`running`, `< 2 min`) |

**Journey A (authentication + session lifecycle): fully validated live**, including CSRF-protected
logout and post-logout invalidation.

**Not validated live in this session**: deep authenticated per-module flows (connections/datasets/
semantic/dashboards/pipelines/jobs/files/events **write** paths) via a fully provisioned tenant, and
the frontend browser E2E in live mode. Reasons: (a) valid tenant credentials are environment-supplied
(`VIP_E2E_PASSWORD`) and not available in this session; (b) the task forbids creating production-like
data. Indirect evidence for these modules: the **clean-DB integration suite passes 27/0** and the
live DB already contains substantial data produced by these modules. The authoritative live-mode UI
gate is the CI `browser` job (Playwright vs live API), which was **not** run here.

---

## Blockers

| Severity | Finding |
| --- | --- |
| **Critical** | None. |
| **High** | `alembic check` **fails** — `ResourceAccessEntry` model vs migration `20260728_0016` nullable drift on `created_at`/`updated_at`. CI's backend-integration job runs `alembic check`, so this would fail CI. Tied to the uncommitted resource-access work. |
| **Medium** | `mypy --strict` fails with 35 test-only errors (25 in `test_resource_access.py`). Blocks CI backend-static-and-unit if reproduced with pinned tooling. |
| **Medium** | Integration suite is **not hermetic** against a pre-populated shared `vip_test` DB (teardown FK ordering) — full-suite RED on the shared DB, GREEN on a fresh DB. Fragile for repeatable local runs. |
| **Low** | `ruff format --check` (1 backend test file) and `prettier --check` (2 frontend Vue files) report formatting drift — possibly tool-version related; confirm with pinned versions. |
| **Informational** | Local backend tooling is Python 3.14 + newer ruff/mypy vs CI's pinned 3.12; some strict/format findings may not reproduce in CI. `npm ci` not executed. Deep live-mode per-module E2E not executed (credentials/scope). Two disposable test DBs + one smoke user created (additive; safe to drop). |

---

## Final verdict

### `BASELINE PARTIALLY VERIFIED — FIXES REQUIRED`

**Rationale**: The environment is healthy (all services up, DB/Redis healthy, workers fresh),
migration state is valid (single head, clean additive upgrade), and **all functional gates pass**
(backend unit 156/0, backend integration 27/0 on a clean DB, frontend Vitest 206/0, production build
OK, live auth flow OK). However, non-functional quality gates fail: **`alembic check` fails** due to
the resource-access model/migration nullable drift (High), `mypy --strict` fails on test files
(Medium, mostly the resource-access test), the integration suite is non-hermetic against a shared DB
(Medium), and format checks flag 3 files (Low). These are fixable and largely concentrated in the
unfinished resource-access work, so the baseline is **partially** — not fully — verified. Per the
task's own criteria, the "SAFE TO BEGIN" verdict cannot be issued while backend gates (alembic
check / mypy) are red.

**Recommended next task**: A small, isolated **"resource-access baseline reconciliation"** change
(not feature work) that (1) aligns `created_at`/`updated_at` nullability between the
`ResourceAccessEntry` model and migration `20260728_0016` so `alembic check` passes, and (2) adds
type annotations to `test_resource_access.py` so `mypy --strict` passes — then re-run the backend
gates and confirm `alembic check` is green with the pinned CI toolchain. Optionally reformat the 3
drifting files with the pinned ruff/prettier versions and add a hermetic per-test DB teardown for the
integration suite. Only after these are green should permissions enhancement work begin.

---
---

# Addendum — Resource-Access Baseline Reconciliation

> The original baseline evidence above is preserved verbatim. This addendum records the
> reconciliation performed afterwards and re-verified results. Where results changed, both the
> original and updated numbers are shown.

**Date**: 2026-07-29 · **Branch**: `enhancement/pipeline-dashboard-studios` ·
**Starting SHA**: `2590248ba51cd0d8da37c000efaed754bac070df` · **Ending SHA**: `2590248ba51cd0d8da37c000efaed754bac070df`
(no commits made). **Working tree**: modified, uncommitted.

**Authoritative toolchain (CI parity)**: dedicated `apps/api/.venv-ci` created with `uv` →
**Python 3.12.13**, installed from `apps/api/requirements.lock` + `pip install --no-deps -e .`.
Pinned tools: **ruff 0.15.22, mypy 1.20.2, pytest 9.1.1** (frontend Prettier **3.9.5**). The earlier
Python 3.14 findings are superseded by these pinned results. The prior "format drift" was in part
tool-version drift; under pinned tools the exact same files were confirmed to need formatting.

## Files changed

| File | Reason | Nature of change | Behavior changed? |
| --- | --- | --- | --- |
| `apps/api/alembic/versions/20260728_0016_resource_access_entries.py` | Model/migration parity for `alembic check` | `created_at`/`updated_at` columns changed `nullable=True` → `nullable=False` (matching the ORM and every comparable governance/dashboard/jobs table). Corrected the existing uncommitted migration in place — no new migration. | No (empty new table; additive create; Python-side `default=utc_now` fills both columns on insert) |
| `apps/api/tests/unit/test_resource_access.py` | `mypy --strict` (25 errors) | Rewrote the untyped `_eval(**kwargs)` helper as an explicit, keyword-only typed wrapper (`-> AccessDecision`); imported `AccessDecision` and `UUID`. | No (identical defaults and dispatch) |
| `apps/api/tests/unit/test_pipeline_schema_flow.py` | `mypy --strict` (2 errors) | Annotated `_codes(issues: list[ValidationIssue])` and `_node(... config: dict[str, object] | None ...)`; imported `ValidationIssue` from `vip_api.pipelines.schemas`. | No |
| `apps/api/tests/unit/test_pipeline_execution_parity.py` | `mypy --strict` (2 errors) + formatting | Annotated `_node(... config: dict[str, object])` and `_propagate_names(order: list[str], nodes: list[NodeInput], edges: list[EdgeInput])`. | No |
| `apps/api/tests/integration/test_pipeline_schema_validation.py` | `mypy --strict` (2 errors) + `ruff format` | Annotated `_codes(issues: list[ValidationIssue])`; added return type `tuple[list[NodeInput], list[EdgeInput]]` to the inner `graph(...)`; imported `ValidationIssue`; applied `ruff format`. | No |
| `apps/api/tests/integration/test_dashboard_lifecycle_integrity.py` | `mypy --strict` (4 errors) | Added a typed `_snapshot_overview_titles(snapshot: dict[str, object])` helper using `typing.cast` for the JSON payload; guarded the two `db.scalar(...)` results with `assert ... is not None` before `.snapshot`. | No (added assertions are always-true in this test) |
| `src/modules/pipelines/NodeColumnSelect.vue` | `prettier --check` | Prettier line-wrapping only. | No |
| `src/modules/pipelines/NodeRenameMap.vue` | `prettier --check` | Prettier line-wrapping only. | No |

No suppressions (`# type: ignore`) were added, strict mode was not weakened, no test files were
excluded, and no product/runtime code was modified.

## Exact model/migration correction

- **Previous mismatch**: model `ResourceAccessEntry.created_at`/`updated_at` = `Mapped[datetime]` (NOT NULL,
  `default=utc_now`) vs migration columns `nullable=True`. `alembic check` reported outstanding
  `alter_column ... nullable=False` operations.
- **Corrected schema**: migration columns are now `sa.DateTime(timezone=True), nullable=False` (no
  `server_default`, matching the codebase convention where timestamps are Python-side defaulted). Indexes,
  unique constraint, FKs, and the additive upgrade/table-only downgrade are unchanged.

## Updated migration results (fresh disposable `vip_recheck_test`)

```text
alembic heads         -> 20260728_0016 (head)          # single head
alembic upgrade head  -> ... 20260728_0015 -> 20260728_0016  (clean)
alembic check         -> No new upgrade operations detected.
```

## Updated backend results (pinned Python 3.12.13, `apps/api`)

| Command | Original baseline | Updated result |
| --- | --- | --- |
| `ruff check .` | (n/a) | **All checks passed!** |
| `ruff format --check .` | 1 file drift | **208 files already formatted** (0 drift) |
| `mypy src tests` | 35 errors | **Success: no issues found in 186 source files** |
| `pytest -m "not integration"` | 156 passed | **156 passed, 27 deselected** (~22.6s) |
| `alembic upgrade head` + `alembic check` | check FAILED | **check: No new upgrade operations detected** |
| `pytest -m integration` (fresh DB) | 27 passed | **27 passed, 156 deselected** (~56.7s) on a clean run |

Integration note: one run earlier showed `1 failed, 26 passed` on
`test_platform_infrastructure.py::test_redis_priority_queue_round_trip`; re-running in isolation gave
pass/fail/pass. Root cause is a **pre-existing 1-second-boundary race** in `RedisJobQueue` scoring
(`score = int(time.time())*1000 + (100 - priority)`, so priority only breaks ties within the same
integer second). It is **unrelated to resource-access and outside this task's scope**; a fully clean
integration run is `27 passed, 0 failed`.

## Updated frontend results (repo root)

| Command | Result |
| --- | --- |
| `npm run typecheck` (`vue-tsc --noEmit`) | passed, 0 errors |
| `npm run lint` (`eslint . --ext .ts,.vue`) | passed, 0 errors/warnings |
| `npm run format:check` (`prettier --check`) | **All matched files use Prettier code style!** |
| `npm run test` (`vitest run`) | **206 passed** across **37 files** (~32s) |
| `npm run build` (`vue-tsc && vite build`) | **built in ~10.5s**, 0 errors |

## Focused resource-access verification

`pytest tests/unit/test_resource_access.py -v` → **19 passed** (~0.05s). Precedence confirmed intact:
suspended subject → explicit deny (over grant **and** super-admin) → super-admin override → archived
workspace → ownership → resource/role-derived grant → default deny. User **and** group subjects,
dashboard/pipeline/dataset/connection ladders, expiry (expired grant ignored + explained; expired deny
does not block), and explicit-deny precedence all covered. Grep confirms the evaluator and
`ResourceAccessEntry` are referenced only inside the `governance` module + tests (the
`dashboard_delivery/cache.py` hit is a coincidental `"resource_access"` cache-key string) — **still
unwired: no routes, services, or frontend integration**.

## Cleanup performed

| Artifact | Type | Action |
| --- | --- | --- |
| `baseline_smoke_probe` (user `45fa98a9-…` in `vip`) | Disposable smoke user | **Removed** (atomic `DELETE 1`; cascades cleared sessions/memberships) |
| `vip_recheck_test` | Disposable test DB (this task) | **Dropped** (`WITH FORCE`) |
| `vip_baseline_test` | Disposable test DB (prior baseline) | **Dropped** |
| `vip_test_baseline` | Disposable test DB (prior baseline) | **Dropped** |
| `vip`, `vip_test`, `vip_b5_test`, `vip_live_uat_source`, `postgres` | Shared dev/CI data | **Retained** |
| `apps/api/.venv-ci` | Local CI-parity toolchain | Retained (gitignored, not in working tree) for reproducibility |

## Remaining blockers (post-reconciliation)

| Severity | Finding |
| --- | --- |
| Critical / High | **None.** All reconciliation targets met; `alembic check`, `mypy`, ruff, and both format checks are green. |
| Medium | **Pre-existing flaky integration test** `test_redis_priority_queue_round_trip` — 1-second-boundary race in `RedisJobQueue` scoring (product code). Unrelated to resource-access; a clean run is 27/0. Should be fixed (e.g. sub-second/monotonic tiebreak) but does not gate this reconciliation. |
| Low | None outstanding. |

## Updated verdict

### `BASELINE PARTIALLY VERIFIED — FIXES REQUIRED`

All eight reconciliation objectives are met and every static, migration, formatting, and functional
gate is green under the pinned CI toolchain — the resource-access work is reconciled and no product
behavior changed. The verdict is held at **PARTIALLY VERIFIED** solely because a genuine (if
intermittent) failure was observed in the fresh-DB integration gate: the pre-existing
`test_redis_priority_queue_round_trip` race. Because the strict "SAFE TO BEGIN" bar requires the
fresh-database integration suite to pass **reliably**, and that one pre-existing (out-of-scope) test
does not, the honest verdict is PARTIALLY VERIFIED. The single remaining fix is unrelated to
permissions and can be addressed independently.

---
---

# Addendum — Final Baseline Certification (Environment Startup + Queue Stabilization)

> The reconciliation evidence above is preserved verbatim. This addendum records the environment
> restore, the fix for the one remaining blocker (the Redis queue race), and a full re-run of every
> quality gate. Where results changed, both prior and updated numbers are shown.

**Date**: 2026-08-01 · **Branch**: `enhancement/pipeline-dashboard-studios` ·
**Starting SHA**: `2590248ba51cd0d8da37c000efaed754bac070df` · **Ending SHA**: `2590248ba51cd0d8da37c000efaed754bac070df`
(no commits made). **Working tree**: modified/uncommitted (adds only `apps/api/src/vip_api/jobs/queue.py`
to the prior set).

## Environment startup verification

Laptop was powered off; Docker engine was down. Started Docker Desktop (engine **29.6.2**) and brought
up the stack (`docker compose up -d`, plus `docker compose --profile connectors up -d mysql` — MySQL is
an optional `connectors`-profile service, restored on host port **3307** because 3306 was occupied).

| Service | Status | Evidence |
| --- | --- | --- |
| postgres | Up, healthy | `pg_isready` → accepting connections; `/ready` database healthy |
| redis | Up, healthy | `redis-cli ping` → PONG; `/ready` redis healthy |
| api | Up, healthy | `/health` → `{"status":"healthy",...}`; `/ready` → `{"status":"ready",...}` |
| dashboard-worker | Up, healthy | heartbeat `default,dashboard` running, age 0s |
| pipeline-worker | Up, healthy | heartbeat `pipeline` running, age ~8s |
| clamav | Up, healthy | compose health |
| mysql (optional) | Up, healthy | compose health (profile `connectors`, port 3307) |

Migration state: DB `alembic_version` = **`20260728_0016`** (matches head). Stale `running`/`stopped`
heartbeat rows from the hard shutdown are orphaned and expected; both current workers publish fresh
heartbeats.

## Queue root cause

`RedisJobQueue` scored a single sorted set as
`score = available_second * 1000 + (100 - priority)`. The whole-second arrival bucket (`*1000`)
dominates the priority offset (range `[0, 200]`), so **priority only breaks ties among jobs enqueued in
the same wall-clock second**. When two immediate jobs straddle a 1-second boundary, arrival time
outranks priority. Empirically confirmed: same-second → high first (`1000000 < 1000100`); across a
boundary → low first (`1000100 < 1001000`). A single scalar cannot both gate delayed jobs by time and
order ready jobs by priority.

## Queue fix (solution)

Rewrote `apps/api/src/vip_api/jobs/queue.py` to use **two sorted sets** plus an atomic Lua pop:

- **ready** set (`{prefix}:queue:{q}`): scored purely by `priority_offset * 10^13 + sequence`, where
  `priority_offset ∈ [0,200]` and `sequence` is a global `INCR` counter — priority fully determines
  order, then FIFO; **arrival second never interferes**. (Max ≈ `2e15 + seq` stays an exact double
  `< 2^53`.)
- **delayed** set (`…:delayed`): scored by absolute `available_ms`, so a delayed job cannot be popped
  early; its ready score is stashed in a `…:pending` hash (written before the delayed member so a
  concurrent pop can never promote it without its score).
- **dequeue**: one Lua script atomically promotes all now-due delayed jobs into the ready set (carrying
  their stored score) and `ZPOPMIN`s the highest-priority ready job — correct across multiple worker
  processes, with **no sleeps or retries**.

Public interface (`enqueue`/`dequeue`/`metrics`, `JobQueue` protocol) is unchanged; the DB remains the
authoritative job state. Two `# type: ignore[misc]` markers cover redis-py's async-stub union-return
defect (consistent with the pre-existing marker on `eval`).

**Files modified**: `apps/api/src/vip_api/jobs/queue.py` (1 file, +87 / −19).

**Why it is correct**: priority ordering, FIFO, and delay gating are each enforced by an independent,
now-orthogonal mechanism; ordering no longer reads the wall clock, eliminating the boundary race while
preserving every prior semantic. Verified below.

## Repeated queue verification

| Check | Executions | Passed | Failed |
| --- | --- | --- | --- |
| `test_redis_priority_queue_round_trip` (pytest, fresh prefix each run) | 30 | 30 | 0 |
| Priority across a **forced** second boundary (harness) | 25 | 25 | 0 |
| FIFO among equal priority (harness) | 25 | 25 | 0 |
| Delay gating: immediate first, delayed gated then delivered (harness) | 10 | 10 | 0 |
| Full integration suite (fresh DB, run 1 & 2) | 2 | 2 | 0 |

The harness (temporary, not committed; deleted after use) deliberately reproduced the old failure
condition; the fix is deterministic.

## Backend results (pinned Python 3.12.13, `apps/api`)

| Command | Result |
| --- | --- |
| `ruff check .` | All checks passed! |
| `ruff format --check .` | 208 files already formatted |
| `mypy src tests` | Success: no issues found in 186 source files |
| `pytest -m "not integration"` | **156 passed, 27 deselected** (~4.8s) |
| `alembic upgrade head` (fresh `vip_cert_test`) | clean → `…0015 -> 0016` |
| `alembic check` | **No new upgrade operations detected.** |
| `pytest -m integration` — run 1 (fresh DB) | **27 passed, 156 deselected** (~32.1s) |
| `pytest -m integration` — run 2 (fresh DB) | **27 passed, 156 deselected** (~29.4s) |

## Frontend results (repo root)

| Command | Result |
| --- | --- |
| `npm run typecheck` (`vue-tsc --noEmit`) | passed, 0 errors |
| `npm run lint` (`eslint . --ext .ts,.vue`) | passed, 0 errors/warnings |
| `npm run format:check` (`prettier --check`) | All matched files use Prettier code style! |
| `npm run test` (`vitest run`) | **206 passed / 37 files** (~11.7s) |
| `npm run build` (`vue-tsc && vite build`) | **built in ~5.4s**, 0 errors |

## Environment status (final)

All services healthy after the full run: api, postgres, redis, dashboard-worker, pipeline-worker,
clamav, mysql — `/health` healthy, `/ready` database+redis healthy, both workers publishing fresh
heartbeats. Disposable `vip_cert_test` dropped after certification; retained shared data: `vip`,
`vip_test`, `vip_b5_test`, `vip_live_uat_source`, `postgres`.

## Remaining blockers (post-certification)

None. Every required static, migration, formatting, and functional gate passes consistently under the
pinned CI toolchain, and the formerly-flaky queue test is now deterministic.

## Final verdict

### `BASELINE VERIFIED — SAFE TO BEGIN NEXT ENHANCEMENT`

The development environment is fully restored and healthy, the resource-access reconciliation remains
green, and the last remaining blocker (the Redis priority-queue race) is fixed and proven deterministic
across 30 isolated runs, 60 forced-boundary/FIFO/delay harness iterations, and two full clean-DB
integration runs. All backend and frontend quality gates pass. The next task — the complete permissions
and access-control enhancement — may begin (it is **not** started here).
