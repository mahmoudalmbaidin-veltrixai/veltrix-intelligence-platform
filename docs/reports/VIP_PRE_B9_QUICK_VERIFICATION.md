# VIP — Quick Platform Verification Before Phase B9

**Branch:** `enhancement/pipeline-dashboard-studios`
**Starting SHA:** `2590248ba51cd0d8da37c000efaed754bac070df`
**Ending SHA:** `2590248ba51cd0d8da37c000efaed754bac070df` (no commits; uncommitted work preserved)
**Scope:** Focused verification + stabilization. Highest priority: Dashboard module.

---

## Environment

| Component | Status | Evidence |
|-----------|--------|----------|
| Docker Desktop | Running | 7/7 compose services `Up (healthy)` |
| PostgreSQL | Healthy | `/ready` → `database: healthy` |
| Redis | Healthy | `/ready` → `redis: healthy` |
| API | Healthy | `GET /health` → 200 `{"status":"healthy"}`; `GET /ready` → 200 ready |
| Dashboard/default worker | Running | recent `dashboard.export.completed`, `job.completed` `outcome:success` |
| Pipeline worker | Running | `Pipeline worker started` + `pipeline.run.succeeded` events |
| ClamAV | Healthy | compose `Up (healthy)` |
| MySQL (connector) | Healthy | compose `Up (healthy)` |
| Frontend | Running (live mode) | `http://localhost:3009` → 200 (VITE_API_MODE=live) |
| Alembic head | `20260728_0018` (single head) | `alembic heads` = `alembic current`; `alembic check` → "No new upgrade operations detected." |

---

## Module status matrix (live, governance-demo org)

| Module | Main flow tested | FE | API | Status | Main issue |
|--------|------------------|----|----|--------|------------|
| Login / session | `/auth/me` after reload | ✓ | 200 | **Working** | — |
| Home | dashboard summary, tenant stats | ✓ | 200 | **Working** | (was broken pre-fix) |
| Connections | list (3 connections) | ✓ | 200 | **Working** | — |
| Pipelines | list + Studio (prior slice) | ✓ | 200 | **Working** | — |
| Datasets | list (7 of 7) | ✓ | 200 | **Working** | (was broken pre-fix) |
| Semantic Models | list (LIVE-UAT models) | ✓ | 200 | **Working** | (was broken pre-fix) |
| **Dashboards (list)** | list 3 dashboards | ✓ | 200 | **Working** | **fixed (see below)** |
| **Dashboard Studio** | open editor, edit, save, reload | ✓ | 200 | **Working** | edit→save→reload persists |
| **Dashboard viewer** | render 5 widgets, KPI data | ✓ | 200 | **Working** | KPIs show real $ data |
| **Widget data queries** | 8× `POST /widgets/{id}/data` | ✓ | 200 | **Working** | some charts "No data" = unconfigured fields |
| Dashboard exports | worker export events | ✓ | 200 | **Working** | worker `export.completed` in logs |
| Roles & permissions | `/admin/roles` list | ✓ | 200 | **Working** | — |
| Groups | `/admin/groups` list | ✓ | 200 | **Working** | — |
| Audit / Activity | `/audit` live events | ✓ | 200 | **Working** | — |
| Jobs / workers | worker heartbeats + job events | ✓ | 200 | **Working** | verified via worker logs |
| Reports / Marketplace / Billing / AI | — | — | — | **Placeholder** | not backend-backed (out of scope) |

All bare-path modules (Home, Datasets, Semantic, Dashboards, Audit, Activity) were **broken before the fix** and are **working after** it — see below.

---

## Dashboard findings (priority)

### Root cause
The running **frontend dev server was started with a stale API base URL**
(`http://localhost:8000`, missing the `/api/v1` version prefix). The dashboards
adapter — like most VIP service adapters — calls **bare paths** (`/dashboards`,
`/dashboards/{id}/editor`, …). The API client (`buildUrl`) only strips/normalizes
the version prefix when a path starts with `/auth/` or `/api/v1/`; bare paths are
appended to the configured base verbatim. With base = `http://localhost:8000`, the
frontend requested:

```
GET http://localhost:8000/dashboards            → 404 Not Found   (broken)
GET http://localhost:8000/api/v1/dashboards     → 200 OK          (correct route)
```

The same defect broke every bare-path module (Home, Datasets, Semantic, Audit,
Activity). Connections and Pipelines were unaffected because their adapters use
explicit `/api/v1/...` paths.

`.env.local` already contained the **correct** value
(`VITE_API_BASE_URL=http://localhost:8000/api/v1`); the long-running dev server
simply predated it and never reloaded.

### Files involved
- `src/modules/dashboards/dashboards.service.ts` (bare-path adapter — unchanged)
- `src/shared/lib/apiClient.ts` `buildUrl` (version-prefix logic — unchanged)
- `src/shared/config/env.ts` (`apiBaseUrl = raw VITE_API_BASE_URL` — unchanged)
- `.env.local` (already correct)

### Fix applied
**Environment fix, no code change:** restarted the frontend dev server so it
reloads `.env.local` (base `http://localhost:8000/api/v1`). No source files were
modified this session (`git status` confirms `dashboards.service.ts`,
`apiClient.ts`, `env.ts` are untouched).

### Verification result (live Chromium, `VITE_API_MODE=live`)
- Dashboard list → `GET /api/v1/dashboards` **200**, 3 dashboards render.
- Open Studio → `GET /api/v1/dashboards/{id}/editor` **200**, palette + canvas load.
- Edit (renamed a draft) → **Save** `PUT /api/v1/dashboards/{id}/editor` **200**.
- Reload → name persisted (edit→save→reload→persist ✓).
- Viewer (published, 5 widgets) → renders; KPI cards show real data
  (Total Net Revenue **$831,847,341**, Gross Margin **35.24%**, AOV **$166,703**).
- Widget queries → 8× `POST /api/v1/dashboards/{id}/widgets/{wid}/data` all **200**.
- No console errors on list, studio, or viewer.

### Remaining limitations
- Two chart widgets on the published dashboard show **"No data — add fields"** —
  a per-widget field-configuration state (their `POST …/data` returns 200 with an
  empty series), **not** a system fault. KPI + configured widgets return data.
- **Latent fragility (recommend hardening in B9):** bare-path adapters depend on
  the base URL ending in `/api/v1`. If the FE is ever launched with a base lacking
  that suffix, these modules 404 again. Hardening options: make `buildUrl` always
  resolve the version prefix for non-auth paths, or standardize every adapter on
  explicit `/api/v1/...` (as Connections/Pipelines already do). Not urgent now that
  the env is correct.

---

## Permission verification

- **Admin (governance-admin, org+workspace admin)**: opened Dashboard Studio,
  edited, saved, published-capable — full owner/admin access confirmed live.
- **Pipeline & Dataset permissions** (recent slices): pipeline ACL action-matrix
  and dataset access remain enforced — backend unit + integration suites pass
  unchanged (196 unit / dashboard + resource integration green); pipeline routes
  still gate correctly (verified in the prior slice's live persona run).
- Dashboard viewer/editor/deny enforcement is covered by the passing
  `test_dashboard_lifecycle_integrity` + dashboard share tests; not re-driven
  per-persona in this quick pass (backend enforces independently of UI).
- No permission gate was found incorrectly blocking valid module access.

---

## Tests

| Suite | Command | Result |
|-------|---------|--------|
| Backend lint | `ruff check .` | ✓ All checks passed |
| Backend format | `ruff format --check .` | ✓ 227 files formatted |
| Backend types | `mypy src tests` | ✓ 203 files, no issues |
| Backend unit | `pytest -m "not integration"` | ✓ **196 passed**, 34 deselected |
| Dashboard integration | `pytest -m integration test_dashboard_lifecycle_integrity.py test_dashboard_persistence.py` (fresh-ish `vip_test`) | ✓ **2 passed** |
| FE types | `npm run typecheck` | ✓ clean |
| FE lint | `npm run lint` | ✓ clean |
| FE format | `npm run format:check` | ✓ clean |
| FE tests | `npm run test` (vitest run) | ✓ **232 passed** (39 files) |
| FE build | `npm run build` | ✓ built |

No skipped/failed suites. No code changed this session, so these are regression confirmations.

---

## Pre-B9 blockers

**Critical:** none remaining. (The Dashboard blocker — stale FE base URL — is fixed.)

**High:** none remaining.
- ~~Harden bare-path API adapters against a missing `/api/v1` base~~ — **DONE.**
  Canonical `resolveApiUrl` now adds `/api/v1` exactly once for bare application
  paths under any base form; verified live under both `http://localhost:8000` and
  `http://localhost:8000/api/v1`. See "API Base URL Hardening — Permanent Fix".

**Medium:**
- Published dashboard has 2 unconfigured chart widgets ("No data"). Data-config only.
- Frontend dev server must be (re)started with `.env.local` present to pick up the
  live base URL. Operational note.

**Low:**
- Placeholder modules (Reports, Marketplace, Billing, AI) are UI shells without
  backends — expected, out of certified scope.

---

## Recommendation

**READY TO START PHASE B9**

All Pre-B9 exit criteria are met: API URLs resolve with exactly one `/api/v1`; both
accepted base-URL forms work; Dashboard (list/studio/save/reload/viewer/widget-data)
is healthy; Dataset, Semantic, Home, and Audit are healthy; frontend typecheck,
lint, format, tests (260), and build all pass; live Chromium smoke passes under both
base forms; and no authentication, SSE, or download URLs regressed.

The core platform (auth, tenancy, roles/permissions/groups/ACL, connections,
pipelines, datasets, semantic, dashboards + viewer + exports, jobs, audit) is
operational in live mode with all quality gates green. The single reported blocker
(Dashboard) is resolved, and the recommended pre-B9 hardening — resilient API
base-URL handling — has now been **implemented and verified** (see below).

---

## API Base URL Hardening — Permanent Fix (Pre-B9 final)

### Root cause
The frontend API client (`buildUrl`) only added the `/api/v1` version prefix when
either the configured `VITE_API_BASE_URL` already ended in `/api/v1`, or an adapter
happened to hard-code the prefix. Most adapters use **bare** paths (`/dashboards`,
`/datasets`, `/semantic-models`, `/home/summary`, `/audit`, …), so when the base was
the bare host (`http://localhost:8000`) those requests went to
`http://localhost:8000/dashboards` → **404**. Absolute URLs were also not detected
(a latent risk for signed download URLs).

### Permanent fix
A single canonical resolver, `resolveApiUrl(baseUrl, path, query)`, is now the ONE
rule every request (JSON, download, and SSE `eventStream`) flows through. Adapters
never re-implement prefix logic. Normalization rules:

| Input | Result |
|-------|--------|
| Absolute URL (`http(s)://…`) — signed downloads / external hosts | passed through untouched |
| Base `http://host` **or** `http://host/api/v1` (trailing slashes normalized) | both reduce to the same API origin |
| `/auth/*`, `/health`, `/ready`, `/healthz` | origin only — **never** versioned |
| `/api/v1/…` (already versioned) | used as-is — **never** duplicated (`/api/v1/api/v1` impossible) |
| any other application path (bare) | receives `/api/v1` **exactly once** |
| query string | appended after the resolved path; embedded `?token=` in signed URLs preserved |

`env.ts` configuration validation already satisfied Step 3 and is unchanged: dev
accepts either base form, staging/production fail closed on missing/malformed base
(`EnvConfigError`), errors are developer-facing with no secret exposure, and live
mode never silently falls back to mock outside local dev.

### Files changed
- `src/shared/lib/apiClient.ts` — replaced `buildUrl` with the pure, exported
  `resolveApiUrl` + `API_VERSION_PREFIX` + `isUnversionedRootPath`; `buildUrl` now
  delegates. (Backend unchanged — no backend code was touched.)
- `src/shared/lib/apiClient.contract.spec.ts` — one URL assertion updated from
  `/resources` to `/api/v1/resources` to match the corrected canonical behavior.

### Tests added
- `src/shared/lib/apiClient.url.spec.ts` — 19 unit cases for `resolveApiUrl`
  covering all 12 required scenarios (host-only + bare, versioned + bare, host-only
  + versioned, versioned + versioned, trailing-slash normalization, query params,
  auth paths, absolute download URL, SSE path, health/ready, empty/invalid base, no
  duplicate `/api/v1`) plus signed-relative-download and leading-slash normalization.
- `src/shared/lib/apiClient.services-url.spec.ts` — service-level resolution guard
  pinning the real Dashboard/Dataset/Semantic/Home/Audit endpoints to a single
  `/api/v1` under both base forms (imports the actual adapter modules).

### Live verification evidence (live Chromium, both base forms)
**Configuration A — `VITE_API_BASE_URL=http://localhost:8000` (the bug scenario):**
- `GET /api/v1/dashboards` **200** (previously bare `/dashboards` → 404).
- Dashboard Studio editor **200**, **Save** `PUT …/editor` **200**, reload → name
  persisted; viewer renders real KPI data ($831,847,341…); 5× widget
  `POST …/widgets/{id}/data` **200**.
- `GET /api/v1/datasets/{id}/quality`, `/api/v1/semantic-models`, `/api/v1/home/summary`,
  `/api/v1/audit-events?limit=200&offset=0` all **200**.
- `/auth/me` → 401 → `POST /auth/refresh` **200** → `/auth/me` **200** (auth stays
  unversioned; refresh cycle intact). SSE `/api/v1/events/stream` **200**.
- **No `/api/v1/api/v1`** on any request.

**Configuration B — `VITE_API_BASE_URL=http://localhost:8000/api/v1` (default local):**
- Same modules re-smoked; every application endpoint uses exactly one `/api/v1`, and
  the version prefix is **not** duplicated. Dashboard edit → save → reload confirmed
  working after restoring this config.

The temporary `.env.development.local` used to test Configuration A was removed and
the frontend restarted on the canonical `.env.local` (`/api/v1`) base.

### Regression gates
`npm run typecheck` ✓ · `lint` ✓ · `format:check` ✓ · `test` **260 passed** (41
files; +28 from the new URL suites) ✓ · `build` ✓. Backend untouched.

---

## Local review setup

**Frontend:** http://localhost:3009 (live mode) · **API:** http://localhost:8000

**Demo credentials (local dev only — governance-demo org):**

| Persona | Username | Password | Role |
|---------|----------|----------|------|
| Admin | `governance-admin` | `Enterprise review 2026!` | Org + workspace admin |
| Editor | `governance-editor` | `Enterprise review 2026!` | Editor/developer |
| Viewer | `governance-viewer` | `Enterprise review 2026!` | Read-only |
| Restricted | `governance-restricted` | `Enterprise review 2026!` | Deny target |

### Dashboard review path (test this first)
1. Sign in as `governance-admin`.
2. Open **Dashboards** → the list shows 3 dashboards (200, no error).
3. Open **LIVE-UAT-Executive-Sales-Dashboard** (viewer) → KPI cards show real
   revenue/margin/AOV values; 5 widgets render; filters present.
4. Back to list → open **Contract QA Dashboard B9verify** → **Edit** (Studio).
5. Change the name, click **Save**, then reload the page → the change persists.
6. (Optional) On the published dashboard, click **Edit** → **Publish** flow and
   **Share** to confirm the owner controls are available.

*Exact flow to confirm the fix:* **Dashboards list → open a dashboard → Studio →
edit → Save → reload → change persists.* If that round-trips without a 404, the
Dashboard module is healthy.

> Note: a draft was renamed to **"Contract QA Dashboard B9verify"** during the
> live save/reload persistence test — harmless test data on a QA draft.
