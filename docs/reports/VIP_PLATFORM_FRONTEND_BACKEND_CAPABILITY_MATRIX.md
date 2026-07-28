# VIP Platform Frontend/Backend Capability Matrix

Audit date: 2026-07-28
Basis: source routes, services, persistence models, workers, migrations, tests, and runtime proof;
menu visibility alone is not treated as implementation.

## Status Definitions

- **Verified**: real frontend and backend behavior with current automated/runtime evidence.
- **Partial**: useful implemented behavior exists, but part of the user journey is static,
  development-only, or lacks a production integration.
- **Frontend-only**: routed UI/service uses local static or mock data and has no matching API.
- **Backend-only**: API/persistence exists without a complete product UI.
- **Read-only/mock**: demonstration or informational behavior; not a production mutation path.
- **Missing**: no material implementation.

## Master Inventory

| Module / capability | Frontend | Backend / persistence | Worker / integration | Security / RBAC | Evidence | Status | Production status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Login, refresh, logout, password reset | Live UI | Auth API, sessions, lockout | Redis/session cleanup | CSRF, replay and revocation | Unit, integration, E2E | Verified | Ready with production cookie/TLS config |
| Username and optional email identity | Live UI | User model/API/migration 0013 | — | Unique normalized identity | Static, integration, E2E | Verified | Ready |
| Organizations | Live CRUD/switcher | Tenant API/DB | Audit/events | Role scoped, last-owner rules | Integration/E2E | Verified | Ready |
| Workspaces | Live CRUD/switcher | Workspace API/DB | Audit/events | Tenant scoped | Integration/E2E | Verified | Ready |
| Memberships, invitations, roles | Live administration | Governance/tenancy APIs | Invitation lifecycle | Admin/Editor/Viewer/Restricted | Integration/E2E | Verified | Ready; production mail provider required |
| Platform administration | Live console | Platform-admin APIs | Jobs where applicable | Separate super-admin checks | Unit/integration/E2E | Verified | Ready for controlled operators |
| Home/activity/favorites | Live mixed views | Home, notifications, audit APIs | SSE/polling | Tenant scoped | Unit/E2E | Partial | Internal/UAT |
| Notifications | Live list/state | Notifications API | SSE | Tenant scoped | Integration/E2E | Verified | Ready |
| Audit trail | Live viewer | Append/query API/DB | Service event writes | Tenant/platform scopes | Integration/E2E | Verified | Ready |
| Connections catalog | Live catalog | Catalog registry/API | — | Entitlement/governance | Unit/E2E | Verified | Ready |
| Connection CRUD/test/rotation | Live UI | Encrypted credential records | Provider testers/jobs | AES-GCM, write-only secrets, tenant scope | Unit/integration/E2E | Verified | Ready for supported providers |
| Dataset catalog | Live list/detail | Dataset API/DB | Discovery/ingestion | Tenant scope | Integration/E2E | Verified | Ready |
| File upload/version/download | Live upload/download | File/version API/DB/storage | Async scan path | Signed one-use token, AV evidence | Real AV + tests | Verified | Ready with durable object storage |
| Malware scanning | Status surfaced | Fail-closed ClamAV adapter/evidence | ClamAV | Clean/EICAR/outage/replay | Real runtime + 18 tests | Verified | Ready |
| Dataset preview/profile/quality | Live views | Preview/profile/quality services | Source access | Scoped credentials | Unit/integration/E2E | Verified | Ready for supported source types |
| Data lineage | Routed visualization | Dataset/pipeline relationships | — | Tenant scoped | E2E/contracts | Partial | Internal/UAT |
| Semantic models | Live list/detail/editor paths | Semantic model API/DB | Query compiler | Tenant scoped, read-only SQL | Unit/integration/E2E | Verified | Ready |
| Metrics/glossary | Live views | Metrics/glossary APIs | — | Tenant scoped | Unit/E2E | Verified | Ready |
| Formula editor/functions | Live editor | Validation/execution functions | Pipeline engine | Restricted expression grammar | Unit/E2E | Verified | Ready |
| Pipeline catalog/studio/versioning | Live UI | Pipeline/version API/DB | Worker | Tenant/RBAC scoped | Integration/E2E | Verified | Ready |
| Pipeline publish/execute | Live UI | Run API/state | Lease-based worker | Published version and scoped artifacts | Full reconciliation | Verified | Ready |
| Row validation/rejected output | Live node configuration | Registry, validation, artifact metadata | Worker execution | Safe reason records | 15-row reconciliation | Verified | Ready |
| Pipeline retry/cancel/recovery | Live status/actions | Attempts/leases/audit | Worker retry/recovery | No duplicate artifact | Runtime resilience + tests | Verified | Ready |
| Dashboard catalog/studio/viewer | Live UI | Dashboard/version API/DB | Query execution | Tenant/RBAC | Integration/E2E | Verified | Ready |
| Published dashboard filters | Live controls | Mapped semantic query filters | — | Validated/scoped | Reconciled runtime | Verified | Ready |
| PDF/PNG/JSON/CSV export | Live actions/history | Export API/artifact store | Dashboard worker | Single-use signed download | Four real exports | Verified | Ready with durable storage |
| Scheduled dashboard delivery | Live schedule/history | Schedule/delivery API/DB | Dashboard worker | Recipient/scope validation | All cadences + sent delivery | Verified | Pilot-ready; production SMTP required |
| Jobs | Live operational surfaces | Job API/state | Workers | Secret-safe payload validation | Unit/integration/E2E | Verified | Ready |
| Events/SSE | Live client/fallback | Event API | SSE, replay, polling fallback | Authenticated tenant stream | Unit/E2E/metrics | Verified | Ready; size for live topology |
| Health/readiness/version | Operational | Public operational endpoints | DB/Redis checks | Minimal disclosure | Runtime failure/recovery | Verified | Ready |
| Prometheus metrics | No general-user UI | Protected endpoint | Aggregate worker/dependency data | Bearer token; no tenant labels | Runtime/unit | Backend-only | Ready with monitoring stack |
| Insights | Routed UI | No dedicated production API | — | Route guards | Source inspection | Frontend-only | Internal demonstration |
| Explore | Routed UI | Uses partial semantic/data services | — | Route guards | Source inspection | Partial | Internal/UAT |
| Reports/report builder | Routed UI | Dashboard delivery is real; report domain absent | Mock/local service | Route guards | Source inspection | Frontend-only | Not production ready |
| AI assistant/studio/knowledge/agents | Routed UI | No AI domain API | Mock/local data | Route guards only | Source inspection | Read-only/mock | Not implemented |
| Automation builder/runs/approvals | Routed UI | No automation domain API | Static/local simulated runs | Route guards only | Source inspection | Read-only/mock | Not implemented |
| Marketplace | Routed catalog/detail | No marketplace API | Static data | Route guards | Source inspection | Read-only/mock | Not production ready |
| Billing/usage | Routed informational UI | No billing provider/API | — | Route guards | Source inspection | Read-only/mock | Not production ready |
| Developer portal | Routed UI | Partial platform metadata only | — | Route guards | Source inspection | Frontend-only | Internal only |
| Settings | Routed UI | Identity/tenant settings partly live | — | Route guards | Source inspection/E2E | Partial | Internal/UAT |
| Feature flags/entitlements | Admin UI | Governance/entitlement responses | — | Route enforcement | Integration/E2E | Partial | Controlled use |

## Table A — Fully Frontend and Backend

Identity/authentication; organizations; workspaces; membership/invitations/RBAC; platform admin;
connections/secrets; datasets; file ingestion and malware scanning; semantic models; formulas;
pipelines; dashboards; exports; scheduled delivery; notifications; audit; jobs; events.

## Table B — Frontend-Only

Insights, report-builder domain, developer portal portions, and several settings surfaces.

## Table C — Backend-Only

Prometheus metrics, some operational worker controls, low-level artifact/evidence endpoints, and
administrative maintenance operations.

## Table D — Read-Only, Mock, or Static

AI surfaces, Automation surfaces, Marketplace, Billing, and some Usage/Reports sample content.

## Table E — Partial

Home/activity/favorites, lineage visualization, Explore, settings, feature flags, and production
email delivery. These are useful in UAT but must not be represented as complete standalone domains.

## Table F — Fully Production Ready in B0–B8 Code Scope

Core identity/tenant/RBAC, encrypted connections, supported dataset/file flows, semantic query,
deterministic pipelines, dashboards/exports, audit/events/jobs, operational health, and real AV.
Deployment still requires the infrastructure controls in the production-readiness report.

## Table G — Internal Use Only

Development-file delivery, demonstration seeds, partial Home/Explore/Lineage/Settings/Developer
views, and any provider using a local adapter.

## Table H — Not Production Ready

| Feature | Exact reason |
| --- | --- |
| AI suite | No backend model/provider/orchestration domain; static/mock UI only |
| Automation suite | No backend trigger/action/runtime domain; simulated local data |
| Report builder | No report-domain persistence/execution API |
| Marketplace | Static catalog; no install/provision lifecycle |
| Billing | No billing provider, ledger, invoice, or webhook implementation |
| Public live deployment | Environment controls and managed services are not provisioned by this local certification |

## Security and Production Summary

| Area | Result |
| --- | --- |
| Tenant isolation | Verified |
| RBAC | Verified for implemented roles/actions |
| Secret handling | Verified; encrypted/write-only/redacted |
| File security | Verified with real ClamAV |
| Signed artifacts | Verified one-use, replay and cross-tenant denial |
| Migrations | Verified single-headed zero-to-head |
| Dependency security | npm/pip clean |
| Container security | Application images zero critical/high; effective derivative changes zero critical/high |
| Local readiness | Green |
| Internal UAT | Green |
| Pilot | Conditional on environment/provider setup |
| Public production | Not claimed by local certification |

No Phase B9, AI, or Automation code was added during certification.
