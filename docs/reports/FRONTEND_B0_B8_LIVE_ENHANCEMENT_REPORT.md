# VIP — Frontend Enhancement & B0–B8 Live Integration Report

Date (UTC): 2026-07-26
Repository: veltrix-intelligence-platform (VIP)
Branch: `frontend/enterprise-ui-enhancement`
Baseline commit: `d3cf9b4` (working-tree changes uncommitted — see §B)

---

## Addendum (2026-07-26) — Dataset device upload & Dashboard export downloader

Two user-reported issues were fixed and verified live.

### FE-002 — Datasets: cannot upload a CSV/Excel file from the device
- **Issue**: The dataset "Import CSV" dialog only accepted **pasted** CSV text; there was no way to
  upload a file from the user's device.
- **Fix** (`src/modules/datasets/DatasetListView.vue`): Added an **"Upload CSV file…"** control with a
  file picker (`accept=.csv,.tsv,.txt`). The chosen file is read in-browser, BOM-stripped, TSV is
  auto-converted to CSV, contents fill the editable CSV field, and the **target table** and **display
  name** are auto-derived from the filename. Guards for empty files and a 10 MB cap. Excel `.xlsx`
  is detected with clear guidance to "Save As CSV" (no heavyweight, security-sensitive xlsx parser
  was added to the bundle).
- **Verified live**: uploading `Q3 Sales Report.csv` filled the textarea and set table
  `q3_sales_report` / display name `Q3 Sales Report`. Regression test:
  `e2e/dataset-upload.spec.ts` (uploads `b8_5_certification.csv`, asserts form population) — passes.

### FE-003 — Dashboard Studio: PDF/PNG export downloader
- **Investigation**: The download pipeline itself is **correct** — verified end-to-end against the
  live backend: publish → `POST /dashboards/{id}/exports` (202) → worker render → `POST
  …/download-token` → `GET …/download?token=…` returns a valid `%PDF-1.4` (2 KB) and `\x89PNG`
  (18 KB) with `Content-Disposition: attachment`. Clicking **Download** in the Studio triggers the
  real browser save (network confirmed).
- **Real defects fixed** (`src/modules/dashboards/DashboardShareDialog.vue`,
  `DashboardStudioView.vue`):
  1. **Exporting a draft failed cryptically.** Exports require a published version; on a draft the
     API returns `DASHBOARD_NOT_PUBLISHED` and the UI showed `String(error)` (`[object Object]`-style).
     Now the Exports tab shows a clear **"Publish this dashboard to enable PDF/PNG/JSON/CSV exports"**
     notice and **disables** the Queue-export control until published (`canExport` gate). Verified
     live on a draft (notice shown, button disabled) and a published dashboard (download works).
  2. **Opaque error messages.** All 10 export/delivery error toasts now use `safeErrorText(error)`
     (backend message + code) instead of `String(error)`.
  3. **Misleading Share tooltip** always read "Save the dashboard before managing governance" even
     when saved — now conditional.
- **Ready-to-test artifact**: a published dashboard **"Downloader Test DL"** (Alpha · Alpha Workspace
  1) was left in place with completed PDF and PNG exports so the download can be exercised directly.

Both changes pass typecheck, ESLint, Prettier; frontend unit and Playwright functional suites remain
green (see §G / console summary).

---

## A. Executive Summary

The VIP frontend (Vue 3 + TypeScript, root `src/`) was run live against the real FastAPI backend
(`apps/api`, port 8000) with the full Docker stack (PostgreSQL, Redis, object storage, API,
dashboard/pipeline workers). The primary reported defect — the **dashboard three-dot menu offering
no usable Delete** — was reproduced in the browser, root-caused, fixed at the **shared-component
level**, and verified end-to-end against the live backend (including optimistic concurrency and
success feedback).

- Primary defect: **fixed and verified live** (dashboard action menu + delete).
- Fix scope: **systemic** — the shared `VipMenu` component now teleports its panel to `<body>`, so
  the same clipping bug is resolved everywhere the component is used (12 views: dashboards, datasets,
  pipelines, connections, admin members/workspaces, automation, dashboard viewer/widgets).
- Regression tests added: 1 unit spec (`VipMenu`) + 1 e2e spec (dashboard action menu / delete).
- Backend integration: B0–B8 live modules confirmed calling real endpoints; delete exercised live.
- Result: **VIP FRONTEND READY WITH NON-BLOCKING ITEMS** (see §H, §J).

---

## B. Environment

| Item | Value |
| --- | --- |
| Branch | `frontend/enterprise-ui-enhancement` |
| Commit | `d3cf9b4` (no commit made; changes in working tree) |
| Working tree | `M e2e/b8-5-pipeline-source.spec.ts` (prior QA pass), `M src/shared/ui/VipMenu.vue`, new `src/shared/ui/VipMenu.spec.ts`, new `e2e/dashboard-actions.spec.ts`, new `docs/reports/` |
| Frontend | http://localhost:3009 (Vite 6, live mode) |
| Backend | http://localhost:8000 (FastAPI) |
| Frontend live config | `VITE_API_MODE=live`, `VITE_API_BASE_URL=http://localhost:8000/api/v1`, `VITE_APP_ENV=development`, `VITE_ENABLE_MOCK_LATENCY=false` |
| Services | postgres (healthy), redis (healthy), api (healthy), dashboard-worker (healthy), pipeline-worker (up), dashboard-storage-init (one-shot, exited) |
| Migration head | `20260725_0011` (single head; `alembic upgrade head` clean) |
| Health | `/health` 200, `/ready` 200 (db+redis healthy), `/api/v1/version` OK |

---

## C. Frontend Enhancements

### FE-001 — Dashboard three-dot action menu was clipped (primary defect)

- **Issue**: On the dashboard list, opening the three-dot ("Actions for …") menu showed no usable
  Delete (and other actions were partially hidden).
- **Reproduction (live, browser)**: With admin `tenant-a@vip.demo`, opening the menu rendered a panel
  spanning x=115–305 while the containing card (`.dl-card`, `overflow: hidden`) spanned x=268–581 —
  so ~85% of the menu, including Delete, was clipped and unclickable. `document.elementFromPoint`
  over the Delete row hit the card edge, not the item.
- **Root cause**: `VipMenu`'s dropdown panel was `position: absolute` **inside** the trigger's DOM
  subtree. Any ancestor with `overflow: hidden` (dashboard cards, dataset cards, report cards) or a
  low stacking context clipped/hid it. This is a **shared-component** defect, not a page defect.
- **Fix**: Rewrote `src/shared/ui/VipMenu.vue` to **teleport the panel to `<body>`** and position it
  with `position: fixed` computed from the trigger's bounding rect, including:
  - alignment (`start`/`end`) with horizontal viewport clamping (8px margins),
  - vertical flip above the trigger when there is not enough room below,
  - reposition on scroll/resize while open,
  - click-outside that accounts for the teleported panel,
  - `z-index: var(--vip-z-popover)` (1300) so it is never trapped beneath cards/tables,
  - preserved keyboard nav (Arrow/Home/End/Escape/Tab), focus-in on open, focus-return on Escape,
    ARIA `role="menu"`/`menuitem`/`separator`, disabled-item handling.
- **Changed files**: `src/shared/ui/VipMenu.vue`.
- **Tests**: `src/shared/ui/VipMenu.spec.ts` (open/close, item render, `select` emit, disabled no-op,
  Escape close); `e2e/dashboard-actions.spec.ts` (menu opens, Delete visible + **in-viewport /
  unclipped**, confirm dialog opens, Cancel closes; Escape closes menu).
- **Result — verified live**:
  - Panel now teleported to `<body>`, `position: fixed`, z-index 1300, fully in viewport; Delete is
    hit-testable.
  - Verified on **datasets** list too (systemic): menu teleported, in-viewport, Delete reachable.
  - Verified at **mobile 375×812**: panel clamps to viewport (l=8, r=198), Delete reachable.
  - No new browser console errors.

---

## D. Dashboard Delete Fix (full flow, live)

Executed in the browser against the live backend:

1. Open dashboard list (`/dashboards`) as `tenant-a@vip.demo` (Organization Owner · Workspace Admin).
2. Click "Actions for …" → menu shows **Rename, Duplicate, Archive, Delete** (admin holds
   `dashboard.update`, `dashboard.archive`, `dashboard.delete` — confirmed via
   `/api/v1/authorization/context`).
3. Click **Delete** → `VipConfirmDialog` opens: title "Delete dashboard?", dashboard name, impact
   list (pages/visuals, status, delivery/export effects), soft-archive note, **type-to-confirm** box,
   Cancel/Delete.
4. Type the dashboard name → confirm.
5. Network (live): `GET /api/v1/dashboards/{id}` (row_version=2) → `DELETE
   /api/v1/dashboards/{id}?expected_version=2` → **204 No Content** → `GET /api/v1/dashboards` → 200.
6. UI: row removed from list, dialog closed, success toast "Dashboard deleted · <name>".

This confirms: permission gating, confirmation with type-to-confirm, **optimistic concurrency**
(`expected_version`), real backend call, list refresh/cache invalidation, success feedback, and no
stale state. Delete-denied for unauthorized users is enforced server-side (viewer/restricted → 403,
verified in the prior QA pass) and reflected in the UI by permission-gated menu items.

---

## E. Backend Integration Matrix (B0–B8, live profile)

| Module | Frontend Route | Backend Endpoint(s) | Live/Mock | Tested | Result |
| --- | --- | --- | --- | --- | --- |
| Auth (B1) | `/login` | `POST /auth/login`, `GET /auth/me`, `POST /auth/refresh`, `POST /auth/logout` | Live | Yes | PASS (login 200, session persists) |
| Tenancy (B2) | shell / `/admin/*` | `/api/v1/organizations`, `/workspaces`, `/tenant-context` | Live | Yes | PASS (Alpha/Beta; cross-tenant 404) |
| Governance (B3) | shell / gates | `/api/v1/authorization/context` | Live | Yes | PASS (114 perms; UI gates server-driven) |
| Connections (B4) | `/connections` | `/api/v1/connections*` | Live | Yes | PASS (1 seeded, secret-redacted) |
| Datasets (B5) | `/datasets` | `/api/v1/datasets*` | Live | Yes | PASS (24 datasets; menu fixed) |
| Semantic (B5) | `/semantic` | `/api/v1/semantic-models*`, `/semantic-query` | Live | Yes | PASS (1 model) |
| Dashboards (B6) | `/dashboards` | `/api/v1/dashboards*` | Live | Yes | PASS (list, delete live) |
| Delivery (B6.5) | `/dashboards/deliveries` | `/api/v1/.../deliveries*` | Live | Partial | PASS (routes render) |
| Pipelines (B7) | `/pipelines` | `/api/v1/pipelines*` | Live | Yes | PASS (43 pipelines; full run via e2e) |
| Jobs/Files/Events (B8) | studios | jobs/files/events APIs + SSE | Live | Partial | PASS (covered by e2e + prior QA) |

Demonstration adapters (ai, automation, billing, marketplace, insights, reports, operations,
developer, home) remain gated by feature flags / entitlements / permissions; route-smoke confirms
they render intentional surfaces with no runtime/network errors in the live profile.

---

## F. Manual Test Results (browser, live)

| Step | Result |
| --- | --- |
| Stack up + health/readiness | PASS |
| Login (admin) + session | PASS |
| Dashboard list renders (live data) | PASS |
| Three-dot menu opens, unclipped | PASS (fixed) |
| Menu on datasets list (systemic) | PASS |
| Menu at mobile 375×812 | PASS (clamped, usable) |
| Delete confirm dialog + type-to-confirm | PASS |
| Delete → 204 + row removed + toast | PASS |
| Browser console errors | None |
| Cross-tenant rejection (prior QA, live API) | PASS (404) |
| RBAC viewer/restricted mutate (prior QA) | PASS (403) |

---

## G. Automated Test Results

| Gate | Command | Result |
| --- | --- | --- |
| Frontend typecheck | `npm run typecheck` | PASS |
| ESLint | `npm run lint` | PASS |
| Prettier | `npm run format:check` | PASS |
| Frontend unit/component | `npm test` | **178 passed** (34 files; +5 new `VipMenu` tests) |
| Production build | `npm run build` | PASS (built in 3.68s; entry 288.4 kB / 95.8 kB gzip) |
| Playwright functional | `npm run test:e2e -- --project=chrome-desktop` | **36 passed** (incl. 2 new `dashboard-actions` tests) |
| Playwright a11y | `npm run test:a11y -- --project=chrome-desktop` | **18 passed** (no critical/serious violations) |
| Backend unit+integration (prior QA, same commit) | `pytest` in py3.12 container | 80 unit + 25 integration passed |

---

## H. Remaining Issues (non-blocking for manual use)

| ID | Sev | Item | Impact | Blocks manual use? |
| --- | --- | --- | --- | --- |
| OBS-1 | LOW | Global `VITE_API_MODE` switch: demo modules resolve to live endpoints in the live profile; contained by flags/entitlements/permissions. | None observed (route-smoke clean). | No |
| OBS-2 | LOW | `datasets.service.ts` masks per-dataset quality-fetch errors into `{status:'unknown'}`. | Optional sub-call degradation; recommend a visible "Quality could not be loaded" note. | No |
| OBS-3 | INFO | `rename` action uses `window.prompt` (native) rather than a themed dialog. | Functional but off-brand; candidate for a follow-up. | No |
| OBS-4 | INFO | Mock adapters bundled in live builds (dead weight). | Bundle size only. | No |

None are blockers. The primary defect is fixed and verified.

## I. Login Details

```
VIP Local URL: http://localhost:3009
Email:        tenant-a@vip.demo
Organization: Organization Alpha
Workspace:    Alpha Workspace 1
Role:         Organization Owner · Workspace Admin
```

Password is provided in the console response (not committed to the repository). It is a local-dev-only
credential set via the repository seed CLI.

## J. Final Verdict

**VIP FRONTEND READY WITH NON-BLOCKING ITEMS**

The primary dashboard three-dot / delete defect is fixed at the shared-component level, verified live
end-to-end (including optimistic concurrency and success feedback), covered by new unit + e2e
regression tests, and applies systemically to all list action menus. Mandatory frontend gates pass;
remaining items are low-risk observations.
