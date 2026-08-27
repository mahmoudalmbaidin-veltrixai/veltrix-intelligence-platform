# VIP Demo Environment Inventory

## Organization

- Veltrix Demo Organization (`veltrix-demo-organization`)
- Dedicated, fictional, local demo tenant only
- Current resource IDs are recorded in ignored local file `artifacts/demo-stage2/environment-manifest.json` because reset recreates them

## Workspaces

- Executive Analytics — published executive consumption, dashboard, semantic model, and delivery example
- Sales Analytics — sales-team workspace demonstrating multi-workspace organization
- Operations Analytics — operations-team workspace demonstrating multi-workspace organization

## Users/personas

| Persona | Username | Demo email | Organization role | Workspace role |
| --- | --- | --- | --- | --- |
| Organization Admin | `demo.organization.admin` | `demo.admin@vip.example` | `organization_admin` | `workspace_admin` |
| Editor | `demo.sales.editor` | `demo.editor@vip.example` | `organization_member` | `editor` |
| Viewer | `demo.executive.viewer` | `demo.viewer@vip.example` | `organization_member` | `viewer` in Executive Analytics only |

Passwords are not stored in Git. They are protected with Windows DPAPI at `%LOCALAPPDATA%\Veltrix\VIP\demo-credentials.dpapi`. Run `scripts\demo\show-vip-demo-credentials.ps1` privately, off screen, when preparing logins.

## Connections

- Demo Sales PostgreSQL — healthy local PostgreSQL connection; credentials are write-only in VIP
- CSV / Excel — file ingestion path is shown from Datasets using the prepared CSV

## Files

- `demo-data/vip_demo_sales_orders.csv`
- 723 fictional sales rows, UTF-8 CSV
- Controlled issues: 3 duplicate rows, 2 null regions, 3 lowercase regions, 2 blank categories, 1 blank order ID, and 1 negative-revenue row
- No real customer or personal data

## Datasets

- Sales Orders — Raw CSV — 723 rows; DQ demonstration source
- Curated Sales Orders — 716 deterministic valid, standardized, deduplicated rows; semantic source
- PostgreSQL table source: `vip_demo_sales.sales_orders_raw`
- Governed output table: `vip_demo_sales.sales_orders_curated`

## Pipelines

- Sales Revenue Quality & Curation
- 12 supported nodes: source, select, rename, type conversion, invalid-row filter, null handling, region normalization, row validation, deduplication, curated output, regional aggregation, protected CSV artifact
- One known-good successful run is retained after preparation/reset

## Semantic models

- Executive Sales Semantic Model — published; timezone `Asia/Riyadh`; currency `SAR`
- Dimensions: Date, Month, Region, City, Product Category, Sales Channel, Sales Representative
- Metrics: Total Revenue, Total Profit, Order Count, Average Order Value, Profit Margin

## Dashboards

- Executive Sales Performance
- Four KPI cards, four charts, regional detail table, and Date/Region/Product Category/Sales Channel filters

## Published resources

- Published Executive Sales Performance viewer
- Published Executive Sales Semantic Model
- Published Sales Revenue Quality & Curation pipeline

## Schedules

- Monday Executive Sales Brief
- Weekly, `Asia/Riyadh`, PDF, disabled by default
- Demonstrates create/save/enable-disable behavior without promising transactional email delivery

## Expected notifications

- Dashboard export (PDF): succeeded
- Dashboard export (PNG): succeeded
- Evaluate dataset quality: succeeded
- All are marked read before the meeting; retain their clean recent state
- `STAGE1-NB-001`: do not click export-completion notifications; show notification state only

## Backup demo assets

- `artifacts/demo-stage2/backup-assets/Executive-Sales-Performance.pdf` — ignored local backup
- `artifacts/demo-stage2/backup-assets/Executive-Sales-Performance.png` — ignored local backup
- `artifacts/demo-stage2/environment-manifest.json` — ignored resource/evidence manifest
- Existing successful pipeline run, published semantic model, curated dataset, and published dashboard
