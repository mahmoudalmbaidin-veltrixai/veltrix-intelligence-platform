# VIP Frontend — Defect Resolution Matrix

Remediation of the Codex Sol 5.6 QA audit (`QA Files/FRONTEND_QA_DEFECT_REGISTER.md`).
Status legend: **Resolved** · **Partially Resolved** · **Deferred** · **Not Applicable**.

Quality gate after remediation: type-check **0 errors** · lint **clean** ·
Prettier **all files conform** · **89/89** unit/component tests pass · production
build **passes**.

| ID | Sev | Status | Resolution / justification |
|----|-----|--------|----------------------------|
| VIP-FE-C001 | Critical | **Resolved** | All 16 module services (connections, pipelines, datasets, semantic, reports, ai, automation, operations, admin, billing, marketplace, developer, insights, home, delivery, dashboards) now expose a typed `Service` interface with `mockXxxService` + `apiXxxService` selected via `defineService(mock, () => api)`. Views import the factory export, never a concrete mock. |
| VIP-FE-C002 | Critical | **Resolved** | `LocalStore` supports `{ scoped: true }` and a tenant/workspace scope set from the session; pipeline/dashboard/delivery/snapshot stores are scoped and seed only the primary tenant. **Verified in-app:** Veltrix shows 3 dashboards, Northwind 0, switch-back restores 3. Query cache invalidates on org/workspace switch. |
| VIP-FE-C003 | Critical | **Resolved** | Pipeline keyboard authoring: palette Enter/Space adds a node; nodes are focusable and Enter-selectable; arrow keys move (Shift = fine step); output/input ports are focusable and Enter starts/completes a connection; Delete removes; all changes announced via the live region. |
| VIP-FE-C004 | Critical | **Resolved** | Dashboard widgets are focusable/`role=button`; Enter selects; arrow keys move on the grid, Shift+arrows resize; Delete removes; selection + resize announced. |
| VIP-FE-H001 | High | **Resolved** | `PlatformStore.hydrate(context)` is called by the auth store on bootstrap/login so the session is the authoritative source of user/org/workspace/role/flags; `applyScope()` sets storage scope from the same source; API context headers derive from it. |
| VIP-FE-H002 | High | **Resolved** | The API client's 401 handler now `cancelAllRequests()`, clears session + context, and routes to `/login?expired=1` preserving the intended path. Login shows a "Session expired" notice. |
| VIP-FE-H003 | High | **Resolved** | `/ai/agents` and `/ai/agent-runs` carry `featureFlag: 'ai-agents-beta'` meta; the existing router guard blocks direct navigation when the flag is off. (Frontend UX gate only — backend must also enforce.) |
| VIP-FE-H004 | High | **Resolved** | On first dashboard save from `/dashboards/new`, the studio `router.replace(/dashboards/:id/edit)` with the created stable ID for deep-link/reload. |
| VIP-FE-H005 | High | **Resolved** | On first pipeline save from `/pipelines/new`, the studio routes to `/pipelines/:id`. |
| VIP-FE-H006 | High | **Resolved** | Edge/node selection is mutually exclusive: `selectEdge()` clears node selection and `selectNode()/selectMany()` clear the edge, so Delete removes exactly the focused element. Regression test added. |
| VIP-FE-H007 | High | **Partially Resolved** | A persistent "Mock" indicator (topbar) marks the whole app as simulated; dashboard PDF/PNG export is labelled a manifest with a "server-rendered" note; AI streaming / uploads remain visibly simulated. Full per-action production wiring is a backend dependency (typed adapters are in place). |
| VIP-FE-H008 | High | **Partially Resolved** | Personal settings (Profile, Appearance/theme, Notifications, Security, Sessions) are functional; Organization/Workspace/Platform sections render representative controls. Full org/workspace/platform forms + validation deferred to their backend endpoints. |
| VIP-FE-H009 | High | **Partially Resolved** | Unit/component coverage expanded to 89 tests incl. env, error model, tenant scoping, edge/node selection, auth store, service factory, dialog a11y. Critical journeys (login/logout, auth gate + intended restore, tenant isolation, keyboard authoring, first-save routing) were **verified via driven-browser assertions** this sprint. A committed Playwright + axe suite is **deferred** (no CI browser here). |
| VIP-FE-H010 | High | **Deferred** | Dev-only Vitest/Vite advisories; a tested toolchain upgrade is out of scope for a UI remediation sprint (no production-dependency advisories). Documented for a separate toolchain PR. |
| VIP-FE-H011 | High | **Resolved** | Drawer: focus trap + return + Escape. Menu: Arrow/Home/End roving focus, Escape/Tab close, focus first item on open. Table: sortable headers are focusable buttons (Enter/Space), clickable rows focusable + Enter-activated. |
| VIP-FE-H012 | High | **Resolved** | Removed nested `<main>` landmarks from Login, Assistant, Automation Builder, Explore, Report Builder and Settings (layouts own the single `<main id="vip-main">`). |
| VIP-FE-H013 | High | **Resolved** | Durable mock logout: a deliberate sign-out sets a persisted flag so bootstrap does not re-seed a session; login clears it. |
| VIP-FE-M001 | Medium | **Resolved** | Repo-wide Prettier pass (123 files); `format:check` script added; all files conform. |
| VIP-FE-M002 | Medium | **Resolved** | Escape closes compact studio overlay panels (and cancels an in-progress keyboard connection). |
| VIP-FE-M003 | Medium | **Resolved** | `VipSwitch` gained an `aria-label`; Feature-Flag switches pass their flag name. |
| VIP-FE-M004 | Medium | **Resolved** | Formula-catalog items are `<button role="option">` in a `role="listbox"`, keyboard-operable with labels. |
| VIP-FE-M005 | Medium | **Partially Resolved** | Delivery dialog derives its subject from the current dashboard name; a rename-after-open sync watcher is deferred (low impact). |
| VIP-FE-M006 | Medium | **Resolved** | `/dashboards/published` defaults its filter to Published via route-name detection. |
| VIP-FE-M007 | Medium | **Partially Resolved** | Tables/lists render skeleton loading states via the shared query layer; a few dense routes still momentarily show resolved-empty — tracked as polish. |
| VIP-FE-M008 | Medium | **Resolved** | Live mode without a base URL now fails closed in staging/CI/production; mock fallback requires an explicit `VITE_ALLOW_MOCK_FALLBACK=true` dev flag. Tests added. |
| VIP-FE-M009 | Medium | **Partially Resolved** | Cancellation is now a distinct `cancelled` error kind (vs `timeout`); `cancelAllRequests()` added; query-building and status mapping tested. Full fetch-level contract tests (headers/upload/download/pagination envelopes) deferred with the E2E harness. |
| VIP-FE-M010 | Medium | **Partially Resolved** | Compact studios collapse panels to overlays and keep a full-width canvas at 390px (verified, no overflow); a dedicated 200%-zoom canvas-minimum pass is deferred. |
| VIP-FE-M011 | Medium | **Deferred** | Profile menu language/timezone/shortcut quick-controls not added; the full Settings → Personal sections cover these. |
| VIP-FE-M012 | Medium | **Resolved** | Demo credentials prefill only in local mock+non-prod; never in live/staging/production. |
| VIP-FE-M013 | Medium | **Deferred** | Connection wizard remains 6-step; reconciling to the documented 8-step flow is a scoped follow-up tied to connector integration. |
| VIP-FE-M014 | Medium | **Partially Resolved** | Global responsive shell hardened; dense-table card/column-priority alternatives for 320–390px deferred. |
| VIP-FE-L001 | Low | **Deferred** | `theme.ts` static+dynamic import chunking warning — cosmetic build note; single-strategy change deferred to avoid churn. |
| VIP-FE-L002 | Low | **Deferred** | Transitive `whatwg-encoding`/`glob` deprecations — upstream; upgrade via tested parent releases. |
| VIP-FE-L003 | Low | **Deferred** | Production source maps — an observability/hosting decision, not a code defect. |

## Summary
- **Critical: 4/4 Resolved.**
- **High: 9 Resolved, 3 Partially Resolved (H007, H008, H009), 1 Deferred (H010).**
- **Medium: 5 Resolved, 5 Partially Resolved, 3 Deferred.**
- **Low: 3 Deferred (non-blocking).**

No Blocker defects existed; none introduced. All four Critical integration gates
and every High security/functional gate blocking backend integration are resolved.
