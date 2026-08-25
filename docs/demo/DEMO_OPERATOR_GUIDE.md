# VIP Stage 2 Demo Operator Guide

This guide is for a 15–25 minute local sales demonstration. It describes only certified V1 behavior.

## Before the session (3–5 minutes)

1. Confirm `http://localhost:8000/ready` and `http://localhost:3009` return HTTP 200.
2. Confirm API, PostgreSQL, Redis, dashboard worker, and pipeline worker are healthy with `docker compose ps`.
3. Open the ignored, access-restricted `VIP_Enterprise_Demo_Environment_and_User_Access_Register.xlsx` privately. Do not screen-share the password column.
4. Select the Northstar organization-admin and commercial-viewer credentials. They are distinct accounts and passwords.
5. Open the Northstar flagship dashboard once so the local browser and chart assets are warm.
6. Keep Stage 3 capabilities out of the conversation: there is no active email delivery, invitation flow, AI Studio, Automation, Billing, Marketplace, SSO/MFA, or production deployment in this environment.

## 20-minute client journey

### 1. Enterprise separation — 2 minutes

Sign in as `northstar.org.admin` using the private register. Show Northstar Retail Group and its Sales & Commercial, Supply Chain, and Executive Management workspaces. Explain that organization membership and workspace roles are separate real VIP controls.

Talking point: Northstar, Crestline, and Meridian are fictional, isolated tenants with synthetic data.

### 2. PostgreSQL connection — 2 minutes

Open **Sales & Commercial — Demo PostgreSQL Landing**. Show the healthy state and run **Test connection**. Explain that the password is environment-injected during reset, not committed or exposed in frontend code.

Talking point: V1 supports PostgreSQL and governed file upload; do not imply other connectors are active.

### 3. Dataset and data quality — 3 minutes

Open **Sales Transactions — Synthetic Raw**, then the Quality tab. Show the 603-row profile and the deliberately controlled conditions:

- one missing ID;
- three duplicate-ID failures;
- one negative primary value;
- a missing/lower-case region condition;
- three failing rules and one warning.

Explain that the other eight demo sources pass their quality checks, so this is a focused “before analysis” use case, not a generally dirty environment.

### 4. Pipeline — 4 minutes

Open **Commercial Revenue Quality and Target Attainment**. Walk left to right through source, regional-target lookup, selection/rename/filter, null handling, conversion, deduplication, join, formula, quality gate, sort, curated output, aggregation, and file export. Show the latest **Succeeded** run and 7,820 processed node-rows. Reopen or reload the pipeline to demonstrate persistence.

### 5. Semantic model — 2 minutes

Open **Northstar Commercial Semantic Model**. Show business dimensions such as Date, Period, Region, Product Category, Store Cluster, and Status. Show supported measures: Revenue, Cost, Orders, Average Margin Score, and Average Fulfillment Hours.

### 6. Dashboard, publication, and export — 4 minutes

Open **Sales and Commercial Performance Dashboard**. Demonstrate KPI cards, region bar chart, trend line, product donut, status column chart, detail table, and the Date/Region/Product Category/Status filters. Reload the page, then open the share/export history and show completed PDF and PNG exports.

Expected headline values for an unfiltered dashboard include total revenue about SAR 892,117, 598 orders, average margin score 78.0, and average fulfillment 17.6 hours.

### 7. Notifications — 1 minute

Open Notifications. Show real quality-evaluation and dashboard-export activity. Demonstrate **Mark all read**, **Mark unread**, **Mark read**, reload persistence, and persistence after logout/login.

### 8. Viewer and isolation — 2 minutes

Sign out and sign in as `northstar.commercial.viewer`. Open the published Northstar flagship. Show that editing is absent. Direct authoring and editor routes fail closed, viewer export creation is prohibited, and a Crestline dashboard ID returns 404 rather than crossing the tenant boundary.

## Optional alternate stories

- Crestline: Network Operations Command Dashboard, network availability, incident severity, downtime, and regional targets.
- Meridian: EHS and Compliance Dashboard, inspected area, compliance score, corrective-action cost, and action closure time.
- File ingestion: Northstar Supply Chain (CSV) or Crestline Field Maintenance / Meridian EHS (XLSX).

## Reset procedure

Create and restore-verify a safety backup first. Then run the primary guarded entry point from the repository root:

```powershell
$env:APP_ENV = "demo"
$env:ALLOW_DEMO_RESET = "true"
$env:VIP_DEMO_POSTGRES_PASSWORD = <inject from the local operator environment>
pwsh -File .\scripts\demo\reset-demo-environment.ps1 `
  -Mode Apply `
  -VerifiedBackupPath <restore-verified-dump> `
  -ConfirmNonProduction
```

The command refuses production/non-local targets, a missing safety flag, a missing or structurally invalid backup, migration drift, unexpected organizations/users/schemas/tables, or an unexpected database/container identity. A second run from the clean state is certified.

## After the session

1. Close the private credential register.
2. Reset/recreate the environment before the next external session if credentials were exposed.
3. Confirm all 24 demo users are again marked `must_change_password=true`.
4. Do not enable paused email schedules or configure external mail delivery as part of Stage 2.
