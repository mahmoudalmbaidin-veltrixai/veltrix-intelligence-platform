# VIP — API Inventory (verified)

> Endpoints were verified against route handlers and service logic, not inferred from names.
> Base prefix is `/api/v1` for all domain routers; `/auth/*` is unversioned; operational endpoints
> are at the root. All authenticated endpoints require a valid access-session cookie. Mutating
> endpoints additionally require CSRF (double-submit cookie/header + origin allowlist). Tenant-scoped
> endpoints require `X-Organization-ID` (and `X-Workspace-ID` for workspace-scoped resources).

**Scope legend**: `pub` = public/no session · `sess` = session only · `org` = organization-scoped ·
`ws` = workspace-scoped · `plat` = platform super-admin.

**Impl legend**: FULL = fully implemented · GAP = implemented with minor gaps · STUB = placeholder
(returns empty / not persisted).

---

## Operational (root)

| Method | Path | Purpose | Auth | Impl |
| --- | --- | --- | --- | --- |
| GET | `/health` | Liveness | pub | FULL |
| GET | `/ready` | Readiness (DB/Redis) | pub | FULL |
| GET | `/api/v1/version` | Build/version info | pub | FULL |

## Authentication (`/auth`)

| Method | Path | Purpose | Auth | Perm | Impl |
| --- | --- | --- | --- | --- | --- |
| POST | `/auth/login` | Validate credentials, create session, set cookies | pub (IP rate-limited) | — | FULL |
| GET | `/auth/me` | Current user + access expiry | sess | — | FULL |
| POST | `/auth/refresh` | Rotate session + cookies (reuse detection) | refresh cookie + CSRF | — | FULL |
| POST | `/auth/logout` | Revoke session, clear cookies (idempotent) | CSRF if session | — | FULL |

> Not present: `POST /auth/forgot-password`, `POST /auth/reset-password` (self-service reset is not implemented).

## Tenancy (`/api/v1`)

| Method | Path | Purpose | Scope | Perm | Impl |
| --- | --- | --- | --- | --- | --- |
| GET | `/organizations` | List user's orgs | sess | — | FULL |
| POST | `/organizations` | Create org + default workspace | sess + CSRF | — | FULL |
| GET | `/organizations/{organization_id}` | Org detail | org | `organization.read` | FULL |
| PATCH | `/organizations/{organization_id}` | Update org | org + CSRF | `organization.update` | FULL |
| GET | `/organizations/{org}/workspaces` | List workspaces | org | `workspace.read` | FULL |
| POST | `/organizations/{org}/workspaces` | Create workspace | org + CSRF | `workspace.create` + quota | FULL |
| GET | `/organizations/{org}/workspaces/{ws}` | Workspace detail | ws | `workspace.read` | FULL |
| PATCH | `/organizations/{org}/workspaces/{ws}` | Update workspace | ws + CSRF | `workspace.update` | FULL |
| GET | `/organizations/{org}/members` | List org members | org | `organization.members.read` | FULL |
| PATCH | `/organizations/{org}/members/{id}` | Update member role/status | org + CSRF | `organization.members.update` | FULL |
| DELETE | `/organizations/{org}/members/{id}` | Remove member | org + CSRF | `organization.members.remove` | FULL |
| GET | `/organizations/{org}/workspaces/{ws}/members` | List ws members | ws | `workspace.members.read` | FULL |
| POST | `/organizations/{org}/workspaces/{ws}/members` | Add/update ws member | ws + CSRF | `workspace.members.manage` | FULL |
| DELETE | `/organizations/{org}/workspaces/{ws}/members/{id}` | Remove ws member | ws + CSRF | `workspace.members.manage` | FULL |
| POST | `/organizations/{org}/invitations` | Create invitation | org + CSRF | `organization.members.invite` | GAP (no prod email) |
| GET | `/organizations/{org}/invitations` | List invitations | org | `organization.members.read` | FULL |
| DELETE | `/organizations/{org}/invitations/{id}` | Revoke invitation | org + CSRF | `organization.members.invite` | FULL |
| POST | `/invitations/accept` | Accept invitation token | sess + CSRF | — | FULL |
| GET | `/tenant-context` | Resolve tenant context | org/ws | — | FULL |

## Governance (`/api/v1`)

| Method | Path | Purpose | Scope | Perm | Impl |
| --- | --- | --- | --- | --- | --- |
| GET | `/authorization/context` | Resolved permissions/flags/entitlements/quotas | org/ws | tenant context | FULL |
| GET | `/roles` | List system roles + permission keys | org | `governance.read` | FULL |
| GET | `/permissions` | Permission catalog | org | `governance.read` | FULL |
| GET | `/organizations/{organization_id}/entitlements` | Org entitlements | org | `governance.read` | FULL |
| GET | `/organizations/{organization_id}/feature-flags` | Effective flags | org | `governance.read` | FULL |
| GET | `/organizations/{organization_id}/quotas` | Quota snapshots | org | `governance.read` | FULL |
| GET | `/audit-events` | Paginated audit log | org | `audit.read` | FULL |

> `resource_access_entries` has no HTTP surface — the evaluator is not wired to routes.

## Platform Administration (`/api/v1/platform`)

All require session + `is_platform_admin` (404 otherwise); mutations require CSRF. Scope = `plat`.

| Method | Path | Purpose | Impl |
| --- | --- | --- | --- |
| GET | `/overview` | Platform-wide counts | FULL |
| GET | `/organizations` | List all orgs (paged/search) | FULL |
| POST | `/organizations` | Create org | FULL |
| GET | `/organizations/{organization_id}` | Org detail | FULL |
| POST | `/organizations/{organization_id}/suspend` | Suspend org | FULL |
| POST | `/organizations/{organization_id}/activate` | Activate org | FULL |
| GET | `/users` | List all users | FULL |
| POST | `/users` | Create user | FULL |
| PATCH | `/users/{user_id}` | Update user profile/flags | FULL |
| POST | `/users/{user_id}/suspend` | Suspend user | FULL |
| POST | `/users/{user_id}/activate` | Activate user | FULL |
| GET | `/users/{user_id}/access-summary` | Org/workspace assignments | FULL |
| POST | `/users/{user_id}/reset-password` | Admin password reset | FULL |
| POST | `/organizations/{org}/members` | Add org member | FULL |
| DELETE | `/organizations/{org}/members/by-user/{user_id}` | Remove org access | FULL |
| POST | `/organizations/{org}/workspaces` | Create workspace | FULL |
| POST | `/organizations/{org}/workspaces/{ws}/members` | Add ws member | FULL |
| DELETE | `/organizations/{org}/workspaces/{ws}/members/by-user/{user_id}` | Remove ws access | FULL |
| POST | `/organizations/{org}/workspaces/{ws}/suspend` | Suspend workspace | FULL |
| POST | `/organizations/{org}/workspaces/{ws}/activate` | Activate workspace | FULL |

## Home / Notifications / Activity (`/api/v1`)

| Method | Path | Purpose | Scope | Perm | Impl |
| --- | --- | --- | --- | --- | --- |
| GET | `/home/summary` | Aggregated home data | ws | `workspace.read` | GAP (static sparklines, pendingApprovals=0) |
| GET | `/notifications` | Job-derived notifications | ws | `workspace.read` | GAP |
| GET | `/activity` | Audit-event activity feed | ws | `workspace.read` | FULL |

## Platform catalogs (`/api/v1`)

| Method | Path | Purpose | Scope | Perm | Impl |
| --- | --- | --- | --- | --- | --- |
| GET | `/usage` | Real quota consumption | ws | `workspace.read` | FULL |
| GET | `/ai/conversations` `/ai/assistants` `/ai/knowledge` `/ai/agents` `/ai/agent-runs` | Empty AI catalogs | ws | `workspace.read` | STUB (`[]`) |
| GET | `/insights` | Empty insights | ws | `workspace.read` | STUB (`[]`) |
| GET | `/marketplace/extensions` | Empty marketplace | ws | `workspace.read` | STUB (`[]`) |
| GET | `/reports` `/reports/templates` `/reports/deliveries` `/reports/exports` | Empty report catalogs | ws | `workspace.read` | STUB (`[]`) |

## Connections (`/api/v1/connections`)

| Method | Path | Purpose | Scope | Perm | Impl |
| --- | --- | --- | --- | --- | --- |
| GET | `/types` | Connection type catalog | ws | `connection.types.read` (feat `connection_studio`) | FULL |
| GET | `` | List connections | ws | `connection.read` | FULL |
| POST | `` | Create + encrypt credentials | ws + CSRF | `connection.create` + quota | FULL |
| GET | `/{id}` | Detail (no secrets) | ws | `connection.read` | FULL |
| PATCH | `/{id}` | Update metadata/config | ws + CSRF | `connection.update` | FULL |
| POST | `/{id}/archive` | Archive | ws + CSRF | `connection.archive` | FULL |
| DELETE | `/{id}` | Archive (delete audit) | ws + CSRF | `connection.delete` | FULL |
| PUT | `/{id}/credentials` | Replace credentials | ws + CSRF | `connection.credentials.update` | FULL |
| POST | `/{id}/credentials/rotate` | Rotate credentials | ws + CSRF | `connection.credentials.rotate` | FULL |
| POST | `/{id}/test` | Live connectivity test | ws + CSRF | `connection.test` | FULL |

## Datasets (`/api/v1/datasets`)

| Method | Path | Purpose | Scope | Perm | Impl |
| --- | --- | --- | --- | --- | --- |
| GET | `` | List datasets | ws | `dataset.read` (feat `dataset_studio`) | FULL |
| POST | `` | Create dataset | ws + CSRF | `dataset.create` + quota | FULL |
| POST | `/discover` | Metadata discovery | ws + CSRF | `dataset.discover` | FULL (PostgreSQL) |
| POST | `/ingest-csv` | CSV → table + register | ws + CSRF | `dataset.create` | FULL (PostgreSQL) |
| POST | `/ingest-file` | Uploaded-file ingest | ws + CSRF | `dataset.create` | FULL |
| GET | `/{id}` | Dataset detail | ws | `dataset.read` | FULL |
| PATCH | `/{id}` | Update metadata | ws + CSRF | `dataset.update` | FULL |
| POST | `/{id}/archive` / DELETE `/{id}` | Archive | ws + CSRF | `dataset.archive` / `dataset.delete` | FULL |
| GET | `/{id}/fields` | List fields | ws | `dataset.fields.read` | FULL |
| GET | `/{id}/preview` | Live paginated preview | ws | `dataset.read` | FULL (PostgreSQL) |
| GET | `/{id}/profile` | Column profiling | ws | `dataset.read` | FULL (PostgreSQL) |
| PATCH | `/{id}/fields/{field_id}` | Update field metadata | ws + CSRF | `dataset.fields.update` | FULL |
| GET | `/{id}/quality` | Quality summary | ws | `dataset.quality.read` (feat `data_quality`) | FULL |
| POST | `/{id}/quality-evaluations` | Queue async quality job (202) | ws + CSRF | `dataset.quality.manage` | FULL |
| GET | `/{id}/quality-evaluations` | List evaluations | ws | `dataset.quality.read` | FULL |
| GET/POST/PATCH/DELETE | `/{id}/quality-rules[...]` | CRUD quality rules | ws (+CSRF write) | read/`dataset.quality.manage` | FULL |
| GET | `/{id}/quality-results` | Rule results | ws | `dataset.quality.read` | FULL |
| GET/POST/DELETE | `/{id}/lineage[...]` | Lineage graph CRUD | ws (+CSRF write) | `dataset.lineage.read`/`.manage` (feat `data_lineage`) | FULL |

## Dashboards (`/api/v1/dashboards`)

| Method | Path | Purpose | Scope | Perm | Impl |
| --- | --- | --- | --- | --- | --- |
| GET | `` | List dashboards | ws | `dashboard.read` (ent `dashboard_studio`) | FULL |
| POST | `` | Create dashboard | ws + CSRF | `dashboard.create` + quota | FULL |
| GET | `/{id}` | Detail | ws | `dashboard.read` | FULL |
| GET | `/{id}/editor` | Editor state | ws | capability `dashboard_studio` | FULL |
| PUT | `/{id}/editor` | Save editor (optimistic lock) | ws + CSRF | capability | FULL |
| POST | `/{id}/publish` | Publish immutable version | ws + CSRF | `dashboard.publish` (feat `dashboard_publishing`) | FULL |
| POST | `/{id}/archive` / DELETE `/{id}` | Archive | ws + CSRF | `dashboard.archive`/`.delete` | FULL |
| GET | `/{id}/viewer` | Published viewer payload | ws | capability | FULL |
| GET | `/{id}/versions` | Version history | ws | `dashboard.versions.read` | FULL |
| POST | `/{id}/versions/{version_id}/restore` | Restore version | ws + CSRF | `dashboard.versions.restore` | FULL |
| GET/POST/DELETE | `/{id}/shares[...]` | Share management | ws | `dashboard.share` (feat `dashboard_sharing`) | GAP |
| GET/POST | `/{id}/snapshots[...]` | Data snapshots | ws (+CSRF/quota create) | feat `dashboard_snapshots` | FULL |
| POST | `/{id}/widgets/{widget_id}/data` | Execute widget query | ws + CSRF | capability | FULL |

## Dashboard exports & delivery (`/api/v1`)

| Method | Path | Purpose | Scope | Perm | Impl |
| --- | --- | --- | --- | --- | --- |
| POST | `/dashboards/{id}/exports` | Queue export (202) | ws | `dashboard.export` (feat `dashboard_exports`) + quota | FULL |
| GET | `/dashboards/{id}/exports` | List exports | ws | `dashboard.export.read` | FULL |
| GET | `/dashboard-exports/{export_id}` | Export status | ws | `dashboard.export.read` | FULL |
| POST | `/dashboard-exports/{export_id}/cancel` | Cancel export | ws + CSRF | `dashboard.export.cancel` | FULL |
| POST | `/dashboard-exports/{export_id}/retry` | Retry export | ws + CSRF | `dashboard.export` | FULL |
| POST | `/dashboard-exports/{export_id}/download-token` | HMAC download token | ws + CSRF | `dashboard.export.download` | FULL |
| GET | `/dashboard-exports/{export_id}/download` | Download artifact | ws | `dashboard.export.download` + token | FULL |
| GET | `/dashboard-deliveries` | All schedules | ws | `dashboard.delivery.read` (feat `dashboard_delivery`) | FULL |
| GET | `/dashboards/{id}/deliveries` | Dashboard schedules | ws | `dashboard.delivery.read` | FULL |
| POST | `/dashboards/{id}/deliveries` | Create schedule | ws | `dashboard.delivery.manage` + quota | GAP (no auto runner) |
| PUT | `/dashboard-deliveries/{schedule_id}` | Update schedule | ws | `dashboard.delivery.manage` | FULL |
| DELETE | `/dashboard-deliveries/{schedule_id}` | Delete/disable schedule | ws | `dashboard.delivery.manage` | FULL |
| GET | `/dashboard-deliveries/{schedule_id}/history` | Delivery run history | ws | `dashboard.delivery.read` | FULL |
| POST | `/dashboard-deliveries/{schedule_id}/test` | Test delivery (202) | ws | `dashboard.delivery.send` | FULL |
| POST | `/dashboards/{id}/deliveries/preview-email` | Email HTML preview | ws | `dashboard.delivery.manage` | FULL |

## Pipelines (`/api/v1/pipelines` + `/api/v1/pipeline-artifacts`)

| Method | Path | Purpose | Scope | Perm | Impl |
| --- | --- | --- | --- | --- | --- |
| GET | `/formula-language` | Formula DSL catalog | ws | `pipeline.read` (feat `pipeline_studio`) | FULL |
| POST | `/formula-language/validate` | Validate expression | ws + CSRF | `pipeline.read` | FULL |
| GET | `` | List pipelines | ws | `pipeline.read` | FULL |
| POST | `` | Create pipeline | ws | `pipeline.create` + quota | FULL |
| GET/PUT/DELETE | `/{id}` | Show/save/archive | ws | `pipeline.read`/`.update`/`.delete` | FULL |
| POST | `/{id}/validate` | Graph validation | ws | `pipeline.update` | FULL |
| POST | `/{id}/publish` | Publish version | ws | `pipeline.publish` | FULL |
| GET | `/{id}/versions` | Version list | ws | `pipeline.versions.read` | FULL |
| POST | `/{id}/versions/{version_id}/restore` | Restore | ws | `pipeline.versions.restore` | FULL |
| POST | `/{id}/runs` | Queue run (202) | ws | `pipeline.execute` + quota | FULL |
| GET | `/{id}/runs` | List runs | ws | `pipeline.runs.read` | FULL |
| GET | `/{id}/runs/{run_id}` | Run detail + logs | ws | `pipeline.runs.read` | FULL |
| POST | `/{id}/runs/{run_id}/cancel` | Cancel run | ws | `pipeline.runs.cancel` | FULL |
| POST | `/{id}/runs/{run_id}/retry` | Retry run | ws | `pipeline.runs.retry` + quota | FULL |
| GET | `/{id}/runs/{run_id}/artifacts` | List artifacts | ws | `pipeline.runs.read` | FULL |
| POST | `/{id}/runs/{run_id}/artifacts/{artifact_id}/download-url` | Signed URL | ws | `pipeline.runs.read` | FULL |
| GET | `/pipeline-artifacts/download?token=...` | Stream artifact | ws | `pipeline.runs.read` + HMAC token | FULL |

## Semantic (`/api/v1/semantic-models`, `/glossary`, `/semantic-query`)

| Method | Path | Purpose | Scope | Perm | Impl |
| --- | --- | --- | --- | --- | --- |
| GET/POST | `/semantic-models` | List/create models | ws | `semantic_model.read`/`.create` + quota | FULL |
| GET/PATCH | `/semantic-models/{id}` | Detail/update | ws | read/update | FULL |
| GET | `/semantic-models/{id}/versions` | Version history | ws | read | FULL |
| POST | `/semantic-models/{id}/validate` | Validate model | ws | update | FULL |
| POST | `/semantic-models/{id}/publish` | Publish | ws | publish | FULL |
| POST | `/semantic-models/{id}/archive` | Archive | ws | archive | FULL |
| CRUD | `/semantic-models/{id}/dimensions[...]` | Dimensions | ws | read / `semantic_dimension.manage` | FULL |
| CRUD | `/semantic-models/{id}/measures[...]` | Measures | ws | read / `semantic_measure.manage` | FULL |
| CRUD | `/semantic-models/{id}/metrics[...]` | Metrics | ws | read / `semantic_metric.manage` + quota | FULL |
| CRUD | `/semantic-models/{id}/kpis[...]` | KPIs | ws | read / `semantic_kpi.manage` | FULL |
| GET/POST/PATCH | `/glossary/domains[...]` | Domain CRUD | ws | `glossary.read/create/update` (feat `business_glossary`) | FULL |
| GET/POST/PATCH | `/glossary/terms[...]` | Term CRUD | ws | glossary perms | FULL |
| POST | `/glossary/terms/{id}/approve` `/deprecate` | Status transitions | ws | `glossary.approve`/`.deprecate` | FULL |
| POST/DELETE | `/glossary/terms/{id}/relationships[...]` | Term relationships | ws | `glossary.update` | FULL |
| POST/DELETE | `/glossary/terms/{id}/assignments[...]` | Resource assignments | ws | `glossary.assign` | FULL |
| POST | `/semantic-query` | Read-only analytical query | ws | `semantic.query` + quota (feat `semantic_query`) | GAP (PostgreSQL only) |

## Jobs (`/api/v1/jobs`)

| Method | Path | Purpose | Scope | Perm | Impl |
| --- | --- | --- | --- | --- | --- |
| GET | `` | List tenant jobs | ws | `job.read` | FULL |
| GET | `/metrics` | Job count metrics | ws | `job.read` | FULL |
| GET | `/platform-metrics` | Queue/worker/upload metrics | ws | `job.manage` | FULL |
| GET | `/workers` | Worker heartbeats | ws | `job.manage` | FULL |
| GET | `/dead-letters` | Dead letter queue | ws | `job.dead_letter` | FULL |
| POST | `/dead-letters/{id}/discard` | Discard dead letter | ws + CSRF | `job.dead_letter` | FULL |
| GET | `/{job_id}` | Job detail | ws | `job.read` | FULL |
| GET | `/{job_id}/progress` | Progress | ws | `job.read` | FULL |
| GET | `/{job_id}/logs` | Job logs | ws | `job.read` | FULL |
| POST | `/{job_id}/cancel` | Cancel | ws + CSRF | `job.cancel` | FULL |
| POST | `/{job_id}/retry` | Retry via Redis queue | ws + CSRF | `job.retry` | FULL |

## Files (`/api/v1/files`)

| Method | Path | Purpose | Scope | Perm | Impl |
| --- | --- | --- | --- | --- | --- |
| POST | `` | Streaming upload | ws + CSRF | `file.upload` (rate-limited) | FULL |
| GET | `` | List files | ws | `file.download` | FULL |
| GET | `/{id}` | File metadata | ws | `file.download` | FULL |
| GET | `/{id}/versions` | Version history | ws | `file.download` | FULL |
| PUT | `/{id}/content` | Replace content | ws + CSRF | `file.manage` | FULL |
| POST | `/{id}/versions/{n}/restore` | Restore version | ws | `file.manage` | FULL |
| POST | `/{id}/download` | Create download token | ws + CSRF | `file.download` | FULL |
| GET | `/download/{token}` | Stream content | ws | `file.download` + token | FULL |
| DELETE | `/{id}` | Soft delete | ws + CSRF | `file.delete` | FULL |

## Events (`/api/v1/events`)

| Method | Path | Purpose | Scope | Perm | Impl |
| --- | --- | --- | --- | --- | --- |
| GET | `/stream` | Resumable SSE (Redis Streams) | ws | `events.subscribe` | FULL |

---

## Notes on verification

- Endpoints marked STUB were confirmed by reading `catalog/routes.py` (a single handler returns
  `[]` for AI, insights, marketplace, and reports catalog paths; `/usage` returns real quota data).
- Delivery schedule creation is marked GAP because no worker/daemon scans schedules for due runs —
  only `POST .../test` triggers an actual delivery. Verified in `dashboard_delivery/worker.py` and
  `scheduling.py`.
- Semantic query and dataset analytics are marked GAP for connectors other than PostgreSQL — the
  compiler raises `QUERY_CONNECTOR_UNSUPPORTED` for non-PostgreSQL connections.
- `resource_access_entries` has an ORM model + migration + unit tests but **no HTTP endpoint** and
  is not referenced by any route dependency (verified by grep).
- Modules `automation`, `billing`, and `developer` have **no backend package**; their frontend
  screens call mock/live catalog-style services that resolve to empty results in live mode.
