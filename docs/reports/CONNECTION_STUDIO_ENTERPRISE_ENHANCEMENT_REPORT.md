# VIP — Connection Studio Enterprise Enhancement Report

Date (UTC): 2026-07-26
Repository: veltrix-intelligence-platform (VIP)
Branch: `frontend/enterprise-ui-enhancement`
Baseline commit: `d3cf9b4` (working-tree changes uncommitted)

> Scope for this session (user-approved, phased): (1) enrich the server-authoritative
> connector registry with enterprise metadata and a broad, **honestly-status-marked**
> catalog; (2) upgrade the frontend catalog with search, filters, status badges and a
> requirements view; (3) make one additional connector — **MySQL** — genuinely work
> end-to-end with a real driver and a live server. No connector is presented as working
> unless it truly is.

---

## A. Executive Summary

**Before:** Connection Studio already had a solid, extensible foundation — a typed,
server-authoritative registry (`catalog.py`), AES-256-GCM encrypted write-only secrets,
SSRF-guarded connection testers, tenant-scoped models, full CRUD + test + credential
replace/rotate APIs, and a frontend catalog + wizard + detail + list. Only **2** connectors
were actually usable (PostgreSQL, REST API); 9 others were bare disabled placeholders.

**Added / changed this session:**
- Registry enriched with enterprise metadata: `implementation_status`
  (available/beta/planned/requires_agent/requires_driver/disabled), `vendor`,
  `subcategory`, `auth_methods`, `deployment` (cloud/on-prem/hybrid), `capabilities`,
  human-readable `requirements`/network guidance, `documentation_reference`, `feature_flag`.
- Broad, accurate catalog: **100 connectors** across 14 categories (databases, warehouses,
  data lakes/object storage, files, APIs, ERP, CRM, marketing/commerce, streaming, BI,
  collaboration, HR/finance/identity, observability, email) — each marked with its **true**
  status. Only genuinely-working connectors are `available`/`beta`.
- Registry API (`GET /api/v1/connections/types`) now returns the full enterprise metadata;
  the frontend catalog was upgraded with search, category/status/deployment filters, honest
  status badges (Available/Beta/Planned/Requires driver/Requires agent), and a **requirements
  detail dialog** (auth methods, capabilities, network/setup requirements).
- **MySQL connector implemented for real** (`beta`): config + credential schema, an async
  `MySQLTester` (aiomysql) with SSRF host validation and safe error-code mapping, driver
  pinned into the API image, and an optional MySQL compose service (profile `connectors`).
  Verified live against a real MySQL 8.0 server.

**Overall readiness:** The catalog is production-honest and the create/test/secret pipeline
is real for the `available`/`beta` connectors. The vast majority of connectors are accurate
catalog definitions awaiting adapter implementation and external credentials.

**Verdict:** `CONNECTION STUDIO COMPLETE WITH EXTERNAL VERIFICATION PENDING`

---

## B. Connector Inventory (status distribution)

100 connectors total. Status counts: **available 3**, **beta 1**, **requires_driver 5**,
**requires_agent 4**, **planned 87**.

| Connector | Category | Backend status | Test | Discovery | Auth methods | Agent |
| --- | --- | --- | --- | --- | --- | --- |
| PostgreSQL | database | **available** | ✅ live (`postgresql_ping`) | metadata | username_password | no |
| MySQL | database | **beta** | ✅ live (`mysql_ping`, aiomysql) | metadata (planned) | username_password | no |
| REST API | api | **available** | ✅ live (`rest_head`, SSRF/TLS) | — | none/bearer/api_key | no |
| Local file upload | file | **available** | n/a (dataset upload) | file | none | no |
| MS SQL Server | database | requires_driver | contract | — | username_password/azure_ad | no |
| Oracle, Db2, Teradata, SAP HANA | database | requires_driver | contract | — | various | no |
| MariaDB, CockroachDB, TiDB, … | database | planned | contract | — | various | no |
| Snowflake, BigQuery, Redshift, Synapse, Databricks, ClickHouse, … | warehouse | planned | contract | — | password/key_pair/oauth/svc-acct | no |
| S3, MinIO, Azure Blob, ADLS, GCS, Iceberg, Delta, … | object_storage | planned (HDFS: requires_agent) | contract | file/partition | access_key/role/svc-acct | HDFS: yes |
| SFTP, FTPS, SharePoint, Drive, OneDrive, Dropbox | file | planned (SMB: requires_agent) | contract | file | password/key/oauth | SMB: yes |
| SAP S/4HANA, ECC | erp | requires_agent | contract | object | oauth/basic/cert | yes |
| Oracle Fusion, NetSuite, D365 F&O/BC, Odoo, Infor, Sage, Workday | erp | planned | contract | object | oauth/token | no |
| Salesforce, HubSpot, Zoho, D365 Sales, Pipedrive | crm | planned | contract | object | oauth/api_key | no |
| GA4, Google/Meta/LinkedIn Ads, Shopify, Stripe, Klaviyo | marketing | planned | contract | object | oauth/api_key | no |
| Kafka, Confluent, Event Hubs, Pub/Sub, Kinesis, RabbitMQ | streaming | planned | contract | topic | sasl/mtls/api_key | no |
| Power BI, Tableau, Looker, ThoughtSpot | bi | planned | contract | metadata only | oauth/pat/api_key | no |
| Jira, Confluence, ServiceNow, Zendesk, GitHub, GitLab, Slack, Notion | collaboration | planned | contract | object | oauth/token | no |
| SuccessFactors, BambooHR, QuickBooks, Xero, Okta, Entra ID | hr_finance | planned | contract | object | oauth/api_token | no |
| Elasticsearch, OpenSearch, Splunk, Datadog, Prometheus, InfluxDB | observability | planned | contract | index/metric | api_key/basic/token | no |

(Full machine-readable inventory is served by `GET /api/v1/connections/types`.)

---

## C. Architecture Changes

- **Registry** (`apps/api/src/vip_api/connections/catalog.py`): `ConnectionTypeDefinition`
  extended with enterprise metadata; `enabled` is now a derived property (`status in
  {available, beta}`) so a connector can never be "enabled" without a real adapter. Catalog
  grown to 100 accurately-marked entries. `validate_configuration`/`validate_credentials`
  unchanged in contract.
- **Schema/serialization** (`schemas.py`, `services.py`): `ConnectionTypeResponse` exposes the
  enriched metadata; `serialize_type` merges DB rows with the code-authoritative catalog by key
  (no migration needed — metadata is code-owned; the seed upserts the core columns).
- **Adapters/testers** (`testers.py`): added `MySQLTester` with lazy driver import (a missing
  optional driver degrades to a safe `CONNECTION_DRIVER_UNAVAILABLE` code instead of crashing
  the API), SSRF host validation, and MySQL error-number → safe-code mapping.
- **Frontend** (`connections.service.ts`, `ConnectorCatalogView.vue`): enriched `ConnectionType`
  type; new catalog with search, category/status/deployment filters, status badges, per-card
  auth/deployment chips, "Create connection" only for creatable connectors, and a requirements
  dialog. Planned connectors are visible but not creatable.
- **Dependencies** (`pyproject.toml`, `requirements*.lock`): `aiomysql==0.3.2` (+ `pymysql`)
  pinned and baked into the API image.
- **Infra** (`docker-compose.yml`): optional `mysql` service under profile `connectors` for
  local integration testing (`docker compose --profile connectors up -d mysql`).

Secret handling, tenant scoping, permissions, and audit are unchanged and were re-verified.

## D. Files Changed

| File | Purpose |
| --- | --- |
| `apps/api/src/vip_api/connections/catalog.py` | Enterprise metadata + 100-connector catalog + MySQL schema |
| `apps/api/src/vip_api/connections/schemas.py` | `ConnectionTypeResponse` enriched fields |
| `apps/api/src/vip_api/connections/services.py` | `serialize_type` merges catalog metadata |
| `apps/api/src/vip_api/connections/testers.py` | `MySQLTester` + registry entry |
| `apps/api/pyproject.toml`, `requirements.lock`, `requirements.runtime.lock` | `aiomysql` driver |
| `docker-compose.yml` | optional `mysql` service (profile `connectors`) |
| `apps/api/tests/unit/test_connector_registry.py` | registry invariants + MySQL validation |
| `src/modules/connections/connections.service.ts` | enriched `ConnectionType` + labels/icons |
| `src/modules/connections/ConnectorCatalogView.vue` | filters, status badges, requirements dialog |
| `e2e/connector-catalog.spec.ts` | catalog rendering/filter/requirements e2e |

## E. Database Migrations

**None required.** Connector metadata is code-authoritative and served at serialization time;
the existing `connection_types` table (seeded via `seed-connection-types`) stores only the core
columns, which the idempotent seed upserts. Existing saved connections are unaffected (the
`connections` table and secret storage are unchanged). Re-run `python -m vip_api.cli
seed-connection-types` after deploy to populate the new catalog rows.

## F. Security Assessment

- **SSRF:** MySQL and REST testers call `validate_host`/`validate_url` (block private/link-local/
  metadata ranges unless dev-allowed); redirects bounded; TLS enforced for REST.
- **Secret handling:** MySQL password stored write-only, AES-256-GCM encrypted; live create/test
  response contains **no plaintext** (verified — only `secret_fields:{password:{configured:true}}`).
- **Safe errors:** testers return safe codes (`CONNECTION_AUTHENTICATION_FAILED`,
  `CONNECTION_TIMEOUT`, `CONNECTION_HOST_UNREACHABLE`, `CONNECTION_DRIVER_UNAVAILABLE`,
  `CONNECTION_METADATA_UNAVAILABLE`) — raw driver exceptions are never surfaced.
- **Tenant/RBAC:** unchanged; connection create/test remain governance-gated and tenant-scoped
  (re-verified in the broader suite: viewer/restricted → 403, cross-tenant → 404).
- **Timeouts:** bounded by `CONNECTION_TEST_TIMEOUT_SECONDS`; pool `maxsize=1` for tests.
- **Driver resilience:** a missing optional driver never crashes the API (lazy import → safe code).

## G. Test Results

| Gate | Command | Result |
| --- | --- | --- |
| Backend lint | `ruff check .` | PASS |
| Backend format | `ruff format --check .` | PASS (187 files) |
| Backend types | `mypy src tests` | PASS (170 files) |
| Backend unit | `pytest -m "not integration"` | **86 passed** (+6 new registry tests) |
| Backend integration | `pytest -m integration` | **25 passed** |
| Migrations | `alembic upgrade head` | PASS (head `20260725_0011`, no new migration) |
| Frontend types | `npm run typecheck` | PASS |
| Frontend lint | `npm run lint` | PASS |
| Frontend format | `npm run format:check` | PASS |
| Frontend unit | `npm test` | **178 passed** |
| Frontend build | `npm run build` | PASS |
| Playwright (catalog) | `test:e2e connector-catalog` | **2 passed** |
| Docker compose | `docker compose config` | PASS (mysql under `connectors` profile) |
| API image build | `docker compose build api` | PASS (aiomysql baked in) |

## H. Live Connector Verification

- **Fully integration-tested (live):** PostgreSQL (pre-existing), **MySQL (new)** — created a
  connection against a real MySQL 8.0 server: create → 201, **test good creds → success/healthy/8ms**,
  **test bad creds → CONNECTION_AUTHENTICATION_FAILED**, no plaintext leak. REST API (live HEAD test).
- **Available, non-network:** Local file upload (handled by the dataset upload path).
- **Contract-complete, awaiting drivers/credentials:** MS SQL, Oracle, Db2, Teradata, SAP HANA
  (requires_driver); Snowflake, BigQuery, Redshift, Databricks, S3/MinIO/Blob/GCS, SFTP, etc.
  (planned) — accurate schemas/metadata, adapters not yet implemented.
- **Requires external agent:** SAP S/4HANA, SAP ECC, HDFS, SMB (on-premise; documented).

## I. Remaining Limitations (not hidden)

- 96 connectors are catalog definitions without runtime adapters yet (marked
  planned/requires_driver/requires_agent). They are **not** creatable in the UI.
- Dynamic wizard still uses the existing schema-driven form (unchanged this session); advanced
  field types (certificate/private-key upload, JSON editor, OAuth action, include/exclude
  editors) are not yet implemented for the planned connectors.
- Metadata discovery endpoints (`/discover`, `/schemas`, `/tables`, `/preview`) are not added
  this session; PostgreSQL retains its existing discovery capability metadata.
- The MySQL integration test is exercised via the running server here; a fully-automated
  Docker-profile integration test in CI is recommended as a follow-up.
- No external SaaS/cloud credentials were used (per the rules); those connectors remain planned.

## J. Final Verdict

**CONNECTION STUDIO COMPLETE WITH EXTERNAL VERIFICATION PENDING**

The registry, catalog, filters, status honesty, secret handling, and the create/test pipeline
are real and verified for the available/beta connectors, and MySQL was added as a genuinely
working (beta) connector proven against a live server. The broader catalog is accurately marked
and awaits per-connector adapter implementation and external credentials.
