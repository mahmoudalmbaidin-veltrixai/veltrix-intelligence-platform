# VIP PRODUCTIZATION — STAGE 2 REPORT

## A. Starting State

| Item | Certified starting value |
|---|---|
| Branch | `feat/vip-productization-p1` |
| HEAD | `3c5d0a9b73a707b412611d7f44685ccfb77675c6` |
| Working tree | Dirty before Stage 2; explicitly preserved |
| API | `/health` 200; `/ready` 200 |
| Frontend | `http://localhost:3009` returned 200 |
| Backend | `vip-api-1` running and healthy |
| PostgreSQL | 17.10, healthy |
| Redis | 8.0.6, healthy |
| Workers | Dashboard worker and pipeline worker healthy |
| Scheduler | Embedded dashboard scheduling worker healthy; all demo delivery schedules paused |
| Migrations | Current at single head |
| Alembic current / heads | `20260808_0025 (head)` / `20260808_0025 (head)` |

Starting counts: 85 organizations, 124 workspaces, 127 users, 242 connections, 1,841 datasets, 609 pipelines, 35 semantic models, 976 dashboards, 45 published dashboards, 298 terminal jobs exposed as notification activity, 76 notification-read rows, and 39,861 audit events.

Pre-existing uncommitted work was identified before edits: modified `Makefile`; untracked `DECKS/`, `VIP_CLIENT_DEMO_CHECKLIST.md`, `VIP_CLIENT_DEMO_SCRIPT.md`, `VIP_DEMO_ENVIRONMENT_INVENTORY.md`, `VIP_Enterprise_Demo_Environment_and_User_Access_Register.xlsx`, `demo-data/vip_demo_sales_orders.csv`, `docs/certification/`, `scripts/certification/`, and `scripts/demo/`. Only Stage 2 files/hunks were committed; unrelated material remains preserved.

## B. Database Pollution Audit

The pre-cleanup inventory reviewed names, timestamps, ownership, tenant relationships, schemas, source-table patterns, and generated provenance before destructive work.

| Entity | Before | Removed | Retained / rebuilt | Final |
|---|---:|---:|---:|---:|
| Organizations | 85 | 82 | 3 | 3 |
| Workspaces | 124 | 115 | 9 | 9 |
| Users | 127 | 102 | 25 (24 demo + platform admin) | 25 |
| Connections | 242 | 233 | 9 | 9 |
| Datasets | 1,841 | 1,820 | 21 | 21 |
| Pipelines | 609 | 600 | 9 | 9 |
| Semantic models | 35 | 26 | 9 | 9 |
| Dashboards | 976 | 967 | 9 | 9 |
| Published dashboards | 45 | 36 | 9 | 9 |
| Notification source jobs | 298 | 283 | 15 | 15 |
| Notification reads | 76 | 64 | 12 final read markers | 12 |
| Audit events | 39,861 | 38,129 | 1,732 legitimate rebuilt actions | 1,732 |

Internal inventory classification:

| Entity type | Count | Suspected QA/test | Suspected demo | Keep? | Reason |
|---|---:|---:|---:|---|---|
| Organizations | 85 | 82 | 3 | Exact three only | 82 matched reviewed fixture/integration/automated patterns; three matched the deliberate fictional manifest |
| Non-demo users | 102 | 102 | 0 | No | Exact usernames were reviewed and allowlisted for deletion |
| Demo users + platform admin | 25 | 0 | 25 | Yes/rebuild | Required RBAC personas and non-tenant provisioning account |
| QA schemas | 13 | 13 | 0 | No | Exact reviewed QA/certification schemas |
| QA public source tables | 77 | 77 | 0 | No | Exact conservative test/certification table patterns |
| Public application tables | 85 | 0 | 0 | Yes | System-required VIP/Alembic structures |
| Demo schemas | 3 | 0 | 3 | Yes/rebuild | Dedicated synthetic sources |

### Definitely disposable QA/test records

The 82 non-demo organizations and their descendants, 102 exact non-demo usernames, 13 exact QA schemas, and 77 exact QA public source tables were deleted. This included the reported fixture/integration/scheduler/settings/temp/`pg-*` families where present in the reviewed inventory.

### Existing deliberate demo records

Northstar, Crestline, and Meridian were recognized as deliberate demo tenants. They were safely dropped and deterministically rebuilt so IDs, relationships, data files, pipelines, semantics, dashboards, exports, notifications, and credentials all share one current manifest.

### System-required records

VIP public application tables, Alembic state, PostgreSQL/Redis runtime structures, and `vip.demo.platform.admin` were retained. No system organization is technically required, so the final organization count is exactly three.

### Ambiguous records — do not delete automatically

No ambiguous target was authorized. The reset computes unknown organizations, users, schemas, and public QA tables and aborts if any value is outside the exact allowlist. Empty clean-state inventories are handled correctly and were exercised on repeated reset runs.

### Backup and restore certification

- Backup: `artifacts/demo-stage2/backups/vip-stage2-precleanup-20260825-130213.dump`
- Size: 7,031,220 bytes
- SHA-256: `3D12A3807A313AA975B15CDB00D4D202FF410D1C98B79AC6A22496CA32E63DC6`
- Backup method: PostgreSQL custom-format `pg_dump`, copied out of `vip-postgres-1`.
- Structural verification: `pg_restore --list` passed.
- Restore verification: restored with `pg_restore --exit-on-error --no-owner --no-acl` into disposable database `vip_stage2_restore_check`; verified `85|124|127|20260808_0025`; disposable database then removed.
- Restore command pattern: create an empty disposable database, then `pg_restore -U vip -d <database> --exit-on-error --no-owner --no-acl <dump>`. Stop application writers before any active-database restore.

## C. Final Demo Organizations

| Organization | Purpose | Workspaces | Users |
|---|---|---|---:|
| Northstar Retail Group | Retail/commercial, supply-chain, and executive analytics | Sales & Commercial; Supply Chain; Executive Management | 8 |
| Crestline Telecom Services | Network, field-maintenance, and service-quality analytics | Network Operations; Field Maintenance; Quality & Performance | 8 |
| Meridian Facilities Solutions | EHS, asset maintenance, and service-delivery analytics | EHS & Compliance; Maintenance Operations; Service Performance | 8 |

All names, personas, stories, and data are fictional and synthetic.

## D. User / RBAC Matrix

| Persona | Per organization | Actual roles | Certified behavior |
|---|---:|---|---|
| Organization administrator | 1 | `organization_admin`; `workspace_admin` in all three workspaces | Organization administration; no cross-org access |
| Workspace administrator | 3 | `organization_member` + scoped `workspace_admin` | Workspace administration only in assigned scope |
| Analyst/editor | 2 | `organization_member` + `editor` / selected viewer scopes | Create/edit analytics; cannot administer memberships |
| Viewer | 2 | `organization_member` + `viewer` | Published consumption; cannot create pipeline or export |
| Platform administrator | 1 global | `is_platform_admin=true` | Provisions tenants/users; no shared tenant credential |

The committed report contains no passwords. The 24 passwords are unique, hashed, and `must_change_password=false` for direct controlled-demo login; the platform password is separate. The ignored local register is ACL-restricted to the current operator, Administrators, and SYSTEM.

## E. Connections

Nine professional PostgreSQL landing connections exist, one per workspace, named `<Workspace> — Demo PostgreSQL Landing`. All nine are `active`, last test `success`, with local measured latency 22–33 ms in the certified run. File-upload workspaces additionally retain the governed CSV/XLSX upload records in the manifest; no fake connector types are presented.

## F. Demo Data Sources

- Dedicated schemas: `vip_demo_northstar`, `vip_demo_crestline`, `vip_demo_meridian`.
- Raw business rows: 5,403 across nine source tables; benchmark rows: 15 across three regional-target tables.
- Curated output rows: 5,398.
- Fixed seed: `240824`.
- PostgreSQL source examples: Sales & Commercial, Network Operations, Maintenance Operations.
- CSV uploads: Supply Chain, Quality & Performance, Service Performance.
- XLSX uploads: Executive Management, Field Maintenance, EHS & Compliance.
- XLSX workbooks are regenerated deterministically from the current CSV seed by a standard-library converter during every reset; ZIP structure checks passed.

## G. Datasets

There are 21 curated assets: nine raw datasets, nine curated outputs, and three regional benchmark lookups. Names and row counts are documented in `docs/demo/DEMO_ENVIRONMENT.md`. All are active and synthetic. Eight raw datasets pass quality evaluation; the single Northstar quality scenario intentionally fails before curation.

## H. Data Quality Scenario

`Sales Transactions — Synthetic Raw` contains 603 rows. Its controlled conditions and results are:

| Rule | Type | Result | Failures / sample |
|---|---|---|---:|
| Business identifier is required | `not_null` | Failing | 1 / 603 |
| Business identifier is unique | `unique` | Failing | 3 / 603 |
| Primary value is non-negative | `range` | Failing | 1 / 603 |
| Region uses governed values | `accepted_values` | Warning | 1 / 603 |

The evaluation has four rules, zero passing, one warning, three failing; the curated output contains 598 rows after null handling, filtering, validation, and deduplication. All other raw datasets pass, preventing the whole environment from looking dirty.

## I. Pipelines

All nine pipelines are published; latest runs succeeded; saved configuration, reopen, rerun, permissions, and outputs were verified.

| Pipeline | Nodes / edges | Purpose | Latest execution |
|---|---:|---|---|
| Commercial Revenue Quality and Target Attainment | 16 / 15 | Clean/join sales with regional targets, validate, aggregate, output/export | Succeeded; 7,820 processed |
| Inventory Risk and Fulfillment Curation | 9 / 8 | Inventory/fulfillment curation | Succeeded; 4,805 |
| Executive KPI Consolidation | 9 / 8 | Executive KPI consolidation | Succeeded; 4,805 |
| Network Availability and Incident Curation | 16 / 15 | Join incidents with regional targets and curate network performance | Succeeded; 7,815 |
| Work Order and SLA Curation | 9 / 8 | Work-order/SLA preparation | Succeeded; 4,805 |
| Service Quality Score Curation | 9 / 8 | Service-quality scoring | Succeeded; 4,805 |
| EHS Risk and Compliance Curation | 16 / 15 | Join EHS activity with compliance targets and curate risk | Succeeded; 7,815 |
| Asset Reliability and Cost Curation | 9 / 8 | Asset reliability/cost preparation | Succeeded; 4,805 |
| Service Ticket and SLA Curation | 9 / 8 | Service-ticket/SLA preparation | Succeeded; 4,805 |

Flagship node types: source dataset, lookup source, select, rename, filter, null handling, type convert, deduplicate, join, formula, row validation, sort, output dataset, aggregate, and file export. Supporting pipelines use the supported curation subset without trivial filler nodes. Nine exceeds the preferred 3–5 because one complete, relevant workflow is retained per non-redundant workspace; three are the primary flagship flows.

## J. Semantic Models

Nine models are published. Representative dimensions: Date, Period, Region, Status, Product Category, Store Cluster, Incident Severity, Network Site, Facility, Risk Level, Maintenance Type, and Service Type. Representative supported measures include Revenue/Cost/Service Value (`sum`), record counts (`count_distinct`), and supported averages for score, availability, SLA compliance, resolution time, downtime, and customer satisfaction.

## K. Dashboards

Nine intentional dashboards are published: one per workspace, with three flagships. Flagships contain nine widgets and four global filters; supporting dashboards contain six widgets and four filters. Certified widget types are KPI, bar, line, column, donut, and table. The three flagship names are **Sales and Commercial Performance Dashboard**, **Network Operations Command Dashboard**, and **EHS and Compliance Dashboard**.

## L. Published Dashboards

All nine dashboards have a published version. Organization-admin/editor behavior and viewer read-only behavior were exercised. Direct edit/pipeline routes fail closed for viewers, and a foreign organization dashboard ID returns 404. Reload and published-view routes passed in Chromium, Firefox, and WebKit.

## M. Export Validation

Each flagship has one completed PDF and one completed PNG export: six completed jobs total.

| Flagship | PDF | PNG |
|---|---:|---:|
| Northstar | 13,853 bytes; SHA-256 `E4691D…EFFEC` | 104,094 bytes; `C557D5…56781` |
| Crestline | 13,816 bytes; `492A88…956F1E` | 104,365 bytes; `9EBEFB…14BEDA` |
| Meridian | 13,714 bytes; `044861…D715E1` | 102,329 bytes; `446CA2…B9FCC2` |

The final Northstar PDF and PNG were copied into ignored evidence, checked non-empty, and visually inspected. The PDF is one landscape A4 page, correctly titled, with KPI cards, charts, table, footer, no clipping, and correct values. The PNG is 2,880 × 4,028, complete and unclipped. Headline values reconcile to the 598-row curated output: total revenue SAR 892,117; 598 orders; average margin 78.0; average fulfillment 17.6 hours.

## N. Notifications

Final activity contains 15 real succeeded jobs: nine dataset-quality evaluations, three PDF exports, and three PNG exports. No AI/Billing/Marketplace/Automation/unsupported-report notifications exist. Chromium, Firefox, and WebKit each verified unread/read/mark-all behavior, reload persistence, and logout/login persistence. Final read-marker count is 12.

## O. Demo Reset Automation

Primary command: `scripts/demo/reset-demo-environment.ps1`; the Makefile exposes `make demo-reset` when GNU Make is used.

The workflow validates environment/backup/migrations/identity, inventories and refuses unknown targets, removes only exact approved QA state, regenerates deterministic CSV/XLSX/PostgreSQL source data, provisions organizations/workspaces/users/RBAC/connections/datasets/quality/pipelines/semantics/dashboards/exports/paused schedules, writes DPAPI credentials, and runs 22 API/RBAC checks. It was certified from the polluted database and then repeatedly from a zero-pollution clean inventory.

Safety controls: `APP_ENV=demo`, `ALLOW_DEMO_RESET=true`, `-ConfirmNonProduction`, local HTTP host only, API environment development/test, exact `vip` database/user, exact `vip-postgres-1` container, one Alembic head, >1 MiB restore-verified backup, `pg_restore --list`, exact tenant/user/schema/table allowlists, and runtime-injected PostgreSQL password. Production, remote, unknown, or flagless execution aborts before deletion.

## P. RBAC / Tenant Isolation Results

The deterministic API suite passed 22/22:

- organization-admin login: 200 for all three organizations;
- published viewer access: 200 for all three flagships;
- viewer pipeline creation: 403;
- viewer export creation: 403;
- editor membership administration: 403;
- unauthorized workspace dataset: 404;
- cross-organization dashboard ID: 404;
- credential state: `24|24|0` for users, hashed passwords, and login-ready status.

The browser suite repeated viewer authoring denial and cross-tenant 404 behavior through direct routes.

## Q. Regression Results

| Surface | Exact certified result |
|---|---|
| Backend non-integration | 305 passed, 25 skipped, 104 deselected |
| Backend integration | 104 passed, 330 deselected |
| Backend total executed | 409 passed, 25 skipped |
| Ruff | 289 files checked/formatted; pass |
| Mypy | 177 source files; pass |
| Frontend Vitest | 70 files, 426 passed |
| Frontend ESLint | Pass |
| Frontend Prettier | Pass |
| Frontend typecheck | Pass |
| Frontend production build | Pass |
| Chromium | 2/2 passed, retries 0 |
| Firefox | 2/2 passed, retries 0 |
| WebKit | 2/2 passed, retries 0 |
| Cross-browser total | 6/6 passed in 5.1 minutes, retries 0 |
| Browser artifact secret scan | 0 findings |

With 5,403 source records, initial route rendering varied by browser. Certification uses a 30-second per-route readiness budget and no retries; this rerun completed the admin journeys in approximately 59–84 seconds and viewer journeys in approximately 15–25 seconds.

## R. Remaining Issues

### BLOCKS STAGE 3

None arising from Stage 2. Stage 3 was not started.

### NON-BLOCKING

- Cold local Docker/browser loads can take tens of seconds; the recommended operator pre-warm step avoids dead air.
- Nine pipelines and nine dashboards exceed the preferred 3–5 overall because each of the nine non-redundant workspaces retains one complete curated workflow and one intentional dashboard. The sales journey should focus on the three flagships.
- Delivery schedules are present only as paused safe-demo records; no email delivery is configured or claimed.

### LATER

Production infrastructure, DNS/TLS, transactional email, invitation delivery, SSO/MFA, AI Studio, Automation, Billing, and Marketplace remain outside Stage 2.

## S. Final Database State

| Entity | Final |
|---|---:|
| Organizations | 3 |
| Workspaces | 9 |
| Users | 25 total: 24 demo + 1 platform admin |
| Connections | 9 |
| Datasets | 21 |
| Pipelines | 9 |
| Semantic models | 9 |
| Dashboards | 9 |
| Published dashboards | 9 |
| Notification source jobs | 15 |
| Notification reads | 12 |
| Audit events | 1,732 |
| Dedicated demo schemas | 3 |
| Recognized QA public source tables | 0 |

All 24 demo users are active, have 24 distinct password hashes, and are `must_change_password=false`. The platform admin is active, separate, and not a tenant. Only the three fictional organizations exist.

## T. Final Verdict

### PASS — CLEAN SELLABLE DEMO ENVIRONMENT CERTIFIED
