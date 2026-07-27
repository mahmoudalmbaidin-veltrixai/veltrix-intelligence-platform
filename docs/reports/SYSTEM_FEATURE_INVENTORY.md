# VIP — System Feature Inventory (Backend + Frontend)

Legend: ✅ done · ⚠️ partial · ❌ not built (mock/demo). **Prod-ready** = wired front↔back,
enforced server-side, and verified this session.

## ✅ Live & production-ready (real backend, verified)

| Feature | FE | BE | Prod-ready | What it does |
| --- | :--: | :--: | :--: | --- |
| Authentication & sessions | ✅ | ✅ | ✅ | Cookie login/logout, session bootstrap + refresh, CSRF, lockout on failed logins |
| Organizations | ✅ | ✅ | ✅ | Multi-tenant orgs; list, switch, update; each is a fully isolated tenant |
| **Create organization (self-serve)** | ✅ | ✅ | ✅ | Create a new isolated org from the top bar; you become owner + a default workspace is made |
| Workspaces | ✅ | ✅ | ✅ | Isolated workspaces inside an org; list, switch, create, update |
| Members & invitations | ✅ | ✅ | ✅ | Invite users by email, change a member's role, manage membership per org |
| Roles & permissions (RBAC) | ✅ | ✅ | ✅ | Role-based access (owner/admin/editor/viewer/restricted); backend is authoritative |
| Tenant isolation | ✅ | ✅ | ✅ | One tenant cannot see/touch another's data (non-disclosing 404 on every request) |
| Governance / feature flags / quotas | ✅ | ✅ | ✅ | Server-driven permissions, entitlements, feature flags and quota gating |
| **Platform Super-Admin console** | ✅ | ✅ | ✅ | Cross-tenant operator view: all orgs/workspaces/users, suspend/activate, create org (super-admin only) |
| Connector catalog | ✅ | ✅ | ✅ | Browse 100 connectors with search + category/status/deployment filters and honest status + requirements |
| Connections — CRUD | ✅ | ✅ | ✅ | Create/edit/archive/delete data connections, tenant-scoped with optimistic concurrency |
| Connections — test | ✅ | ✅ | ✅ | Live connectivity/auth test for PostgreSQL, MySQL, REST; safe diagnostic codes |
| Connections — secrets | ✅ | ✅ | ✅ | Write-only, AES-256-GCM encrypted credentials; replace/rotate; never returned in API/UI |
| Datasets — catalog | ✅ | ✅ | ✅ | List/search/sort datasets; metadata, ownership, tags |
| **Datasets — CSV upload from device** | ✅ | ✅ | ✅ | Upload a .csv/.tsv file, auto-fill table/name, register as a governed dataset |
| Datasets — schema/preview/profile | ✅ | ✅ | ✅ | Discover schema, preview rows, live column profiling |
| Data quality & lineage | ✅ | ✅ | ✅ | Quality checks/status and dataset-to-dataset lineage |
| Semantic layer | ✅ | ✅ | ✅ | Semantic models: dimensions, measures, metrics, KPIs; validated bounded queries |
| Dashboards — list & actions | ✅ | ✅ | ✅ | Dashboard list with a working ⋯ menu: rename, duplicate, archive, **delete** (confirmation) |
| Dashboard Studio | ✅ | ✅ | ✅ | Build dashboards: widgets, layout, filters, save, publish, versions, optimistic concurrency |
| Dashboard export & download | ✅ | ✅ | ✅ | Async PDF/PNG/JSON/CSV export from the published version; secure single-use signed download |
| Dashboard sharing / snapshots / delivery | ✅ | ✅ | ✅ | Viewer sharing, snapshots, scheduled email delivery with preview |
| Pipeline Studio | ✅ | ✅ | ✅ | Build node/edge pipelines, validate graph + formulas, publish immutable versions |
| Pipeline runs | ✅ | ✅ | ✅ | Async worker execution with progress, logs, results, retry, cancel |
| Files | ✅ | ✅ | ✅ | Upload with validation + fail-closed malware-scan gate + secure download |
| Jobs & real-time events (SSE) | ✅ | ✅ | ✅ | Background jobs and tenant-scoped live progress events |

## ✅ Connectors — catalog complete; a few operational (rest are honest placeholders)

| Connector(s) | FE (catalog) | BE (usable) | Prod-ready | What it does |
| --- | :--: | :--: | :--: | --- |
| PostgreSQL | ✅ | ✅ available | ✅ | Full connect + test + metadata discovery |
| REST API (generic) | ✅ | ✅ available | ✅ | HTTP source with SSRF protection, TLS, bearer/API-key auth |
| Local file upload | ✅ | ✅ available | ✅ | Device CSV upload (via Datasets) |
| MySQL | ✅ | ✅ beta | ✅ | Connect + test + discovery (functional, pending broader certification) |
| MS SQL / Oracle / Db2 / SAP HANA / Teradata | ✅ | ⚠️ requires driver | ❌ | Catalog-defined; need the vendor driver in the connector runtime |
| SAP S/4HANA, ECC, HDFS, SMB | ✅ | ⚠️ requires agent | ❌ | Catalog-defined; on-prem systems need the secure agent/gateway |
| Snowflake, BigQuery, Redshift, Databricks, S3/MinIO/Blob/GCS, Kafka, Salesforce, Jira, ServiceNow, … (~87) | ✅ | ❌ planned | ❌ | Accurate catalog entries (auth methods, requirements) awaiting adapter + credentials; not creatable |

## ❌ Frontend-only — not wired to backend (demo/mock, later phases)

| Module | FE | BE | Prod-ready | What it does (today = mock) |
| --- | :--: | :--: | :--: | --- |
| AI Studio (assistant/agents/knowledge) | ✅ | ❌ | ❌ | AI surfaces, hidden behind a feature flag; demo data |
| Automation | ✅ | ❌ | ❌ | Workflow/automation builder UI; demo data |
| Billing | ✅ | ❌ | ❌ | Plans/usage/invoices UI; demo data |
| Marketplace | ✅ | ❌ | ❌ | Extension catalog UI; demo data |
| Insights | ✅ | ❌ | ❌ | Insight boards UI; demo data |
| Reports | ✅ | ❌ | ❌ | Report builder UI; demo data |
| Operations (activity / audit center / usage) | ✅ | ❌ | ❌ | Operational views UI; demo data |
| Developer portal | ✅ | ❌ | ❌ | API keys/developer UI; demo data |
| Home widgets | ✅ | ❌ | ❌ | Home overview widgets; demo data |

## Bottom line
The **data + tenancy platform spine** — auth → orgs/workspaces (create + isolate) → RBAC →
**platform super-admin** → connections (+catalog, +MySQL) → datasets (+device upload) → semantic →
dashboards (+delete, +PDF/PNG export) → pipelines → files/events — is **live and production-ready**.
The "product surface" modules (AI, automation, billing, marketplace, insights, reports, operations,
developer, home) are **UI-only** placeholders for later phases.
