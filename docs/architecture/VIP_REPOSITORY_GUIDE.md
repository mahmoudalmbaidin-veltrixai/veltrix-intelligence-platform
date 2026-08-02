# VIP — Repository Guide

> Practical orientation for developers. All commands are documented from the repo's own
> `Makefile`, `package.json`, `pyproject.toml`, `docker-compose.yml`, and CI workflow.

---

## 1. Repository map

```
VIP/
├── src/                          # Vue 3 frontend (repository root app)
│   ├── main.ts                   # app bootstrap (Pinia, theme, apiClient wiring, auth.bootstrap)
│   ├── App.vue                   # layout selector + global overlays
│   ├── app/
│   │   ├── router/               # index.ts (routes + global guard), meta.ts
│   │   ├── layouts/              # AppLayout, StudioLayout, SettingsLayout, BlankLayout
│   │   ├── shell/                # AppSidebar, AppTopbar, MobileNav, NotificationDrawer
│   │   └── navigation.ts         # NAV_GROUPS / QUICK_CREATE registry
│   ├── modules/                  # feature modules (one folder per surface)
│   │   ├── auth/ connections/ pipelines/ datasets/ semantic/ dashboards/
│   │   ├── reports/ ai/ automation/ insights/ marketplace/ developer/ billing/
│   │   ├── admin/ platform/ operations/ home/ explore/ settings/ errors/
│   ├── shared/
│   │   ├── lib/apiClient.ts      # the single HTTP client (cookies, CSRF, tenant headers, SSE)
│   │   ├── services/             # serviceFactory + per-domain mock/live services
│   │   ├── contracts/            # Zod schemas + contract tests
│   │   ├── stores/               # Pinia: auth, platform, authorization, theme, ui
│   │   ├── authorization/        # PermissionGate / EntitlementGate / FeatureGate / QuotaGate
│   │   ├── ui/                   # Vip* design-system components + command palette
│   │   ├── viz/                  # custom SVG charts
│   │   ├── composables/ config/ types/
│   └── styles/                   # tokens.css, base.css
│
├── apps/api/                     # FastAPI backend
│   ├── src/vip_api/
│   │   ├── main.py               # application factory + ASGI app
│   │   ├── cli.py                # management CLI (users, seeds, platform-admin grants)
│   │   ├── api/router.py         # central router registration
│   │   ├── api/routes/           # operational (/health,/ready) + version
│   │   ├── core/                 # config, middleware, errors, logging, context
│   │   ├── database/             # Base, async session, health
│   │   ├── redis/                # Redis client
│   │   ├── auth/ tenancy/ governance/ platform_admin/   # identity + security
│   │   ├── connections/ datasets/ semantic/             # data-layer domains
│   │   ├── dashboards/ dashboard_delivery/ pipelines/   # studio domains + workers
│   │   ├── jobs/ files/ events/ catalog/ home/          # platform services
│   │   └── schemas/
│   ├── alembic/                  # migrations (env.py + versions/)
│   ├── tests/                    # unit/ + integration/ + conftest.py
│   ├── scripts/                  # docker-entrypoint, worker-health, postgres-init, backend_quality
│   ├── pyproject.toml            # deps + pytest/ruff/mypy config
│   ├── requirements*.lock        # pinned runtime/dev deps
│   └── Dockerfile
│
├── infra/postgres/Dockerfile     # Postgres 17 image (su-exec hardening)
├── docker-compose.yml            # postgres, redis, clamav, api, workers, storage-init, mysql(opt)
├── .github/workflows/quality-gate.yml   # CI (5 jobs)
├── docs/
│   ├── architecture/             # this guide + platform architecture + system-workflow diagrams
│   ├── backend/                  # per-domain backend design docs
│   ├── reports/                  # status/QA/certification reports (treat claims skeptically)
│   └── validation/
├── tests/e2e/                    # Playwright specs
├── playwright.config.ts vitest.config.ts vite.config.ts
├── package.json Makefile netlify.toml
├── .env.example .env.local .env.test      # env templates (names only; no secrets committed)
└── ARCHITECTURE.md README.md
```

Excluded from analysis (generated/deps/caches): `node_modules`, `.git`, `dist`, `build`,
`coverage`, `playwright-report`, `test-results`, `.venv`, `.mypy_cache`, `.ruff_cache`,
`.pytest_cache`, `__pycache__`, `artifacts`.

## 2. Important folders (responsibilities)

- `src/shared/lib/apiClient.ts` — the ONLY place raw HTTP happens; all services depend on it.
- `src/shared/services/serviceFactory.ts` — chooses mock vs live per domain via `VITE_API_MODE`.
- `src/app/router/index.ts` — all routes + the global auth/tenant/permission/entitlement/flag guard.
- `apps/api/src/vip_api/main.py` + `api/router.py` — backend composition root.
- `apps/api/src/vip_api/governance/` — RBAC, flags, entitlements, quotas, audit, route-policy test.
- `apps/api/src/vip_api/tenancy/` — org/workspace/membership + tenant context resolution.
- `apps/api/alembic/` — schema source of truth (single linear head).

## 3. Entry points

| Layer | Entry point |
| --- | --- |
| Frontend app | `src/main.ts` → mounts `src/App.vue` after `auth.bootstrap()` |
| Frontend router | `src/app/router/index.ts` (`router.beforeEach` guard) |
| Frontend state | `src/shared/stores/{auth,platform,authorization}.ts` |
| Backend ASGI app | `apps/api/src/vip_api/main.py::app` (factory `create_application`) |
| Backend routes | `apps/api/src/vip_api/api/router.py::register_routers` |
| Backend middleware | `core/middleware.py::RequestContextMiddleware` + CORS + TrustedHost |
| Job worker | `python -m vip_api.jobs.worker` |
| Pipeline worker | `python -m vip_api.pipelines.worker` |
| Delivery worker | `python -m vip_api.dashboard_delivery.worker` (or `dashboard.export` job handler) |
| Management CLI | `python -m vip_api.cli <command>` |
| DB init/migrations | `apps/api/alembic/env.py`, `alembic.ini` |
| Docker orchestration | `docker-compose.yml` |
| CI | `.github/workflows/quality-gate.yml` |

## 4. How to run locally

**Backend (Docker, recommended):**

```bash
docker compose up --build
# API on :8000 — the api container runs `alembic upgrade head` + seeds, then uvicorn
# Health: http://localhost:8000/health  /ready  /api/v1/version
```

**Backend (native, without Docker):**

```bash
make backend-infra          # docker compose up -d postgres redis
cd apps/api
make backend-migrate        # alembic upgrade head
make backend-start          # uvicorn vip_api.main:app --reload
```

**Create a user and grant super-admin:**

```bash
cd apps/api
python -m vip_api.cli create-user
python -m vip_api.cli grant-platform-admin you@example.com
```

**Frontend:**

```bash
npm ci
npm run dev                 # http://localhost:3009 (default VITE_API_MODE=mock)
# To use the live backend:
#   set VITE_API_MODE=live and VITE_API_BASE_URL=http://localhost:8000 in a local env file
```

> Staging/production frontend builds fail fast unless `VITE_API_MODE=live` and a valid
> `VITE_API_BASE_URL` are set (`src/shared/config/env.ts`).

## 5. How to run tests

**Frontend:**

```bash
npm run test              # vitest run (37 unit/component specs)
npm run test:contract     # apiClient + contract specs
npm run test:e2e          # Playwright (excludes @a11y) — needs dev server + live API
npm run test:a11y         # Playwright accessibility specs
```

**Backend:**

```bash
cd apps/api
make backend-unit                 # pytest -m "not integration"
make backend-integration          # RUN_INTEGRATION_TESTS=1 pytest -m integration (needs Postgres+Redis)
python scripts/backend_quality.py # ruff + mypy + unit (+ integration + alembic check if env set)
```

> Integration tests are collection-skipped unless `RUN_INTEGRATION_TESTS=1`
> (`apps/api/tests/conftest.py`). This guide does not report test pass/fail — no suites were run.

## 6. How to start workers

Workers are separate processes (already wired in Compose):

```bash
# generic jobs (runs dashboard exports + dataset quality + file lifecycle handlers)
python -m vip_api.jobs.worker        # or: make backend-worker
# pipeline execution
python -m vip_api.pipelines.worker   # or: make pipeline-worker
```

Worker health is verified by `apps/api/scripts/worker-health.py` against the `worker_heartbeats`
table. Workers set `SKIP_PLATFORM_BOOTSTRAP=true` so they do not run migrations/seeds.

## 7. How migrations work

- Alembic with an async `env.py` that imports every domain `models` module so `Base.metadata` is
  complete, then sets `sqlalchemy.url` from `Settings.database_url` at runtime.
- Single linear history; current head is `20260728_0016_resource_access_entries`.
- Autogenerate excludes external warehouse tables (`vip_b5_*` and registered dataset source tables).
- Common commands (from `apps/api`):

```bash
make backend-migrate        # alembic upgrade head
make backend-migration      # alembic revision --autogenerate -m "..."
alembic check               # verify models vs migrations (also in CI)
```

- Migrations are overwhelmingly additive. Notable non-additive upgrades: `53957b92b086` (RBAC
  enum→`role_id` cutover, drops old enum columns) and `20260728_0013` (email made nullable +
  partial unique index). Do not create or apply migrations as part of analysis tasks.

## 8. Where to add a new frontend feature

1. Create a module folder under `src/modules/<feature>/` with views + a `<feature>.service.ts`.
2. Define the service interface with a mock and a live implementation; export via
   `defineService(mock, () => apiService)` (see `serviceFactory.ts`). Live implementations must call
   the shared `apiClient` — never `fetch` directly.
3. Add Zod contracts in `src/shared/contracts/` if new server shapes are introduced.
4. Register routes in `src/app/router/index.ts` with `meta` (`layout`, `requiresAuth`,
   `permission`, `entitlement`, `featureFlag`), and add nav entries in `src/app/navigation.ts`.
5. Gate UI with `PermissionGate` / `EntitlementGate` / `FeatureGate` / `QuotaGate` where needed.
6. Add Vitest specs alongside the code (`*.spec.ts`) and Playwright specs under `tests/e2e/`.

## 9. Where to add a new backend domain

1. Create `apps/api/src/vip_api/<domain>/` with `routes.py`, `services.py`, `models.py`,
   `schemas.py` (and `repositories.py`/`dependencies.py` following `connections`/`datasets`).
2. Scope every table with `organization_id` + `workspace_id` and composite tenant FKs; add
   tenant-scoped unique constraints/indexes; add `row_version` if you need optimistic locking.
3. Enforce authorization via `require_permission(...)` / `require_governance(...)` /
   `require_capability(...)` dependencies and add CSRF (`require_csrf`) on mutations — the
   `governance/route_policy.py` test asserts coverage for `/api/v1/*` routes.
4. Register the router in `api/router.py::register_routers` (under `API_V1_PREFIX`).
5. Add permission keys to the governance policy catalog + seed; add feature flags/entitlements/
   quotas as needed.
6. Add an Alembic migration (`make backend-migration`) and import the models module in
   `alembic/env.py` if it is a new package.
7. Add unit tests under `tests/unit/` and integration tests under `tests/integration/`.

## 10. Where to add a new worker

1. Register a job handler in `apps/api/src/vip_api/jobs/handlers.py` / `registry.py` (preferred for
   most async work — runs on the generic `jobs.worker`).
2. For a dedicated long-running executor, follow `pipelines/worker.py` (claim with lease + heartbeat,
   `FOR UPDATE SKIP LOCKED`, publish events via the Redis broker).
3. Add the process to `docker-compose.yml` with `SKIP_PLATFORM_BOOTSTRAP=true` and a
   `worker-health.py` healthcheck.

## 11. Where shared contracts live

- **Frontend**: `src/shared/contracts/apiContracts.ts` (Zod schemas) + `.spec.ts` contract tests;
  domain response shapes in each `*.service.ts`.
- **Backend**: Pydantic schemas in each domain's `schemas.py`; stable error codes in
  `core/errors.py`; permission keys in `governance/policies.py`.
- There is **no shared code-generated client** — the frontend and backend contracts are maintained
  in parallel and guarded by contract tests + the `route_policy` test.

## 12. Naming and architecture conventions (discovered)

- Frontend components use a `Vip*` prefix for the design system; views end in `View.vue`; services
  end in `.service.ts`; Pinia stores are `useXStore`.
- Backend packages are domain-oriented (`routes → services → repositories → models`); FastAPI
  dependency classes named `RequireXGovernance`; permission keys are dotted
  (`resource.action`, e.g. `dashboard.publish`).
- Tenant columns are always `organization_id` + `workspace_id`; DB constraints follow the naming
  convention in `database/base.py` (`ix_/uq_/ck_/fk_/pk_`).
- Migrations are dated + sequential (`YYYYMMDD_NNNN_description.py`) alongside a few hash-named
  legacy revisions; single linear head is maintained.
- Async-first backend (async SQLAlchemy + asyncpg + `httpx`); tests use `asyncio_mode = auto`.
