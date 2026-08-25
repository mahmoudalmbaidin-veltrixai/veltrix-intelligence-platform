# VIP Stage 2 Demo Environment Manifest

This manifest describes the non-production, synthetic VIP sales-demo environment created by `scripts/demo/reset-demo-environment.ps1`. It contains no passwords. Stable machine-readable scenario definitions live in `demo-data/stage4/scenarios.json`; generated IDs live only in the ignored `artifacts/demo-stage4/environment-manifest.json`.

## Safety boundary

- Environment: local/demo only; never production.
- Supported V1 sources demonstrated: PostgreSQL, CSV upload, XLSX upload.
- Explicit reset gates: `APP_ENV=demo`, `ALLOW_DEMO_RESET=true`, local HTTP API, development/test API identity, exact local database/container identity, one Alembic head, restore-verified backup, `-ConfirmNonProduction`, and an exact cleanup allowlist.
- Unsupported and excluded: email activation/delivery, invitations, AI Studio, Automation, Billing, Marketplace, production hosting, DNS/TLS, SSO/MFA, Resend/SES/SMTP.
- Synthetic data marker: every source row includes `SYNTHETIC DEMO DATA` notes.

## Organizations and workspaces

| Organization | Industry story | Workspaces | Flagship |
|---|---|---|---|
| Northstar Retail Group | Retail and distribution performance | Sales & Commercial; Supply Chain; Executive Management | Sales & Commercial |
| Crestline Telecom Services | Telecommunications operations and service assurance | Network Operations; Field Maintenance; Quality & Performance | Network Operations |
| Meridian Facilities Solutions | Facilities, EHS, maintenance, and service delivery | EHS & Compliance; Maintenance Operations; Service Performance | EHS & Compliance |

There is no additional system tenant. Platform provisioning is performed by the non-tenant account `vip.demo.platform.admin`.

## Users and RBAC

Each organization has eight unique demo users:

| Persona | Count per organization | Actual VIP role mapping | Demonstration purpose |
|---|---:|---|---|
| Organization administrator | 1 | `organization_admin` plus `workspace_admin` in all three workspaces | Organization governance and administrative separation |
| Workspace administrator | 3 | `organization_member` plus `workspace_admin` in one workspace | Department administration |
| Analyst/editor | 2 | `organization_member` plus `editor` in assigned workspaces; selected secondary scopes are viewer | Authoring without membership administration |
| Viewer | 2 | `organization_member` plus `viewer` | Published-dashboard consumption only |

All 24 passwords are unique and hashed. All 24 users are active and remain `must_change_password=false` so the operator register works directly during controlled sales demonstrations. Plaintext credentials exist only in the ignored, access-restricted operator register `VIP_Enterprise_Demo_Environment_and_User_Access_Register.xlsx` and the current Windows user's DPAPI store.

## Data sources and datasets

The three dedicated schemas are `vip_demo_northstar`, `vip_demo_crestline`, and `vip_demo_meridian`. They contain 5,403 raw business records plus 15 regional benchmark rows. The seed is fixed at `240824`.

| Organization / workspace | Ingestion path | Raw dataset | Curated dataset | Lookup |
|---|---|---|---|---|
| Northstar / Sales & Commercial | PostgreSQL | Sales Transactions — Synthetic Raw (603) | Curated Commercial Performance (598) | Regional Sales Targets (5 CSV rows) |
| Northstar / Supply Chain | CSV upload | Inventory and Fulfillment — Synthetic Raw (600) | Curated Supply Chain Operations (600) | — |
| Northstar / Executive Management | XLSX upload | Executive KPI Pack — Synthetic Raw (600) | Curated Executive KPIs (600) | — |
| Crestline / Network Operations | PostgreSQL | Network Sites and Incidents — Synthetic Raw (600) | Curated Network Operations (600) | Regional Availability Targets (5 CSV rows) |
| Crestline / Field Maintenance | XLSX upload | Field Work Orders — Synthetic Raw (600) | Curated Field Maintenance (600) | — |
| Crestline / Quality & Performance | CSV upload | Service Quality Measures — Synthetic Raw (600) | Curated Service Quality (600) | — |
| Meridian / EHS & Compliance | XLSX upload | EHS Inspections and Incidents — Synthetic Raw (600) | Curated EHS Compliance (600) | Regional Compliance Targets (5 CSV rows) |
| Meridian / Maintenance Operations | PostgreSQL | Asset Maintenance Events — Synthetic Raw (600) | Curated Asset Maintenance (600) | — |
| Meridian / Service Performance | CSV upload | Service Tickets — Synthetic Raw (600) | Curated Service Delivery (600) | — |

Every workspace also has a tested, environment-credential-backed PostgreSQL landing connection named `<Workspace> — Demo PostgreSQL Landing`. Credentials are injected at reset time and are not committed.

## Data-quality scenario

Only `Sales Transactions — Synthetic Raw` is deliberately dirty. It contains one missing business ID, three duplicate-ID failures, one negative primary value, one missing region, and one lower-case region value. Its four governed rules show one warning and three failures before curation. The other eight raw datasets pass their quality evaluations, so the wider demo remains presentation-clean.

## Pipelines

All pipelines are published, reopen successfully, and have a latest successful rerun.

| Pipeline | Workspace | Graph | Latest rows processed |
|---|---|---:|---:|
| Commercial Revenue Quality and Target Attainment | Northstar / Sales & Commercial | 16 nodes / 15 edges | 7,820 |
| Inventory Risk and Fulfillment Curation | Northstar / Supply Chain | 9 / 8 | 4,805 |
| Executive KPI Consolidation | Northstar / Executive Management | 9 / 8 | 4,805 |
| Network Availability and Incident Curation | Crestline / Network Operations | 16 / 15 | 7,815 |
| Work Order and SLA Curation | Crestline / Field Maintenance | 9 / 8 | 4,805 |
| Service Quality Score Curation | Crestline / Quality & Performance | 9 / 8 | 4,805 |
| EHS Risk and Compliance Curation | Meridian / EHS & Compliance | 16 / 15 | 7,815 |
| Asset Reliability and Cost Curation | Meridian / Maintenance Operations | 9 / 8 | 4,805 |
| Service Ticket and SLA Curation | Meridian / Service Performance | 9 / 8 | 4,805 |

Flagship graphs include source, lookup source, selection, rename, filter, null handling, type conversion, deduplication, join, calculation, row validation, sort, output dataset, aggregate, and file export. Supporting graphs omit the lookup/join/export branch but remain full curation workflows, not one-node fixtures.

## Semantic models and dashboards

Each workspace has one published semantic model with business dimensions, five supported measures, and one published dashboard.

| Organization | Semantic models | Dashboards |
|---|---|---|
| Northstar | Northstar Commercial; Supply Chain; Executive semantic models | Sales and Commercial Performance Dashboard; Supply Chain and Inventory Dashboard; Northstar Executive Overview |
| Crestline | Crestline Network Operations; Field Maintenance; Quality semantic models | Network Operations Command Dashboard; Field Maintenance and SLA Dashboard; Service Quality and Performance Dashboard |
| Meridian | Meridian EHS; Maintenance; Service semantic models | EHS and Compliance Dashboard; Asset Maintenance Dashboard; Service Delivery Performance Dashboard |

The three flagships contain nine widgets each: KPI cards, bar, line, column, donut, and detail table, with four global filters. The six supporting dashboards contain six widgets each: KPIs, bar, line, and table, with four filters. All nine are published. Each flagship has completed PDF and PNG exports; delivery schedules exist only as paused safe-demo records and never send email.

## Recommended 20-minute journey

1. Sign in as the Northstar organization administrator and show tenant/workspace separation.
2. Open the Sales & Commercial PostgreSQL connection and run the live connection test.
3. Open the raw dataset, profile it, and explain the deliberate quality failures.
4. Open the 16-node flagship pipeline, review the join/quality/output branches, and show the successful run.
5. Open the published semantic model and its business measures.
6. Open, filter, reload, and publish/view the flagship dashboard; show PDF/PNG export history.
7. Open Notifications and demonstrate unread/read/mark-all persistence.
8. Sign in as the Northstar viewer and show published consumption plus blocked authoring/cross-tenant routes.

See `docs/demo/DEMO_OPERATOR_GUIDE.md` for the timed operator script.
