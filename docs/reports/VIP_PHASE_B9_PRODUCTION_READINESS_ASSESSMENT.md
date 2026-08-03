# VIP Phase B9 — Production-Readiness Assessment & Prioritized Backlog

**Date:** 2026-08-03
**Repository:** `veltrix-intelligence-platform`
**Branch:** `frontend/enterprise-ui-enhancement`
**Commit (HEAD):** `886eb4f7511a153d9a85dd3f3ba17b507636bf11` (merge of PR #2 — Enterprise authorization baseline)
**Working tree:** clean
**Checkpoint tag:** `pre-phase-b9-enterprise-baseline` → `6254d60d445f9b3849fa88d5151bd56cd770f339` (unchanged)
**Method:** read-only code audit (10 parallel evidence agents) + live API smoke tests against the running stack. No product code modified. No migrations. No commits.

> This is an assessment and planning deliverable only. No Phase B9 backlog item has been implemented.

---

## Executive summary

### Current platform readiness
VIP has a **genuinely production-grade platform core** — authentication, the async job/worker subsystem, file handling with malware scanning, the centralized authorization engine, tenant isolation, error contracts, structured logging/metrics, and append-only audit are all real, well-tested, and enforced server-side. The **BI value chain (Connections → Datasets → Semantic → Dashboards)** is real and backend-wired end-to-end, with parameterized SQL and per-resource authorization even on indirect (dashboard-widget) execution paths.

The gaps are concentrated in **(a) a small number of confirmed security/authoring defects introduced or left open during the enterprise-authorization work, (b) one advertised-but-non-functional feature (automatic recurring dashboard delivery), and (c) a set of placeholder modules that must be gated/hidden before production.** None of these are architectural; all are bounded fixes.

### Main strengths
- Argon2id auth with server-side session revocation, refresh rotation + reuse-detection, real DB-backed login lockout, double-submit CSRF, prod-enforced secure cookies.
- Job queue/worker: retry + dead-letter + lease/heartbeat + crash recovery + **DB-authoritative fallback when Redis is down**.
- Files: extension/MIME/magic-byte validation + **enforced ClamAV scanning** (noop scanner rejected in prod) + signed, TTL, permissioned downloads.
- Centralized authorization evaluator with correct precedence (suspended → deny → super-admin → archived → owner → grant/role → default-deny), SQL collection filtering, expiry, ownership; **113 audit call-sites**; tenant isolation enforced at the query layer.
- Semantic/dataset SQL is parameterized with identifier allow-listing; semantic execution is authorization-gated even via dashboards/exports.
- Uniform error envelope with correlation IDs; secret-redacting JSON logs; token-gated, label-sanitized Prometheus metrics; strong production config validators that fail closed on unsafe CORS/host/cookie/secret settings.

### Main risks
1. **Confirmed privilege-escalation** in the role-assignment service (no privilege-ceiling / `is_assignable` / self guards).
2. **Automatic recurring dashboard delivery never fires** — no scheduler exists; `next_run_at` is written but never consumed; cron is unparsed.
3. **Pipeline authoring breaks**: cannot re-publish after first publish; schema-aware editors are empty on load.
4. **Auth recovery controls inert**: self-service password reset has no route; `must_change_password` is never enforced.
5. **Placeholder modules** (Automation, Billing, Developer Portal, Reports, AI, Insights, Marketplace) render blank/broken in live mode and are not gated off.
6. **Production hardening gaps**: no global security headers, uneven rate limiting (unthrottled connection-test outbound primitive), authorization-context N+1s, DB index gaps, no data-retention mechanism.

### Recommended B9 strategy
Sequence strictly: **B9.0 critical stabilization (security + authoring/data blockers)** → **B9.1 core product completion (delivery scheduler, dataset/pipeline gaps)** → **B9.2 production hardening (headers, rate limiting, perf/index/retention)** → **B9.3 UX/accessibility** → **B9.4 deferred modules (gate/hide, then build)**. Gate all placeholder nav behind their already-declared entitlements/feature-flags **now** (a cheap quick win) so nothing broken is user-reachable in production.

**Verdict: `READY TO BEGIN PHASE B9 AFTER CRITICAL FIXES`.**

---

## Module readiness classification

### Production-ready now
| Module / capability | Evidence |
|---|---|
| Auth core: login, logout, refresh/rotation, CSRF, cookies, lockout, session revocation, Argon2id | `auth/{routes,authentication,sessions,cookies,csrf,password,dependencies,rate_limit}.py` |
| Job queue + worker: ordering, retry, dead-letter, lease/heartbeat, restart recovery, Redis-down fallback | `jobs/queue.py`, `jobs/worker.py:160-540` |
| Files: validation + ClamAV scan + signed/TTL/permissioned downloads | `files/{validation,scanning,services,storage}.py` |
| Authorization evaluator: ACL/deny/expiry/ownership/collection filtering/audit | `governance/resource_access.py`, `resource_access_service.py` |
| Tenant isolation (query-layer, non-disclosing 404) | `tenancy/repositories.py:50-133`, `resource_access_service.py:401-405` |
| Connections: create/test/rotate, secrets never exposed, catalog, permissions | `connections/*`, `src/modules/connections/*` |
| Semantic: CRUD, versioning, publish, safe parameterized query, auth-gated execution | `semantic/query.py:76-282`, `semantic/services.py` |
| Dataset core: registration, preview, profile, quality, permissions | `datasets/{services,preview,quality,ingestion}.py` |
| Dashboard: build/edit/save/publish/viewer parity, optimistic locking, on-demand export | `dashboards/*`, `src/modules/dashboards/*` |
| Error contracts, structured logging, Prometheus metrics, audit (113 sites) | `core/{errors,logging,metrics,middleware}.py`, `governance/audit.py` |

### Partially ready
| Module | What works | What's missing |
|---|---|---|
| Pipeline Studio | Create/save/autosave/nodes/edges/undo/redo/formula/validate/run/cancel/retry/logs | Re-publish broken; schema empty on load; read-only surfaces ungated; artifacts not surfaced; run-start/retry still broad-RBAC gated |
| Dataset Studio | Overview/preview/schema/profile/quality (real) | Access/Versions/Activity/Lineage tabs are hardcoded mocks; certification enforced at `edit` not `certify` |
| Dashboard delivery | On-demand export + "send test now" + email | **Recurring schedules never execute; cron unparsed** |
| Auth recovery | Admin-driven reset | Self-service reset has no route; `must_change_password` not enforced; no MFA |
| Admin UX / tenancy | Real org/ws/membership/role/group views | Tenant-lifecycle audit is logs-only (not persisted) |

### Broken / blocked
| Item | Evidence | Severity |
|---|---|---|
| Role-assignment privilege escalation | `role_assignment_service.py:96-191` (no ceiling/`is_assignable`/self guard) | Critical (security) |
| Recurring dashboard delivery does not fire | no scheduler; `scheduling.py:23-24` (cron→now+1m); `dashboard_delivery/services.py:496` writes `next_run_at`, never read | High |
| Pipeline cannot re-publish after first publish | `PipelineStudioView.vue:471` (`:disabled="…||status==='published'"`) | High |
| Pipeline schema-aware editors empty on load | `usePipelineEditor.ts:26-100`, `pipelines.service.ts:114-121` (no init `propagateSchemas`, schema not mapped) | High |
| AuditCenter broken in live | FE calls `/audit`; backend is `/audit-events` (`operations.service.ts:524` vs `governance/routes.py:186`) | Medium |

### Placeholder modules (UI-only unless noted)
| Module | Backend reality | Recommended treatment |
|---|---|---|
| Reports | `/reports*` list routes are empty stubs `[]`; `/reports/:id`, `POST /reports/deliveries` unregistered → 404 (`catalog/routes.py:42-50`) | Gate/hide |
| AI Studio | list stubs `[]`; `streamReply` **throws** in live (`ai.service.ts:399-401`) | Hide/defer |
| Automation Studio | no router registered → all 404 | Hide |
| Insights | `/insights` stub `[]`; `/insights/explain` 404 | Gate/hide |
| Billing | no `/billing/*` route → 404 (mock hardcodes a card) | Hide |
| Marketplace | `/marketplace/extensions` stub `[]` | Gate/hide |
| Developer Portal | no `/developer/*` route → 404; **mock mints fake API keys/secrets** | Hide (do not ship secret-minting mock) |
| Settings persistence | localStorage only (`mock.ts:60`), not tenant-durable | Complete (server settings endpoint) |
| Notifications / Activity / Usage | **Real** backend-wired (`home/routes.py`, `catalog/routes.py:19-32`) | Ship |

---

## Findings by severity

Each finding: Severity · Module · Evidence · User impact · Technical impact · Recommended action · Size · Dependencies · Milestone.

### Critical
**C1 — Role-assignment privilege escalation.**
Module: Governance/RBAC · Evidence: `role_assignment_service.py:96-191`; route only guards `require_permission("role.assign")` (`role_routes.py:225`). Unlike membership (`tenancy/services.py:224-246`) and invitations (`:341-346`), the assignment service performs **no `is_assignable` check, no privilege-ceiling check, and no self-assignment guard**. A holder of `role.assign` can assign `organization_owner`/`organization_admin`/`workspace_admin` to anyone including themselves, escalating beyond the granting admin's own ceiling; `role.assign` can also be packaged into a custom role and handed to a low-privilege user. · User impact: tenant takeover by any user who obtains `role.assign`. · Technical impact: bypasses the ceiling model enforced everywhere else. · Action: add `is_assignable` rejection + subset-of-caller-permissions ceiling (mirror `role_service.py:170-180`) + block self-elevation. · **Size: M** · Deps: none · **Milestone: B9.0**.

### High
**H1 — Automatic recurring dashboard delivery never executes.**
Module: Dashboard delivery · Evidence: no scheduler/beat anywhere; `next_run_at` written (`dashboard_delivery/services.py:496,562`) and indexed (`models.py:134`) but **never queried**; only `test_delivery()` creates runs (`services.py:618-657`); cron unparsed, `next_run()` else-branch returns `now+1m` (`scheduling.py:17-24`); compose has no scheduler service. · User impact: customers who configure daily/weekly/cron deliveries silently receive nothing. · Technical impact: advertised feature is inert. · Action: add a scheduler (dedicated async loop or periodic job handler) doing `WHERE enabled AND next_run_at<=now FOR UPDATE SKIP LOCKED` → create run+export → advance `next_run_at`; implement real cron/time-of-day. · **Size: L** · Deps: job worker (ready) · **Milestone: B9.1** (top item).

**H2 — Pipeline cannot be re-published after first publish.**
Module: Pipeline Studio · Evidence: `PipelineStudioView.vue:196-210,471` — Publish disabled once `status==='published'`; no re-draft transition. · User impact: pipeline edits can never be promoted after the first publish. · Action: allow publish of a newer version / add draft transition. · **Size: S** · **Milestone: B9.0**.

**H3 — Pipeline schema-aware editors empty on load.**
Module: Pipeline Studio · Evidence: `pipelines.service.ts:114-121` (schema not mapped), `usePipelineEditor.ts:26-100` (no `propagateSchemas()` at init). Select/Rename/Formula column pickers + Schema tab are empty until the user perturbs the graph. · User impact: core authoring appears broken after reopening a saved pipeline. · Action: map input/output schema on load and propagate at construction. · **Size: S–M** · **Milestone: B9.0**.

**H4 — Auth recovery controls inert (self-service reset + must_change_password).**
Module: Auth · Evidence: `password_reset.py` fully implemented but **called by no route** (FE "Forgot password?" is cosmetic, `LoginView.vue:106-112`); `must_change_password` column exists (`models.py:68`) and admins set it, but login never checks it and it's absent from `AuthenticatedUser` (`schemas/auth.py:31-48`). · User impact: locked-out users have no recovery; admin-issued temp passwords never forced to rotate. · Action: wire `POST /auth/password-reset/request|confirm` + email; add `must_change_password` to context + gate until changed + `POST /auth/change-password`. · **Size: M** · **Milestone: B9.0**.

**H5 — Unthrottled connection-test outbound primitive + fail-open login limiter.**
Module: Backend API/security · Evidence: `CONNECTION_TEST_RATE_LIMIT_PER_MINUTE` defined (`config.py:115`) but **never wired**; `POST /connections/{id}/test` makes outbound calls with no throttle; login limiter fails open on Redis error (`auth/rate_limit.py:24-28`); no data-plane rate limiting. · User impact: SSRF-adjacent abuse/DoS amplification; brute-force window on Redis outage. · Action: wire the connection-test limiter; fail-closed (or degrade) login limiter; add per-account limiting; add baseline data-plane limits. · **Size: M** · **Milestone: B9.0** (connection-test) / B9.2 (general).

### Medium
**M1 — Pipeline run-start/retry still broad-RBAC gated (permission-model inconsistency).** `pipelines/routes.py` — `run_create`/`run_retry` use `gate("pipeline.execute"|"pipeline.runs.retry")` while read/save/publish/cancel moved to `pipeline_capability` + ACL, so an ACL-elevated operator can cancel but cannot start/retry. Action: route run/retry through the resource evaluator at the `operator` level. Size: S. **B9.1**.

**M2 — Pipeline read-only surfaces ungated.** `PipelineCanvas.vue`, `NodeInspector.vue`, `NodePalette`, keyboard handlers (`PipelineStudioView.vue:263-309`) permit local mutation for viewers/operators (backend blocks persistence, so it's UX-misleading, not a hole). Action: pass `canEdit` into canvas/inspector/palette/keyboard. Size: S–M. **B9.1**.

**M3 — Pipeline artifacts never surfaced.** `file-export` produces artifacts but there is no artifact list/download UI (`PipelineStudioView.vue:640-651`). Size: M. **B9.1**.

**M4 — Dataset four tabs are hardcoded mocks.** Access/Versions/Activity/Lineage in `DatasetDetailView.vue:108-154,353-376` render static data even in live mode (real lineage BFS exists at backend). Action: wire to resource-access/audit/lineage APIs. Size: M (L if Versions/Activity need new endpoints). **B9.1**.

**M5 — Dataset certification enforced at `edit`, not `certify`.** `certification_status` transitions through `update_dataset` (`services.py:268`, edit-gated); no dedicated certify guard. Action: split into a `certify`-gated action. Size: S. **B9.1**.

**M6 — Export visual fidelity is a Python reimplementation.** `dashboard_delivery/rendering.py` (ReportLab/PIL), data-consistent but not pixel-parity with the Vue viewer. Action: document parity limits or move to headless-browser rendering. Size: M–L. **B9.1**.

**M7 — MySQL discovery over-promised.** Catalog advertises MySQL `metadata_discovery` (`catalog.py:194-210`) but discovery has no MySQL adapter (`discovery.py:217-229`) and MySQL lacks `read_only_analytics`; registration/preview/profile/quality/semantic all fail on MySQL. Action: build adapter or trim the advertised capability. Size: L (adapter) / S (trim). **B9.1**.

**M8 — AuditCenter path mismatch.** FE `/audit` vs backend `/audit-events`. Action: fix FE path. Size: S. **B9.1**.

**M9 — No global HTTP security headers.** Only `x-correlation-id`/`x-request-id` set (`core/middleware.py:65-78`); no HSTS/CSP/X-Frame-Options/global nosniff/Referrer-Policy/Permissions-Policy. Action: add a security-headers middleware. Size: S. **B9.2**.

**M10 — Authorization-context N+1s.** Per-quota usage loop (~22 queries) in `resolve_authorization_context` (`services.py:228-240`); `effective_access` re-runs `check_access` per level (~30–45 queries for a 5-level ladder, `resource_access_service.py:579-593`). Action: collapse to grouped aggregates / single evaluation. Size: M. **B9.2**.

**M11 — DB index gaps.** Unindexed semantic-layer FK columns (`semantic_measures/joins/metrics/kpis`, `dataset_quality_rules.field_id`, `dashboard_widgets.semantic_model_id`); `dataset_quality_results` has no tenant index. Action: add indexes (additive migration). Size: S–M. **B9.2**.

**M12 — Tenant-composite FK inconsistency (semantic child tables).** Reference bare `datasets.id`/`dataset_fields.id` instead of the tenant-composite target (`dbe2b0380363:463-533`), weakening DB-level tenant isolation for those rows. Size: M. **B9.2**.

**M13 — No data-retention/partitioning mechanism.** `audit_events`, `dataset_quality_results`, pipeline/job log tables grow unbounded; `expires_at` columns exist but no purge job. Action: retention worker + partition strategy for hot tables. Size: M. **B9.2**.

**M14 — Session/suspension propagation lag & tenant audit persistence.** Suspending a user doesn't revoke live sessions (waits out access TTL, `sessions.py:23-25`); tenant-lifecycle events are logs-only (`tenancy/audit.py:9-31`). Action: revoke-all on suspend; route tenant events through `record_audit`. Size: S each. **B9.2**.

**M15 — Placeholder modules reachable in live.** Automation/Billing/Developer are 404; Reports/AI/Insights/Marketplace return empty stubs; env forces `live` in prod so the mock safety net is gone. Action: gate every placeholder nav behind its declared entitlement/feature-flag defaulted OFF (or hide). Size: S. **B9.4 (do immediately as a quick win)**.

**M16 — Form validation not schema-driven.** zod used only for API envelopes; forms use ad-hoc checks. Size: M. **B9.3**.

### Low
- **L1** Semantic `validate_model` misses transitive cycles; `warnings` always empty (`semantic/services.py:257-297`). S. B9.1.
- **L2** Nav vs route permission mismatches cause dead-clicks (`navigation.ts:95` `dataset.read` vs route `semantic_model.read`). S. B9.3.
- **L3** Inconsistent list/pagination contracts (envelope+total vs bare `list[...]`). S–M. B9.2.
- **L4** Business/transaction logic in some route handlers (`datasets/routes.py:291-317` commits mid-route). S. B9.2.
- **L5** Soft-delete (`archived_at` vs `deleted_at`) and optimistic-lock (`version` vs `row_version`) naming inconsistency. S. B9.2.
- **L6** Legacy/duplicate `dashboard_delivery/worker.py` not wired into compose. S (prune). B9.2.
- **L7** Stale "ACL not yet wired" docstrings (`resource_access.py:6-8`, `models.py:286-288`). XS. B9.2.
- **L8** `VipConfirmDialog` missing on some detail views (`ConnectionDetailView.vue`). S. B9.3.
- **L9** No distributed tracing (OpenTelemetry). Metrics only. M. B9.2.

### Informational (positive)
Uniform error envelope; 113 audit sites with prod enforcement; secret-redacting logs; token-gated metrics; strong prod config validators; tenant-scoped repositories with ACL-consistent pagination counts; comprehensive queue/worker resilience; parameterized SQL throughout.

---

## Security review
- **Confirmed defect:** role-assignment privilege escalation (C1). This is the single must-fix security item before Phase B9 build-out.
- **Auth:** strong (Argon2id, rotation, reuse-detection, lockout, server revocation, CSRF, prod-secure cookies). Gaps: no MFA (greenfield), inert `must_change_password` + dead password-reset (H4), rate-limit fail-open + unthrottled connection-test (H5), suspension propagation lag (M14).
- **SSRF:** validated at connection-validate time (private/loopback/link-local/metadata/scheme blocked) but a resolve-then-connect TOCTOU/DNS-rebinding window remains (drivers re-resolve). Combine with M/H rate-limiting on the test endpoint. Size: M. B9.2.
- **Secrets:** never returned by any API; AES-256-GCM at rest with AAD binding; single static env key (no rotation) — add key-rotation. B9.2.
- **SQL:** parameterized + identifier allow-listing everywhere; one low-risk re-interpolation spot in `quality.py:216-219` (guarded). 
- **Headers:** missing (M9). **Tenant isolation:** enforced at query layer (strong).

## Performance review
- Authorization context is request-scoped cached but rebuilt per first request with ~30 queries incl. a 22-iteration quota N+1 (M10); `effective_access`/simulate are per-level N+1 (M10). No shared/Redis cache — consider short-TTL context cache with mutation invalidation. B9.2.
- Pipeline schema propagation is ~O(n²·e) per mutation and `nodeIssues` recomputes full validation reactively — fine for modest graphs, degrades large ones. B9.2/B9.3.
- Dashboard widget queries are bounded-concurrent (8). Semantic queries are config-bounded + quota-metered + result-size capped. Good.

## Database review
- Chain linear, single head `20260728_0018`, ORM/migration parity clean (`alembic check` → no drift), forward migrations data-safe, FK `ondelete` coverage strong, tenant-scoped uniqueness extensive.
- Gaps: index gaps on secondary/semantic FK columns + `dataset_quality_results` tenant index (M11); tenant-composite FK inconsistency in semantic child tables (M12); no retention/partitioning (M13); soft-delete/lock naming inconsistency (L5). No backup/DR migration evidence.

## Worker & operational review
- Job/worker subsystem is production-grade: retry, dead-letter, lease/heartbeat, expired-lease recovery, graceful shutdown, Redis-down DB-authoritative fallback. ClamAV enforced. Signed/TTL/permissioned downloads. Observability via heartbeats + job logs/progress/attempts + Prometheus.
- The one operational hole: **no scheduler process** (H1). Legacy duplicate delivery worker should be pruned (L6). No OTel tracing (L9). Backups/DR/rollback runbook not evidenced — add for B9.2.

## Frontend & UX review
- Strong: single typed `apiClient` with single-flight refresh, dual error-envelope parsing, correlation IDs; `useQuery`/`useMutation` server-state layer; RBAC/entitlement/flag-aware router guard + nav; toast + aria-live integration; consistent studio chrome; forced-live in prod with fail-closed config.
- Weak/gaps: placeholder modules reachable (M15); form validation not schema-driven (M16); confirm-dialog coverage list-centric (L8); nav/route permission mismatches (L2); pipeline read-only surfaces ungated (M2); settings localStorage-only. a11y foundation is good but only one tagged E2E spec (expand coverage).

## Test & CI review
Authoritative current totals (this environment):
| Suite | Count |
|---|---|
| Backend unit | ~196 passing (177 `test_` fns across 22 files) |
| Backend integration | 35 passing (19 files) |
| Frontend unit (vitest) | 266 passing (42 spec files) |
| Browser E2E | 15 spec files × 5 Playwright projects (chrome-desktop, edge-desktop, firefox-desktop, chrome-high-dpi, chromium-mobile) |
| Accessibility | 1 `@a11y`-tagged spec (runs inside the browser job) |
| CI jobs | 5: `static-and-unit`, `browser`, `backend-static-and-unit`, `backend-integration`, `backend-container` — all green on HEAD |

Gaps: no tests for the three highest-impact pipeline defects (re-publish, load-time schema, read-only gating); no test for `must_change_password`/reset routes (they don't exist); **no negative test for the role-assignment escalation** (C1); no scheduler/delivery-execution test (feature absent); a11y coverage is a single spec; no performance or worker-crash-recovery E2E; local E2E depends on a clean seed (CI is authoritative). Add negative-security tests as each B9.0 fix lands.

---

## Phase B9 backlog (numbered)

| ID | Title | Sev | Module | Deps | Size | Milestone |
|---|---|---|---|---|---|---|
| B9-01 | Add ceiling/`is_assignable`/self guards to role-assignment | Critical | RBAC | — | M | B9.0 |
| B9-02 | Fix pipeline re-publish (draft→publish transition) | High | Pipelines | — | S | B9.0 |
| B9-03 | Load-time schema mapping + propagation | High | Pipelines | — | S–M | B9.0 |
| B9-04 | Wire self-service password reset + enforce `must_change_password` | High | Auth | email | M | B9.0 |
| B9-05 | Wire connection-test rate limiter; fail-closed login limiter | High | API/security | Redis | M | B9.0 |
| B9-06 | Gate/hide all placeholder nav behind entitlement/flag (OFF) | Med | FE/nav | — | S | B9.0 (quick win) |
| B9-07 | Delivery scheduler + real cron/time-of-day | High | Delivery | jobs | L | B9.1 |
| B9-08 | Route pipeline run/retry through resource evaluator (operator) | Med | Pipelines | — | S | B9.1 |
| B9-09 | Gate pipeline read-only surfaces (canvas/inspector/palette/keys) | Med | Pipelines | — | S–M | B9.1 |
| B9-10 | Surface pipeline artifacts (list + signed download) | Med | Pipelines | files | M | B9.1 |
| B9-11 | Wire 4 dataset mock tabs to real APIs | Med | Datasets | audit/version ep | M–L | B9.1 |
| B9-12 | Enforce `certify` on dataset certification | Med | Datasets | — | S | B9.1 |
| B9-13 | Fix AuditCenter path `/audit`→`/audit-events` | Med | FE/ops | — | S | B9.1 |
| B9-14 | MySQL discovery adapter OR trim advertised capability | Med | Connections/Datasets | — | L/S | B9.1 |
| B9-15 | Export fidelity: document limits or headless rendering | Med | Delivery | — | M–L | B9.1 |
| B9-16 | Global security-headers middleware (HSTS/CSP/XFO/nosniff/…) | Med | API | — | S | B9.2 |
| B9-17 | Rate limiting: per-account + data-plane baseline | Med | API | Redis | M | B9.2 |
| B9-18 | Fix authorization-context + effective-access N+1s | Med | RBAC/perf | — | M | B9.2 |
| B9-19 | Short-TTL AuthorizationContext cache w/ invalidation | Low | RBAC/perf | Redis | M–L | B9.2 |
| B9-20 | Add indexes (semantic FKs, quality_results tenant) | Med | DB | migration | S–M | B9.2 |
| B9-21 | Fix tenant-composite FKs in semantic child tables | Med | DB | migration | M | B9.2 |
| B9-22 | Retention/partitioning for audit/quality/log tables | Med | DB/ops | — | M | B9.2 |
| B9-23 | Revoke live sessions on suspend; persist tenant audit | Med | Auth/tenancy | — | S | B9.2 |
| B9-24 | SSRF TOCTOU hardening + secret key rotation | Med | Connections | — | M | B9.2 |
| B9-25 | Schema-driven form validation (shared zod layer) | Med | FE | — | M | B9.3 |
| B9-26 | Confirm-dialog coverage on detail views | Low | FE | — | S | B9.3 |
| B9-27 | Fix nav/route permission mismatches (dead-clicks) | Low | FE | — | S | B9.3 |
| B9-28 | Expand accessibility E2E coverage | Med | FE/tests | — | M | B9.3 |
| B9-29 | Server-side settings persistence | Med | FE/API | — | M | B9.3 |
| B9-30 | Build Reports backend (then ungate) | — | Reports | — | L | B9.4 |
| B9-31 | Build AI Studio backend + streaming | — | AI | — | Program | B9.4 |
| B9-32 | Build Automation/Billing/Marketplace/Developer backends | — | Deferred | — | Program | B9.4 |

**Acceptance criteria (representative):**
- **B9-01:** a user holding only `role.assign` cannot assign a non-assignable or above-ceiling role, nor self-elevate; covered by a new negative integration test; existing assignment tests still pass.
- **B9-02:** publishing a modified pipeline after a prior publish creates a new published version; UI enables Publish when dirty vs published.
- **B9-03:** reopening a saved pipeline populates Select/Rename/Formula column pickers and the Schema tab without any graph mutation.
- **B9-04:** `POST /auth/password-reset/request|confirm` work end-to-end with email; a user with `must_change_password` is forced through `POST /auth/change-password` before any other action; both covered by integration tests.
- **B9-05:** connection-test is throttled per the configured limit; login limiter denies (not fails open) on Redis outage.
- **B9-06:** in live/prod build, no placeholder module is reachable unless its entitlement/flag is explicitly enabled.
- **B9-07:** an enabled daily/weekly/cron schedule produces a delivery run+export at the correct next occurrence without manual action; `next_run_at` advances; covered by a scheduler test.

---

## Recommended Phase B9 milestones
- **B9.0 — Critical stabilization:** B9-01 … B9-06. Security escalation, pipeline authoring blockers, auth recovery, connection-test throttle, gate placeholders. Exit: no known security/authoring blocker; nothing broken is user-reachable.
- **B9.1 — Core product completion:** B9-07 … B9-15. Delivery scheduler, pipeline permission/UX/artifacts, dataset tabs/certify, audit path, MySQL honesty, export fidelity.
- **B9.2 — Production hardening:** B9-16 … B9-24. Security headers, rate limiting, perf/N+1, indexes/FKs, retention, suspension propagation, SSRF/key rotation.
- **B9.3 — UX & accessibility:** B9-25 … B9-29. Form validation, confirm dialogs, nav fixes, a11y coverage, settings persistence.
- **B9.4 — Deferred modules:** B9-30 … B9-32. Build Reports/AI/Automation/Billing/Marketplace/Developer backends, then ungate.

---

## Do-not-start list
- **Do not** build any placeholder-module backend (Reports, AI, Automation, Billing, Marketplace, Developer Portal) before B9.0 and the B9.1 scheduler are complete.
- **Do not** add features on top of the role-assignment escalation (B9-01) — fix it first.
- **Do not** enable placeholder nav tiles in production until B9-06 gating lands.
- **Do not** ship the Developer Portal mock (mints fake API keys/secrets) in any build.
- **Do not** advertise MySQL analytics/discovery until B9-14 resolves the adapter gap.
- **Do not** rely on recurring dashboard delivery until B9-07 ships (today it silently never fires).
- **Do not** treat local full-suite E2E failures as product regressions — the CI clean-seed run is authoritative.

---

## Environment snapshot (assessment run)
| Component | State |
|---|---|
| Docker Compose | api, postgres, redis, clamav, dashboard-worker, pipeline-worker — all healthy (mysql profile optional) |
| API | `GET /health` 200, `GET /ready` 200 |
| Frontend | `http://localhost:3009` 200 (live mode, base `…:8000/api/v1`) |
| PostgreSQL / Redis | reachable (readiness probe passes) |
| Workers | dashboard-worker + pipeline-worker healthy (heartbeats) |
| Alembic | current `20260728_0018`, single head, `alembic check` → no drift |
| Live module smoke (admin) | home/roles/groups/connections/pipelines/datasets/semantic-models/dashboards/jobs/notifications → 200 |

*Left running at `http://localhost:8000` and `http://localhost:3009` per instructions.*
