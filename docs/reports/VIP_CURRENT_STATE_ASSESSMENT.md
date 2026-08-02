# VIP — Current State Assessment

> Independent, code-verified assessment. Reports in `docs/reports/` and `docs/validation/` were
> treated as claims and cross-checked against source. No product code, migrations, dependencies, or
> commits were changed to produce this document. No test suites were executed, so no pass/fail
> results are asserted here.

---

## 1. Executive summary

VIP is a genuinely substantial full-stack platform whose **data and platform core is real and
well-engineered**, wrapped in a broad UI that also includes several **not-yet-backed "coming soon"
surfaces**. The security foundation (cookie sessions, CSRF, lockout, fixed-role RBAC, tenant
isolation, persistent governance audit, super-admin console) and the primary studios (Connections,
Datasets, Semantic, Dashboards + exports, Pipelines) are implemented with real database-backed logic
and asynchronous workers. Conversely, AI Studio, Automation Studio, Insights, Marketplace, Reports,
Billing, and the Developer portal are UI-first with placeholder or empty backends.

The single most important nuance: the frontend is a **hybrid app** that defaults to rich in-browser
mocks (`VITE_API_MODE=mock`). In mock mode, nearly every screen looks complete. In live mode
(required for staging/production), the mature domains work end-to-end while the placeholder domains
degrade to honest empty states — and a few actions (AI chat streaming, webhook creation) fail or
no-op. Production-readiness must therefore be judged in **live mode**, not from the mock UI.

## 2. What is implemented (production-ready or near it)

- **Authentication & sessions**: opaque HttpOnly cookie sessions, Argon2id hashing, refresh rotation
  with reuse detection, per-account lockout, per-IP login rate limiting, CSRF (double-submit +
  origin).
- **Tenancy**: organizations, workspaces, memberships, invitations; header-based tenant context with
  non-disclosing 404s; repository-level tenant filtering and composite tenant FKs.
- **Governance**: fixed system roles, permission catalog, feature flags, entitlements, atomic
  quotas, persistent audit; dependency-based enforcement with a route-policy coverage test.
- **Platform super-admin console**: cross-tenant org/user/workspace management, suspension, admin
  password reset, fully audited, gated by a non-disclosing 404.
- **Connection Studio + secrets**: real PostgreSQL/MySQL/HTTP testers, AES-GCM encrypted write-only
  credentials with versioned rotation, SSRF/network guards, quotas, audit.
- **Dataset Studio**: catalog, metadata discovery, live preview/profiling, CSV/file ingestion,
  quality rules + async evaluations, lineage graph (PostgreSQL-centric).
- **Semantic layer**: models/dimensions/measures/metrics/KPIs, glossary, immutable versions, and a
  safe parameterized read-only PostgreSQL query compiler/executor.
- **Dashboard Studio**: pages/widgets/filters editor with optimistic locking, publish/versioning,
  sharing, snapshots, and real widget queries via the semantic engine.
- **Dashboard exports**: async PDF/PNG/JSON/CSV rendering, retry/cancel, retention, HMAC signed
  downloads.
- **Pipeline Studio + execution**: node-graph authoring, formula DSL, graph validation, immutable
  versions, durable async runs with leases/heartbeats/attempts/node tracking, artifacts + signed
  downloads.
- **Platform services**: durable job platform (queues, retries, dead letters, progress, worker
  heartbeats), files/storage with malware scanning and signed downloads, and resumable SSE over
  Redis Streams.

## 3. What is partially implemented

- **Dashboard delivery scheduling**: schedule CRUD + on-demand "test delivery" + email rendering are
  real, but **no daemon scans `next_run_at`** for due runs and cron expressions are validated but not
  parsed — recurring delivery is effectively manual.
- **Datasets / semantic across connectors**: analytics (preview, profile, query, pipeline source
  reads, CSV ingest) assume **PostgreSQL**; non-PostgreSQL connectors can be tested but not queried
  (`QUERY_CONNECTOR_UNSUPPORTED`).
- **Audit**: governance/domain/platform events persist to `audit_events`, but tenancy events are
  **log-only**, and `AUDIT_*` enable flags are not checked at write time.
- **Home / notifications**: real aggregation, but `pendingApprovals` is always 0, health sparklines
  are static repeats, the unread-notifications badge is hardcoded (4), and there is no read/unread
  state.
- **Invitations / password reset**: invitation tokens and password-reset tokens exist server-side,
  but there is **no production email delivery** and **no self-service reset routes**.
- **Datasets detail UI**: access/versions/activity tabs in `DatasetDetailView.vue` render **mock**
  data even in live mode.
- **Developer portal**: API key creation is wired to a service, but **webhook creation is toast-only**.

## 4. What is missing / not implemented

- **Resource-level access control**: `governance/resource_access.py` + `resource_access_entries`
  table + unit tests exist, but the evaluator is **not wired into any route** (foundation only).
- **Custom roles, direct-user permissions, and group-based RBAC**: not present (fixed system roles
  only).
- **Authorization/feature-flag/entitlement/quota caching**: config TTLs exist; runtime cache is not
  built (`AUTHORIZATION_CACHE_ENABLED` defaults false).
- **AI Studio backend**: catalog endpoints return `[]`; live chat streaming throws "not implemented".
- **Automation Studio backend**: no package; builder does not persist.
- **Billing backend**: none; plan/usage are hardcoded UI.
- **Marketplace / Insights backend**: catalog stubs returning `[]`.
- **Reports backend**: catalog stubs returning `[]`; builder is local-state only.
- **Self-service Settings persistence**: profile/appearance/security saves are UI-only.
- **MFA** and **external KMS secret provider**: not present.

## 5. Production-ready areas

Auth/sessions, platform admin console, connections + secrets, dashboards (core + exports),
pipelines (authoring + execution), jobs, files, and SSE events are production-ready in live mode
(subject to standard deployment hardening: HTTPS, secure cookies, real signing/encryption keys,
correct CORS/CSRF origins, trusted hosts, and rotated secrets).

## 6. High-risk areas

1. **Placeholder surfaces shipped as if complete** — AI/Automation/Insights/Marketplace/Reports/
   Billing/Developer screens can mislead stakeholders into thinking features exist; in live mode they
   are empty or fail. Risk: expectation/scope mismatch and demo-vs-reality confusion.
2. **Recurring dashboard delivery** — schedules can be created but never fire automatically; users may
   assume deliveries are being sent. Operational metrics track "late" schedules but nothing claims
   them.
3. **Resource ACL designed but not enforced** — any code or docs implying per-resource sharing/deny
   is authoritative would be incorrect today; enforcement is still role-union based.
4. **Single-connector analytics** — datasets/semantic/pipelines are effectively PostgreSQL-only for
   query/execution despite a broader connector catalog.
5. **Mock fallback in development** — easy to mistake mock behavior for working live behavior;
   assessments should always be done with `VITE_API_MODE=live`.

## 7. Security and tenancy observations

- **Strengths**: opaque hashed tokens with purpose separation; refresh-reuse detection; fail-closed
  permission checks (unknown keys denied); non-disclosing 404s for cross-tenant and super-admin
  access; encrypted write-only connection secrets; SSRF guards on connection tests; HMAC signed,
  single-use, expiring download tokens for files/exports/artifacts; pervasive composite tenant FKs.
- **Gaps / to verify**:
  - Tenancy audit is not persisted (only governance/domain/platform events are) — audit completeness
    is partial.
  - `GOVERNANCE_FAIL_CLOSED` is validated as config but not referenced at runtime — confirm intended
    behavior.
  - `must_change_password` is stored but not enforced at login.
  - No authorization caching means every request resolves permissions from the DB — a performance
    (not security) consideration.
  - Resource-level deny/allow is not enforced; treat any resource-sharing UI as advisory until wired.

## 8. Frontend/backend inconsistencies

- **AI chat**: UI offers streaming chat; live adapter throws `AI streaming is not implemented`.
- **Reports/AI/Insights/Marketplace**: UI lists content; live backends return `[]` (empty states).
- **Automation builder / Settings / Favorites / Dashboard templates**: UI implies persistence; state
  is local/hardcoded with no backend calls.
- **Developer webhooks**: UI implies creation; no API call is made (toast only).
- **Billing plan**: UI shows a concrete plan/price; backend has no billing and the frontend
  hardcodes `plan: enterprise`.
- **Datasets detail**: access/versions/activity tabs show mock rows even against the live API.

## 9. End-to-end journey traces (verified)

- **Journey A — User access**: `LoginView` → `POST /auth/login` (cookies) → `auth.bootstrap`/
  `GET /auth/me` → `platform.bootstrapTenancy` (`/organizations`, `/workspaces`) → org/workspace
  selection persisted per user → `authorization.bootstrap` (`/authorization/context`) → router
  gates. **Status: works end-to-end.** Audit: login/denials recorded.
- **Journey B — Connection lifecycle**: `ConnectionWizard` → `POST /connections` (validate against
  type catalog, encrypt secret, consume quota, audit) → `POST /{id}/test` (real tester) → health
  status → `PATCH`/credentials rotate → archive/delete. **Status: works end-to-end** (secrets never
  returned; SSRF/network guards enforced).
- **Journey C — Pipeline lifecycle**: `PipelineStudio` → `PUT /{id}` save draft → `POST /{id}/validate`
  → `POST /{id}/publish` (immutable version) → `POST /{id}/runs` (quota, 202) → `pipeline-worker`
  claims with lease → executes nodes → logs/attempts/artifacts → cancel/retry → signed artifact
  download. **Status: works end-to-end** (PostgreSQL sources; events published to SSE).
- **Journey D — Dataset lifecycle**: `POST /datasets` or `/discover` → schema discovery → `/preview`
  + `/profile` → field metadata `PATCH` → quality rules + async `dataset.quality` job → lineage
  edges → query via semantic engine. **Status: works end-to-end for PostgreSQL**; certification is
  metadata-only; detail UI tabs partly mocked.
- **Journey E — Dashboard lifecycle**: `DashboardStudio` → `PUT /{id}/editor` (optimistic lock) →
  add pages/widgets/filters → `POST /{id}/widgets/{wid}/data` (semantic query) → `POST /{id}/publish`
  → `GET /{id}/viewer` → shares → snapshots → export → **delivery schedule created but not
  auto-run**. **Status: works end-to-end except recurring delivery automation.**
- **Journey F — Export lifecycle**: `POST /dashboards/{id}/exports` (quota, 202) → job enqueued →
  worker claims (`SKIP LOCKED`) → renders (ReportLab/Pillow/JSON/CSV) → artifact stored → `POST
  .../download-token` (HMAC) → `GET .../download` → audit → retention cleanup. **Status: works
  end-to-end.**

## 10. Test and QA gaps

- Backend: ~30 test files (19 unit, 11 integration) + `conftest.py`; markers `unit`/`integration`/
  `security`; integration tests are collection-skipped unless `RUN_INTEGRATION_TESTS=1` (need
  Postgres/Redis). `test_migrations` validates head/upgrade/downgrade. `test_resource_access`
  covers the (unwired) ACL evaluator.
- Frontend: 37 Vitest specs + 15 Playwright e2e specs (serial, live API mode, 5 browser projects,
  includes `@a11y`).
- **Gaps**: placeholder modules (AI, automation, insights, marketplace, reports, billing, developer,
  settings) have little/no meaningful backend test coverage because they have little/no backend;
  resource-ACL has unit tests but no route/integration tests (nothing to integrate yet); delivery
  scheduling lacks an automated-run test because the runner does not exist. **No suites were executed
  for this assessment** — prior reports claiming "all tests pass" were not re-verified and should be
  re-run in CI to confirm against the current tree (note the uncommitted `resource_access` changes).

## 11. Technical debt

- Two overlapping platform-admin surfaces (`/platform` vs `/admin/platform`).
- Custom SVG chart library (no third-party) — capable but higher maintenance for advanced viz.
- Repository layer is inconsistent (present for connections/datasets, absent elsewhere — services
  query models directly).
- Config flags without runtime implementations (authorization caching, `GOVERNANCE_FAIL_CLOSED`,
  `TENANCY_REQUIRE_WORKSPACE_BY_DEFAULT`, `AUDIT_*` at write time).
- Mock/live dual implementations for many domains increase surface area and drift risk between the
  two paths.
- PostgreSQL-only analytics coupling across datasets/semantic/pipelines.

## 12. Recommended next priorities

1. Implement the recurring **delivery scheduler daemon** (scan `next_run_at`, parse cron) or clearly
   disable schedule creation until available.
2. **Wire the resource-access evaluator** into dashboard/pipeline/dataset/connection routes (or mark
   it clearly as future) so RBAC semantics match any resource-sharing UI.
3. Add **self-service password reset** routes + email delivery, and enforce `must_change_password`.
4. Persist **tenancy audit** events and honor `AUDIT_*`/`GOVERNANCE_FAIL_CLOSED` at runtime.
5. Replace **mock UI tabs and placeholder actions** (dataset detail tabs, settings save, developer
   webhooks, favorites) with real endpoints or explicit "coming soon" gating.
6. Decide the roadmap for **AI/Automation/Insights/Marketplace/Reports/Billing** — either build
   backends or hide/flag them to avoid stakeholder confusion.
7. Broaden **connector support** for analytics beyond PostgreSQL, or document the constraint clearly.
8. Implement **authorization caching** to reduce per-request DB load at scale.

## 13. Items requiring manual verification

- Actual **test suite results** on the current tree (unit + integration + e2e). A controlled
  baseline run was subsequently performed — see `docs/reports/VIP_BASELINE_VALIDATION_REPORT.md`
  (backend unit 156 passed; integration 27 passed on a clean migrated `_test` DB; frontend Vitest
  206 passed; build passed). The CI Playwright browser job (live-mode UI E2E) was not run here.
- Whether the uncommitted files (`governance/models.py` change, `resource_access.py`,
  `20260728_0016_*` migration, `test_resource_access.py`) are intended to be committed. **Note
  (confirmed in baseline run):** `alembic check` currently FAILS because the `ResourceAccessEntry`
  ORM model declares `created_at`/`updated_at` as `NOT NULL` while migration `20260728_0016`
  creates them nullable — a model/migration drift that must be reconciled before this work is
  committed. `mypy --strict` also reports 25 errors in `test_resource_access.py` (under-annotated
  helpers).
- Behavior of **ClamAV** scanning under load and on large uploads (API default scanner is `clamav`,
  worker default is `noop`).
- **SMTP delivery** against a real provider (default is the file outbox provider).
- Real **production security posture** (cookie `Secure`/domain, CORS/CSRF origins, trusted hosts,
  rotated signing/encryption keys) — Compose defaults are development-only.
- Performance/scalability of per-request authorization resolution and synchronous semantic/dashboard
  queries under concurrency.
- Accuracy of prior `docs/reports/*` certification claims (several assert broad readiness; this
  assessment found meaningful placeholder surfaces they may overstate).
