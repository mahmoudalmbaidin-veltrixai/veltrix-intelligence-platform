# VIP — Module Catalog

> Verified module-by-module catalog. Status labels are assigned from code evidence (backend logic,
> frontend wiring, permissions, tenancy, tests), not from the mere existence of routes or screens.
> Frontend paths are under `src/modules/`; backend packages under `apps/api/src/vip_api/`.

**Status legend**: Production-ready · Implemented with minor gaps · Partially implemented ·
Prototype · Placeholder · Disabled · Legacy · Not implemented · Broken · Unable to verify.

---

## 1. Authentication and Sessions

- **Business purpose**: Secure sign-in and session lifecycle for all users.
- **Persona**: All users.
- **Frontend**: `modules/auth/LoginView.vue`; `shared/stores/auth.ts`; `shared/services/auth/apiAuthService.ts` (always live).
- **Backend**: `auth/` (`routes.py`, `authentication.py`, `sessions.py`, `cookies.py`, `csrf.py`, `password.py`, `password_reset.py`, `rate_limit.py`, `models.py`).
- **API surface**: `POST /auth/login`, `GET /auth/me`, `POST /auth/refresh`, `POST /auth/logout`.
- **DB entities**: `users`, `auth_sessions`, `password_reset_tokens`.
- **Dependencies**: Redis (login rate limit), governance/tenancy for post-login context.
- **Status**: **Production-ready** (core). Password-reset self-service is **Not implemented** (service exists, no public routes/email); `must_change_password` stored but not enforced.
- **Limitations**: No MFA; no self-service password reset UI/route.
- **Test coverage**: `tests/unit/test_auth_security.py`, `tests/integration/test_authentication.py`; frontend login e2e.
- **Production-readiness**: Ready for cookie-session auth; add reset + MFA for completeness.

## 2. Platform Administration

- **Business purpose**: Cross-tenant operator console for orgs, users, workspaces, suspension, and admin password reset.
- **Persona**: Platform super-admin (`users.is_platform_admin`).
- **Frontend**: `modules/platform/PlatformConsoleView.vue` (route `/platform`, live). A simpler `modules/admin/PlatformAdminView.vue` also exists at `/admin/platform`.
- **Backend**: `platform_admin/` (`routes.py`, `services.py`, `dependencies.py`).
- **API surface**: `/api/v1/platform/*` — overview, orgs list/create/detail/suspend/activate, users list/create/suspend/activate/update/access-summary/reset-password, org+workspace member add/remove, workspace create/suspend/activate. (Full list in `VIP_API_INVENTORY.md`.)
- **DB entities**: reads/writes across `users`, `organizations`, `workspaces`, memberships; audits via `audit_events`.
- **Dependencies**: super-admin gate; CSRF; tenancy models.
- **Status**: **Production-ready**. Non-disclosing 404 for non-admins; all mutations audited; CLI grants the flag.
- **Limitations**: Two overlapping admin surfaces (`/platform` vs `/admin/platform`).
- **Test coverage**: `tests/unit/test_platform_admin*.py`, `tests/integration/test_platform_infrastructure.py`, e2e platform-admin.
- **Production-readiness**: Ready.

## 3. Users

- **Business purpose**: User identity records, status, and profile.
- **Persona**: Platform admin (create/manage); self (profile view).
- **Frontend**: managed via admin/platform consoles + `modules/settings/SettingsView.vue` (profile is UI-only).
- **Backend**: `auth/models.py::User`; managed through `platform_admin` and `tenancy` memberships.
- **API surface**: creation/updates via `/api/v1/platform/users*`; self via `GET /auth/me`.
- **DB entities**: `users` (username, optional email, status enum, `is_platform_admin`, `failed_login_count`, `locked_until`, `must_change_password`, `deleted_at`).
- **Status**: **Implemented with minor gaps** — backend user management is real; self-service profile editing (Settings) is not persisted.
- **Limitations**: No self-service profile/password update endpoints.
- **Test coverage**: covered indirectly via auth + platform admin tests.
- **Production-readiness**: Admin-managed users are production-ready; self-service is placeholder.

## 4. Organizations

- **Business purpose**: Top-level tenant boundary.
- **Persona**: Org owners/admins; platform admins.
- **Frontend**: `modules/admin/OrgAdminView.vue`; org switcher in `AppTopbar`; `shared/stores/platform.ts`; `shared/services/tenancy/apiTenancyService.ts`.
- **Backend**: `tenancy/` (routes/services/repositories/models).
- **API surface**: `GET/POST /api/v1/organizations`, `GET/PATCH /api/v1/organizations/{id}`.
- **DB entities**: `organizations` (status enum, `deleted_at`).
- **Dependencies**: governance (roles/quotas), auth.
- **Status**: **Implemented with minor gaps** (tenancy audit is log-only; `plan` is hardcoded `enterprise` in the frontend mapping).
- **Test coverage**: `tests/integration/test_tenancy.py`; e2e organization-create.
- **Production-readiness**: Ready for core CRUD.

## 5. Workspaces

- **Business purpose**: Sub-tenant boundary within an organization that scopes most resources.
- **Persona**: Workspace admins; org admins; platform admins.
- **Frontend**: `modules/admin/WorkspaceAdminView.vue`; workspace switcher in topbar; `platform` store.
- **Backend**: `tenancy/` (workspace routes/repos).
- **API surface**: `GET/POST /api/v1/organizations/{org}/workspaces`, `GET/PATCH /api/v1/organizations/{org}/workspaces/{ws}`.
- **DB entities**: `workspaces` (status enum incl. `suspended`, `deleted_at`, default-workspace partial unique index).
- **Status**: **Implemented with minor gaps** (`TENANCY_REQUIRE_WORKSPACE_BY_DEFAULT` unused; modules self-check `workspace_id`).
- **Test coverage**: `tests/integration/test_tenancy.py`; e2e tenant-isolation.
- **Production-readiness**: Ready.

## 6. Memberships

- **Business purpose**: Bind users to orgs/workspaces with a role.
- **Persona**: Org/workspace admins; platform admins.
- **Frontend**: `modules/admin/MembersView.vue`.
- **Backend**: `tenancy/` (`MembershipRepository`, invitation routes).
- **API surface**: org members list/update/remove; workspace members list/add/remove; invitations create/list/revoke; `POST /api/v1/invitations/accept`.
- **DB entities**: `organization_memberships`, `workspace_memberships`, `invitations`, `invitation_workspaces`.
- **Status**: **Implemented with minor gaps** — invitation token is returned in response only in dev/test; no production email delivery.
- **Test coverage**: `tests/integration/test_tenancy.py`.
- **Production-readiness**: Ready except invitation email delivery.

## 7. Roles and Permissions (Governance / RBAC)

- **Business purpose**: Authorize actions; expose feature flags, entitlements, quotas, and audit.
- **Persona**: Org admins (read); platform (seed).
- **Frontend**: `modules/admin/GovernanceView.vue` + `FeatureFlagsView.vue` (read-only); `shared/stores/authorization.ts`; gate components in `shared/authorization/`.
- **Backend**: `governance/` (`routes.py`, `services.py`, `policies.py`, `dependencies.py`, `route_policy.py`, `audit.py`, `models.py`, `resource_access.py`).
- **API surface**: `/api/v1/authorization/context`, `/roles`, `/permissions`, org `/entitlements` `/feature-flags` `/quotas`, `/audit-events`.
- **DB entities**: `permissions`, `roles`, `role_permissions`, `entitlements`, `organization_entitlements`, `feature_flags`, `feature_flag_overrides`, `quota_definitions`, `organization_quotas`, `quota_usage`, `audit_events`, `resource_access_entries`.
- **Status**: **Implemented with minor gaps**. Fixed system roles only (no custom roles/direct-user/groups). Resource-level ACL (`resource_access.py`, `resource_access_entries`) is **foundation only — not wired into any route**. Authorization caching configured but not built. `GOVERNANCE_FAIL_CLOSED` not referenced at runtime.
- **Test coverage**: `tests/unit/test_governance_policies.py`, `tests/unit/test_resource_access.py`, `tests/integration/test_governance.py`; e2e governance personas.
- **Production-readiness**: Ready for fixed-role RBAC + flags/entitlements/quotas; resource ACL is not yet enforced.

## 8. Connection Studio

- **Business purpose**: Register, test, and manage tenant data-source connections.
- **Persona**: Data engineers / workspace editors.
- **Frontend**: `modules/connections/*` (List, ConnectorCatalog, Wizard, Detail) — always live.
- **Backend**: `connections/` (routes, services, repositories, testers, secrets, catalog, models).
- **API surface**: `/api/v1/connections` CRUD + `/types`, `/{id}/test`, credentials update/rotate, archive. (See inventory.)
- **DB entities**: `connection_types`, `connections`, `connection_secrets`.
- **Status**: **Production-ready** — real PostgreSQL/MySQL/HTTP testers, AES-GCM encrypted secrets, quota + audit, SSRF/network guards.
- **Limitations**: Downstream analytics (preview/query/pipeline execution) are PostgreSQL-centric.
- **Test coverage**: `tests/unit/test_connection_security.py`, `test_connector_registry.py`; `tests/integration/test_connections.py`, `test_b5_database.py`; e2e connections + catalog.
- **Production-readiness**: Ready.

## 9. Secrets and Credentials

- **Business purpose**: Store connection credentials write-only and encrypted, with versioned rotation.
- **Persona**: Data engineers.
- **Frontend**: within Connection Detail (update/rotate actions).
- **Backend**: `connections/secrets.py` (`DatabaseEncryptedSecretProvider`, AES-GCM, versioned rows).
- **API surface**: `PUT /connections/{id}/credentials`, `POST /connections/{id}/credentials/rotate`.
- **DB entities**: `connection_secrets` (immutable versions, tenant-scoped).
- **Dependencies**: `CONNECTION_ENCRYPTION_KEY` (+ version), `CONNECTION_SECRET_PROVIDER`.
- **Status**: **Production-ready** (secrets never returned in responses).
- **Test coverage**: `tests/unit/test_connection_security.py`.
- **Production-readiness**: Ready; external KMS provider not present (database-encrypted only).

## 10. Pipeline Studio

- **Business purpose**: Author data pipelines as node graphs with versions.
- **Persona**: Data engineers.
- **Frontend**: `modules/pipelines/*` (List, Studio, Runs) — always live; empty `seed.ts`.
- **Backend**: `pipelines/` (routes, services, execution, worker, formula, validation, registry, storage, models).
- **API surface**: `/api/v1/pipelines` CRUD + validate/publish/versions/runs + `/api/v1/pipeline-artifacts/download`. (See inventory.)
- **DB entities**: `pipelines`, `pipeline_nodes`, `pipeline_edges`, `pipeline_versions`, plus run tables (below).
- **Status**: **Production-ready** — graph validation, immutable versions, formula DSL, 13+ transform node types.
- **Test coverage**: `tests/unit/test_pipelines.py`, `test_pipeline_*`; integration `test_pipeline_*`; frontend pipeline specs; e2e pipeline source.
- **Production-readiness**: Ready.

## 11. Pipeline Execution

- **Business purpose**: Durable async execution of published pipeline versions.
- **Persona**: Data engineers / operators.
- **Frontend**: `PipelineRunsView.vue` (list/cancel/retry, artifacts, logs).
- **Backend**: `pipelines/worker.py`, `pipelines/execution.py`.
- **API surface**: `POST /{id}/runs`, `GET /{id}/runs`, run detail/cancel/retry, artifacts + signed download URL.
- **DB entities**: `pipeline_runs`, `pipeline_run_attempts`, `pipeline_node_runs`, `pipeline_run_logs`, `pipeline_artifacts`, `pipeline_outbox_events`.
- **Dependencies**: dedicated `pipeline-worker`; PostgreSQL connections; Redis events.
- **Status**: **Production-ready** — leases/heartbeats, attempts, node-level tracking, retention, signed artifacts.
- **Limitations**: Source reads assume PostgreSQL.
- **Test coverage**: pipeline integration tests.
- **Production-readiness**: Ready.

## 12. Dataset Studio

- **Business purpose**: Register/discover datasets, preview/profile data, manage fields, ingest CSV.
- **Persona**: Data engineers / analysts.
- **Frontend**: `modules/datasets/*` (List, Detail, DataQuality, DataLineage). Core data is live; the Detail view's access/versions/activity tabs use **mock** arrays.
- **Backend**: `datasets/` (routes, services, repositories, discovery, preview, quality, ingestion, models).
- **API surface**: `/api/v1/datasets` CRUD + discover, ingest-csv/file, fields, preview, profile, quality (rules/evaluations/results), lineage. (See inventory.)
- **DB entities**: `datasets`, `dataset_fields`, `dataset_quality_rules`, `dataset_quality_results`, `dataset_quality_evaluations`, `dataset_lineage_edges`.
- **Dependencies**: connections; jobs (`dataset.quality` handler).
- **Status**: **Implemented with minor gaps** — real discovery/preview/profile/ingest/lineage/quality, but PostgreSQL-centric and Detail UI has mock tabs.
- **Test coverage**: `tests/unit/test_dataset_quality.py`, `test_b5_contracts.py`; integration `test_b5_database.py`.
- **Production-readiness**: Ready for PostgreSQL sources; broaden connectors + replace mock UI tabs.

## 13. Semantic Models and Metrics

- **Business purpose**: Define semantic models, dimensions, measures, metrics, KPIs, a glossary, and run bounded read-only queries.
- **Persona**: Analytics engineers.
- **Frontend**: `modules/semantic/*` (List, Builder, Glossary, Metrics) — live.
- **Backend**: `semantic/` (routes: models/glossary/query; services; query compiler; models).
- **API surface**: `/api/v1/semantic-models/*`, `/api/v1/glossary/*`, `POST /api/v1/semantic-query`.
- **DB entities**: `semantic_models`, `semantic_model_versions`, `semantic_model_datasets`, `semantic_joins`, `semantic_dimensions`, `semantic_measures`, `semantic_metrics`, `semantic_kpis`, `glossary_domains`, `glossary_terms`, `glossary_term_relationships`, `glossary_assignments`.
- **Status**: **Implemented with minor gaps** — full lifecycle + working PostgreSQL query compiler; query execution rejects non-PostgreSQL connectors (`QUERY_CONNECTOR_UNSUPPORTED`).
- **Test coverage**: `tests/unit/test_b5_contracts.py`; integration `test_b5_database.py`.
- **Production-readiness**: Ready for PostgreSQL; multi-connector query is a gap.

## 14. Dashboard Studio

- **Business purpose**: Build dashboards (pages, widgets, filters), version, publish, and view.
- **Persona**: Analysts / editors.
- **Frontend**: `modules/dashboards/*` (List, Studio, Viewer, Templates, Deliveries). Core is live; `DashboardTemplatesView` uses a hardcoded template array.
- **Backend**: `dashboards/` (routes, services ~989 lines, query, models).
- **API surface**: `/api/v1/dashboards` CRUD + editor, publish, versions/restore, viewer, shares, snapshots, widget data. (See inventory.)
- **DB entities**: `dashboards`, `dashboard_pages`, `dashboard_widgets`, `dashboard_filters`, `dashboard_versions`, `dashboard_shares`, `dashboard_snapshots`.
- **Dependencies**: semantic query engine; optional Redis cache.
- **Status**: **Production-ready** — optimistic locking (`row_version`), real widget queries, versioning.
- **Test coverage**: `tests/unit/test_dashboards.py`; frontend dashboard specs; e2e studios.
- **Production-readiness**: Ready (template gallery is static UI).

## 15. Dashboard Sharing

- **Business purpose**: Share dashboards with principals.
- **Persona**: Dashboard owners.
- **Frontend**: share dialog within dashboards module.
- **Backend**: `dashboards/services.py` share management (feature `dashboard_sharing`).
- **API surface**: `GET/POST/DELETE /api/v1/dashboards/{id}/shares`.
- **DB entities**: `dashboard_shares`.
- **Status**: **Implemented with minor gaps** — principal validation exists; no public/anonymous link tokens observed.
- **Test coverage**: covered within dashboard tests.
- **Production-readiness**: Ready for internal sharing.

## 16. Dashboard Exports

- **Business purpose**: Async export of dashboards to PDF/PNG/JSON/CSV with signed downloads.
- **Persona**: Analysts.
- **Frontend**: export actions within dashboards; download handling in apiClient.
- **Backend**: `dashboard_delivery/` (routes, services, worker, rendering, storage).
- **API surface**: `/dashboards/{id}/exports`, `/dashboard-exports/{id}` (+ cancel/retry/download-token/download).
- **DB entities**: `dashboard_exports`.
- **Dependencies**: job worker (`dashboard.export`), artifact volume, signing key.
- **Status**: **Production-ready** — real renderers, retry/cancel, retention, HMAC downloads.
- **Test coverage**: `tests/unit/test_dashboard_delivery.py`; integration `test_dashboard_*`.
- **Production-readiness**: Ready.

## 17. Reports

- **Business purpose**: Report builder + scheduled report deliveries.
- **Persona**: Analysts.
- **Frontend**: `modules/reports/*` (List, Builder, Deliveries). Builder is a rich block editor with mostly local state.
- **Backend**: **none** — reports endpoints are served by `catalog/routes.py` empty stubs (`/reports`, `/reports/templates`, `/reports/deliveries`, `/reports/exports` → `[]`).
- **API surface**: read-only empty catalog stubs only.
- **DB entities**: none.
- **Status**: **Prototype / Placeholder** — no persistence in live mode.
- **Test coverage**: none backend.
- **Production-readiness**: Not production-ready.

## 18. Scheduling / Email Delivery

- **Business purpose**: Schedule recurring dashboard deliveries by email.
- **Persona**: Analysts / operators.
- **Frontend**: `modules/dashboards/DashboardDeliveriesView.vue` (live delivery service); `reports/DeliveriesView.vue` (stub).
- **Backend**: `dashboard_delivery/` (schedules, runs, `scheduling.py`, `email.py`).
- **API surface**: `/dashboard-deliveries*`, `/dashboards/{id}/deliveries*` (create/update/delete/history/test/preview-email).
- **DB entities**: `dashboard_delivery_schedules`, `dashboard_delivery_runs`.
- **Dependencies**: email provider (file/SMTP).
- **Status**: **Implemented with minor gaps** — CRUD + on-demand "test delivery" + email rendering work, but **no daemon scans `next_run_at`** (no automatic recurring runner); cron is validated but not parsed.
- **Test coverage**: within dashboard delivery tests.
- **Production-readiness**: Not fully — recurring automation missing.

## 19. Files and Storage

- **Business purpose**: Upload/download/version files with malware scanning and signed downloads.
- **Persona**: All producers/consumers of files.
- **Frontend**: used by dataset ingest-file and downloads via apiClient.
- **Backend**: `files/` (routes, services, storage, scanning, validation, lifecycle, models).
- **API surface**: `/api/v1/files` upload/list/detail/versions/content/restore/download-token/download/delete.
- **DB entities**: `files`, `file_versions`, `file_uploads`, `file_download_tokens`, `file_scans`.
- **Dependencies**: ClamAV; storage provider; signing key; optional `platform.file_lifecycle` job.
- **Status**: **Production-ready**.
- **Test coverage**: `tests/unit/test_platform_jobs_files_events.py`; integration `test_platform_infrastructure.py`.
- **Production-readiness**: Ready.

## 20. Async Jobs and Worker Platform

- **Business purpose**: Durable background execution with retries, dead letters, progress, and heartbeats.
- **Persona**: Operators.
- **Frontend**: `modules/operations/*`; jobs surfaced via `platformInfrastructure` service.
- **Backend**: `jobs/` (routes, services, worker, queue, handlers, registry, retry, models).
- **API surface**: `/api/v1/jobs` list/detail/progress/logs/cancel/retry, metrics, platform-metrics, workers, dead-letters.
- **DB entities**: `jobs`, `job_payloads`, `job_attempts`, `job_progress`, `job_logs`, `job_errors`, `dead_letter_jobs`, `job_results`, `worker_heartbeats`.
- **Status**: **Production-ready** — Redis + DB `SKIP LOCKED` claim, leases, handler registry.
- **Test coverage**: `tests/unit/test_platform_jobs_files_events.py`; integration `test_platform_infrastructure.py`.
- **Production-readiness**: Ready.

## 21. Real-Time Updates / SSE

- **Business purpose**: Push job/file/export activity to the browser.
- **Persona**: All authenticated users.
- **Frontend**: `AppLayout` subscribes; apiClient SSE parser.
- **Backend**: `events/` (`routes.py`, `broker.py` — Redis Streams).
- **API surface**: `GET /api/v1/events/stream` (`events.subscribe`, resumable).
- **DB entities**: none (ephemeral Redis Streams).
- **Status**: **Production-ready**.
- **Test coverage**: `tests/unit/test_platform_jobs_files_events.py`.
- **Production-readiness**: Ready.

## 22. Audit and Activity

- **Business purpose**: Record and view platform activity and governance decisions.
- **Persona**: Org admins / auditors.
- **Frontend**: `modules/operations/AuditCenterView.vue`, `ActivityCenterView.vue`; `home/ActivityView.vue`; `auditService`.
- **Backend**: `governance/audit.py` (persistent `audit_events`); `home/routes.py` activity feed; `tenancy/audit.py` (log-only).
- **API surface**: `GET /api/v1/audit-events` (`audit.read`), `GET /api/v1/activity`.
- **DB entities**: `audit_events`.
- **Status**: **Implemented with minor gaps** — governance/domain/platform actions persisted; tenancy events are log-only; `AUDIT_*` flags not checked at write time.
- **Test coverage**: within governance/platform tests.
- **Production-readiness**: Ready for governance audit; unify tenancy audit persistence.

## 23. Notifications

- **Business purpose**: Surface recent job-based notifications.
- **Persona**: All users.
- **Frontend**: `modules/operations/NotificationsView.vue`, `shell/NotificationDrawer.vue` (unread badge hardcoded to 4 in `ui` store).
- **Backend**: `home/routes.py::notifications_router` (`GET /api/v1/notifications`) maps recent `Job` rows.
- **API surface**: `GET /api/v1/notifications`.
- **DB entities**: derived from `jobs`.
- **Status**: **Implemented with minor gaps** — real job-derived notifications; no dedicated notification store or read/unread state; badge count is static UI.
- **Production-readiness**: Basic; not a full notification system.

## 24. AI Studio

- **Business purpose**: AI assistant/chat, assistants, knowledge bases, agents, agent runs.
- **Persona**: Analysts / builders.
- **Frontend**: `modules/ai/*` (Assistant, AiStudio, Knowledge, Agents, AgentRuns).
- **Backend**: **none** — `catalog/routes.py` returns `[]` for `/ai/conversations|assistants|knowledge|agents|agent-runs`.
- **API surface**: empty catalog stubs; **live chat streaming throws** (`ai.service.ts::streamReply` raises "not implemented").
- **DB entities**: none.
- **Status**: **Partially implemented / Prototype** — rich mock UI; live mode shows empty lists and non-functional chat.
- **Production-readiness**: Not production-ready.

## 25. Automation Studio

- **Business purpose**: Author automations with runs and approvals.
- **Persona**: Ops builders.
- **Frontend**: `modules/automation/*` (List, Builder, Runs, Approvals). Builder is non-persistent (local state).
- **Backend**: **none** — no automation backend package; list/run endpoints are mock/live catalog-style with empty live responses.
- **API surface**: none real.
- **DB entities**: none.
- **Status**: **Prototype / Placeholder**.
- **Production-readiness**: Not production-ready.

## 26. Billing

- **Business purpose**: Plan/usage/billing management.
- **Persona**: Org owners / finance.
- **Frontend**: `modules/billing/BillingView.vue` — hardcoded plan card; actions are toast-only.
- **Backend**: **none** (no billing package; `plan` hardcoded `enterprise` in frontend platform store).
- **API surface**: none real.
- **DB entities**: none.
- **Status**: **Placeholder**.
- **Production-readiness**: Not production-ready.

## 27. Marketplace

- **Business purpose**: Extension/app marketplace.
- **Persona**: Admins.
- **Frontend**: `modules/marketplace/*` (Marketplace, ExtensionDetail). Install state is local overlay only.
- **Backend**: **none** — `catalog/routes.py` `/marketplace/extensions` → `[]`.
- **API surface**: empty stub.
- **DB entities**: none.
- **Status**: **Placeholder (live) / Prototype (mock)**.
- **Production-readiness**: Not production-ready.

## 28. Insights

- **Business purpose**: Automated insight cards / NLQ.
- **Persona**: Analysts.
- **Frontend**: `modules/insights/*` — mock `SEED` marked `simulated: true`; pin/save/share are client-side toasts.
- **Backend**: **none** — `/insights` → `[]`.
- **Status**: **Prototype (mock) / Placeholder (live)**.
- **Production-readiness**: Not production-ready.

## 29. Developer / API Platform

- **Business purpose**: API keys, webhooks, deliveries.
- **Persona**: Developers.
- **Frontend**: `modules/developer/DeveloperPortalView.vue` — key create via mock/live service; **webhook create is toast-only**.
- **Backend**: **none** — `/developer/*` are catalog-style with empty live responses.
- **Status**: **Partially implemented (mock) / Placeholder (live)**.
- **Production-readiness**: Not production-ready.

## 30. Explore

- **Business purpose**: Ad-hoc analysis over semantic models.
- **Persona**: Analysts.
- **Frontend**: `modules/explore/ExploreView.vue` — uses semantic model list + widget-data composable (dashboard/semantic query APIs); no dedicated explore endpoint.
- **Backend**: reuses semantic query engine.
- **Status**: **Implemented with minor gaps** — works when semantic models exist.
- **Production-readiness**: Usable; reuses semantic infrastructure.

## 31. Home / Favorites / Settings (supporting surfaces)

- **Home** (`modules/home/HomeView.vue`, `home/routes.py`): **Implemented with minor gaps** — real tenant-scoped aggregation; `pendingApprovals` always 0; health sparklines are static repeats.
- **Favorites** (`modules/home/FavoritesView.vue`): **Placeholder** — hardcoded array.
- **Settings** (`modules/settings/SettingsView.vue`): **Placeholder** — profile/appearance/security are UI-only; saves show toasts; session list uses mock timestamps.

---

## Module status summary

| # | Module | Backend | Frontend | Status |
| --- | --- | --- | --- | --- |
| 1 | Authentication & Sessions | `auth/` | `auth/`, stores | Production-ready (reset not implemented) |
| 2 | Platform Administration | `platform_admin/` | `platform/` | Production-ready |
| 3 | Users | `auth/`, `platform_admin/` | admin/settings | Implemented w/ minor gaps |
| 4 | Organizations | `tenancy/` | `admin/` | Implemented w/ minor gaps |
| 5 | Workspaces | `tenancy/` | `admin/` | Implemented w/ minor gaps |
| 6 | Memberships | `tenancy/` | `admin/MembersView` | Implemented w/ minor gaps |
| 7 | Roles & Permissions | `governance/` | `admin/`, authorization store | Implemented w/ minor gaps (resource ACL not wired) |
| 8 | Connection Studio | `connections/` | `connections/` | Production-ready |
| 9 | Secrets & Credentials | `connections/secrets` | connection detail | Production-ready |
| 10 | Pipeline Studio | `pipelines/` | `pipelines/` | Production-ready |
| 11 | Pipeline Execution | `pipelines/worker` | `PipelineRunsView` | Production-ready |
| 12 | Dataset Studio | `datasets/` | `datasets/` | Implemented w/ minor gaps |
| 13 | Semantic & Metrics | `semantic/` | `semantic/` | Implemented w/ minor gaps |
| 14 | Dashboard Studio | `dashboards/` | `dashboards/` | Production-ready |
| 15 | Dashboard Sharing | `dashboards/` | dashboards | Implemented w/ minor gaps |
| 16 | Dashboard Exports | `dashboard_delivery/` | dashboards | Production-ready |
| 17 | Reports | catalog stub | `reports/` | Prototype/Placeholder |
| 18 | Scheduling & Email Delivery | `dashboard_delivery/` | `dashboards/Deliveries` | Implemented w/ minor gaps (no auto runner) |
| 19 | Files & Storage | `files/` | shared | Production-ready |
| 20 | Async Jobs & Workers | `jobs/` | `operations/` | Production-ready |
| 21 | Real-Time / SSE | `events/` | `AppLayout` | Production-ready |
| 22 | Audit & Activity | `governance/audit`, `home/` | `operations/` | Implemented w/ minor gaps |
| 23 | Notifications | `home/notifications` | `operations/`, drawer | Implemented w/ minor gaps |
| 24 | AI Studio | catalog stub | `ai/` | Prototype/Placeholder |
| 25 | Automation Studio | none | `automation/` | Prototype/Placeholder |
| 26 | Billing | none | `billing/` | Placeholder |
| 27 | Marketplace | catalog stub | `marketplace/` | Placeholder |
| 28 | Insights | catalog stub | `insights/` | Prototype/Placeholder |
| 29 | Developer/API | catalog stub | `developer/` | Partially implemented/Placeholder |
| 30 | Explore | semantic reuse | `explore/` | Implemented w/ minor gaps |
| 31 | Home/Favorites/Settings | `home/` / none | `home/`, `settings/` | Mixed (Home minor gaps; Favorites/Settings placeholder) |
