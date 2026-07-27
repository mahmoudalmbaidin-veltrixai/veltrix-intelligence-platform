# VIP — Platform Status Matrix (Front vs Back vs Live)

Legend: ✅ done · ⚠️ partial · ❌ not yet (mock/demo) · **Live** = wired front↔back and testable now.

## Fully live — frontend + backend, testable end-to-end

| Module / Feature | Frontend | Backend | Live & testable | Notes |
| --- | :---: | :---: | :---: | --- |
| Login / logout / session / CSRF | ✅ | ✅ | ✅ | Cookie session, refresh, lockout |
| Organizations & workspaces (switch) | ✅ | ✅ | ✅ | Tenant context enforced |
| Roles & permissions (RBAC) | ✅ | ✅ | ✅ | Backend authoritative; viewer/restricted denied |
| Cross-tenant isolation | ✅ | ✅ | ✅ | A cannot see B (404) |
| Members & invitations | ✅ | ✅ | ✅ | `/admin/members` |
| Governance / feature flags | ✅ | ✅ | ✅ | `/admin/governance`, `/admin/feature-flags` |
| Connector catalog (browse/search/filter/requirements) | ✅ | ✅ | ✅ | 100 connectors, honest status badges |
| Connections — list / create / edit / archive / delete | ✅ | ✅ | ✅ | Tenant-scoped, optimistic concurrency |
| Connections — **test connection** | ✅ | ✅ | ✅ | Live for PostgreSQL, MySQL, REST |
| Connections — secret storage / replace / rotate | ✅ | ✅ | ✅ | AES-256-GCM, write-only, never returned |
| Datasets — list / search / sort / filter | ✅ | ✅ | ✅ | |
| Datasets — **CSV upload from device** | ✅ | ✅ | ✅ | New; auto-fills table/name |
| Datasets — schema discovery / preview / profile | ✅ | ✅ | ✅ | |
| Data quality / lineage | ✅ | ✅ | ✅ | `/datasets/quality`, `/datasets/lineage` |
| Semantic models / dimensions / measures / metrics / KPIs | ✅ | ✅ | ✅ | `/semantic`, `/semantic/metrics` |
| Dashboards — list / ⋯ menu / delete | ✅ | ✅ | ✅ | Menu fix (teleport); type-to-confirm delete |
| Dashboard Studio — create / widgets / save / publish / versions | ✅ | ✅ | ✅ | Layout persists; optimistic concurrency |
| Dashboard **export PDF / PNG + secure download** | ✅ | ✅ | ✅ | Real files; requires published dashboard |
| Dashboard sharing / snapshots / delivery schedule | ✅ | ✅ | ✅ | Email preview via provider abstraction |
| Pipelines — build / nodes / edges / validate | ✅ | ✅ | ✅ | |
| Pipelines — publish / **run (async worker)** / logs / results / retry / cancel | ✅ | ✅ | ✅ | Real worker execution |
| Files — upload / validation / malware-scan gate / secure download | ✅ | ✅ | ✅ | Fail-closed scanning |
| Real-time job/run events (SSE) | ✅ | ✅ | ✅ | Tenant-scoped |

## Connectors detail (front done for all; back only for a few)

| Connector group | Frontend (catalog) | Backend (usable) | Live & testable |
| --- | :---: | :---: | :---: |
| PostgreSQL | ✅ | ✅ available | ✅ |
| REST API (generic) | ✅ | ✅ available | ✅ |
| Local file upload | ✅ | ✅ available | ✅ (via Datasets) |
| MySQL | ✅ | ✅ beta | ✅ (local server) |
| MS SQL / Oracle / Db2 / SAP HANA / Teradata | ✅ | ⚠️ requires driver | ❌ |
| SAP S/4HANA, SAP ECC, HDFS, SMB | ✅ | ⚠️ requires on-prem agent | ❌ |
| Snowflake, BigQuery, Redshift, Databricks, S3/MinIO/Blob/GCS, SFTP, Salesforce, Kafka, Jira, ServiceNow, … (≈87) | ✅ | ❌ planned (catalog only) | ❌ |

> The catalog shows all 100 connectors with accurate status; only the 4 "available/beta" can actually be created/tested. Planned ones are visible but **not** creatable.

## Frontend only — NOT wired to backend (mock/demo, later phases)

| Module | Frontend | Backend | Live | Notes |
| --- | :---: | :---: | :---: | --- |
| AI Studio (assistant/agents/knowledge) | ✅ | ❌ | ❌ | Hidden behind `ai_studio` flag |
| Automation builder | ✅ | ❌ | ❌ | Mock data |
| Billing / plans / usage | ✅ | ❌ | ❌ | Mock data |
| Marketplace | ✅ | ❌ | ❌ | Mock data |
| Insights | ✅ | ❌ | ❌ | Mock data |
| Reports builder | ✅ | ❌ | ❌ | Mock data |
| Operations (activity / audit / usage views) | ✅ | ❌ | ❌ | Mock data |
| Developer portal / API keys | ✅ | ❌ | ❌ | Mock data |
| Home dashboard widgets | ✅ | ❌ | ❌ | Mock data |

## How to test live
URL `http://localhost:3009` · admin `tenant-a@vip.demo` (password shared separately) · Org Alpha / Alpha Workspace 1.
Full step-by-step: `docs/reports/MANUAL_TEST_SCENARIO.md`. Sample data: `sample-data/vip_sales_sample.csv`.

**Summary:** the core data platform (auth → tenancy/RBAC → connections → datasets → semantic → dashboards+export → pipelines → files/events) is **live end-to-end**. The "product surface" modules (AI, automation, billing, marketplace, insights, reports, operations, developer, home) are **frontend-only** for now.
