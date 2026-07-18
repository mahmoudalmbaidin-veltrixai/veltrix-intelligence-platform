# VIP Frontend — Updated Backend-Integration Readiness

Supersedes `QA Files/FRONTEND_BACKEND_INTEGRATION_READINESS.md` (which scored
45/100, "NOT READY"). Re-assessed after the remediation sprint.

## Verdict: READY FOR PHASED BACKEND INTEGRATION (with minor conditions)

Estimated readiness: **~84 / 100** (self-assessed against the audit's rubric;
subject to an independent re-audit). The two hard gates that blocked
integration — a universal mock/live adapter boundary and session-authoritative,
tenant-isolated context — are now met and verified.

## Gate status

### Gate 1 — Identity & context ✅
- One authoritative flow: `authService.bootstrap/login` → `PlatformStore.hydrate(context)`; logout/expiry → `clearContext()`.
- Bootstrap runs before mount; protected routes gated by `requiresAuth` + auth store.
- 401 → cancel requests, clear state, redirect to login, restore intended route (verified).
- 403 → `/forbidden`; missing entitlement → upgrade; disabled feature flag → blocked (enforced in route meta).
- Local mocks, editor persistence and (on switch) query cache are partitioned by tenant/workspace. **Two-tenant isolation verified.**

### Gate 2 — Adapter & contract pattern ✅ (conditions)
- Every module exports an interface + mock + live adapter via `defineService`.
- Inline fixtures largely moved behind services (global search/command providers still hold demo lists — flagged, low risk).
- Centralized client: base URL, timeout, retry (idempotent), abort, JSON/multipart/download, `X-Organization-Id`/`X-Workspace-Id`/`X-Locale`/`X-Timezone`/`X-Correlation-Id`, normalized errors incl. distinct `cancelled`/`timeout`.
- **Conditions:** no OpenAPI-generated client / runtime DTO validation yet; pagination envelope not centrally modeled; fetch-level contract tests deferred.

### Gate 3 — Editor integrity ✅
- New Dashboards/Pipelines route to stable `/:id` URLs on first save (deep-link/reload safe).
- Pipeline edge/node deletion fixed (mutually exclusive selection) + regression test.
- Unsaved-change protection retained. Export/delivery/AI clearly labelled as simulation; typed adapters ready for async-job contracts.

### Gate 4 — Accessibility & release automation ◑
- Keyboard-authoring alternatives added for both studios; shared Menu/Drawer/Table repaired; nested landmarks removed.
- **Deferred:** committed Playwright route/workflow/guard + axe suites (verified this sprint via driven-browser assertions instead), and a 2-tenant live-contract environment.

## Endpoint integration order (unchanged, now unblocked)
1. Auth/session (`login`, `logout`, `me`, `refresh`).
2. Organizations / workspaces / permissions / entitlements / feature flags — with 2-tenant isolation tests.
3. Shared contracts: pagination, errors, trace IDs, uploads/downloads, async-job status.
4. Read-only catalog/list: Connections, Datasets, Semantic metadata.
5. Dashboard CRUD (create routing is now stable) → widget data, filters, versions, sharing.
6. Pipeline CRUD (deletion/integrity fixed) → validate/run/log/retry events.
7. Reports/deliveries/exports (real async render/delivery).
8. Automation & AI (streaming/event, approval, ingestion).
9. Billing / Developer / Marketplace mutations (authorization, idempotency, audit).

## Required backend contracts (see BACKEND_INTEGRATION.md)
REST under `VITE_API_BASE_URL`; cookie-session auth with the endpoints above;
`X-Organization-Id`/`X-Workspace-Id` scoping enforced server-side; error bodies
`{ message, errors[] }`; `X-Correlation-Id` echoed. **Backend must enforce all
permissions, tenant isolation, entitlements and ownership — frontend guards are
a UX layer only.** Streaming (runs, AI) and file upload/download are backend
dependencies.

## Conditions before scaling integration
1. Land the Playwright + axe CI suites and a 2-tenant live-contract harness (H009).
2. Adopt an OpenAPI-generated client or schema-validated DTO boundary; add
   fetch-level client contract tests (M009).
3. Complete Org/Workspace/Platform settings forms as their endpoints land (H008).
4. Replace remaining simulated actions (AI streaming, uploads, real PDF/PNG
   render, deliveries) with their async-job contracts (H007).

Begin read-only integration (Gates 1–2 items 1–4) immediately; gate mutations,
exports, admin, billing and AI/automation on their listed contracts.
