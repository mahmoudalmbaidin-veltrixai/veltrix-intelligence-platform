# VIP Client Demo Script

## Core story

`CONNECT → PREPARE → GOVERN → MODEL → ANALYZE → PUBLISH → OPERATIONALIZE`

Keep the story in customer language. Describe outcomes, trust, and governed reuse; discuss implementation details only when asked.

## 0–2 min — Positioning

**One-sentence position:** VIP turns connected enterprise data into governed, reusable business metrics and decision-ready dashboards in one controlled workflow.

Open on Home in the Veltrix Demo Organization. Explain that the environment is a fictional enterprise sales operation prepared for a deterministic demonstration.

## 2–4 min — Organization & Governance

1. Show Veltrix Demo Organization.
2. Show Executive Analytics, Sales Analytics, and Operations Analytics; explain their distinct business purposes.
3. Show the actual roles: Organization Admin, `editor`, and `viewer`.
4. Explain that authors build governed assets while viewers consume published analytics without authoring or administration.

Do not open unrelated tenants or the cross-tenant platform console. Do not use the word “Analyst” as a role name; say “Editor, the analyst-equivalent authoring role.”

## 4–7 min — Connections & Data

1. Open Demo Sales PostgreSQL and show the successful health state. Do not reveal configuration secrets.
2. Open Datasets and preview Sales Orders — Raw CSV.
3. Keep `demo-data/vip_demo_sales_orders.csv` ready to show the supported file path; re-upload only when the customer explicitly wants to see ingestion live.
4. Explain that the prepared file contains 723 fictional orders and a small set of intentional quality issues.

Sales-safe connector statement:

> VIP V1 currently supports PostgreSQL and file-based ingestion as the primary generally available paths. Additional connectors are being expanded based on customer demand.

Do not imply Snowflake, Salesforce, Oracle, or the full connector catalog is generally available. The default catalog view shows only the two available V1 paths; other entries are clearly Beta, Planned, Requires driver, or Requires agent.

## 7–12 min — Pipeline & Data Quality

1. Open Sales Revenue Quality & Curation.
2. Walk left to right through the 12-node flow without editing it:
   - Raw Sales CSV
   - Select Business Columns
   - Standardize Column Names
   - Convert Revenue Type
   - Filter Invalid Records
   - Handle Missing Regions
   - Normalize Region Names
   - Business Quality Gate
   - Deduplicate Orders
   - Curated Sales Output
   - Regional Revenue Summary
   - Protected Regional Summary
3. Show the retained successful run first. Run live only if useful; the measured run is normally under two seconds locally.
4. Open Data Quality for the raw dataset and show the deterministic issues:
   - 1 missing Order ID
   - 1 negative Revenue
   - 3 non-standard Region values
   - 3 duplicate Order IDs
5. Open Curated Sales Orders and show the 716-row valid output.

Talk track: “VIP keeps the issues visible for governance, rejects invalid records deterministically, standardizes acceptable records, and writes a trusted output for reuse.”

## 12–15 min — Semantic Layer

1. Open Executive Sales Semantic Model.
2. Show business dimensions: Date, Month, Region, City, Product Category, Sales Channel, and Sales Representative.
3. Show Total Revenue, Total Profit, Order Count, Average Order Value, and Profit Margin.
4. Explain that business definitions are created once and reused by dashboards and exports.

Parity anchor values:

- Total Revenue: SAR 659,930.00
- Total Orders: 716
- Western region: SAR 229,500.00
- Data Management: SAR 229,500.00

## 15–20 min — Dashboard

1. Open Executive Sales Performance.
2. Start with the four KPIs: Total Revenue, Total Profit, Total Orders, Profit Margin.
3. Move through Revenue by Region, Revenue Trend by Month, Revenue by Product Category, Profit by Sales Channel, and Regional Performance Detail.
4. Apply one Region filter, then clear it. If time permits, demonstrate Product Category.
5. Explain that dashboard values are queried from the published semantic model, not manually copied.

Avoid editing layout during the customer meeting.

## 20–22 min — Publish & Export

1. Open the published viewer and point out the absence of authoring controls.
2. Show that the Viewer can consume the published dashboard but cannot open Dashboard Studio.
3. Show the fresh PDF and PNG exports.
4. Keep the known-good local PDF ready as the primary fallback if a live export is slow.

The PDF and PNG were visually checked: KPI values are fully visible, month labels are readable, charts render, and all five regional table rows are present.

## 22–24 min — Schedule & Notifications

1. Open Monday Executive Sales Brief.
2. Show weekly frequency, `Asia/Riyadh`, PDF format, saved state, and disabled status.
3. Explain enable/disable and cancel behavior. Do not enable it during the meeting unless the customer specifically asks.
4. Open Notifications and show the three clean recent completed outcomes.

**DO NOT CLICK — SHOW NOTIFICATION STATE ONLY.** `STAGE1-NB-001` means an export-completion notification deep link can navigate to 404.

If asked about email delivery: current demo scheduling triggers platform processing and in-app outcomes. Transactional email productization is a separate upcoming stage; do not promise live Resend-backed delivery.

## 24–25 min — Close

Close on the value chain: connect governed sources, prepare trustworthy data, define reusable metrics, publish decision-ready analytics, and operationalize them with controlled exports and schedules.

Recommended next step: a bounded customer PoC using one approved PostgreSQL source or file dataset, agreed KPI definitions, and the customer’s hosting/security requirements.

## Backup path

If a live action fails:

1. Move immediately to the published Executive Sales Performance dashboard.
2. Use `artifacts/demo-stage2/backup-assets/Executive-Sales-Performance.pdf`.
3. Use the companion PNG if screen rendering is preferable.
4. Show the retained successful pipeline run instead of starting a new one.
5. Continue from the published semantic model and curated dataset.

Do not troubleshoot, expose logs, or repair data while screen sharing.

# Questions to answer carefully

### How many connectors do you support?

VIP V1’s generally available demonstration paths are PostgreSQL and file-based ingestion. The broader catalog represents Beta, planned, driver-dependent, or agent-dependent expansion and must not be quoted as a GA connector count.

### Do you have AI?

AI Studio is a roadmap capability and is not part of the current V1 demonstration scope. Do not navigate to or imply availability of gated AI modules.

### Can you host in Saudi Arabia?

Hosting and residency are designed against the customer’s security, regulatory, and architecture requirements. Do not claim KSA residency before an approved production design and hosting decision exist.

### Is this currently production SaaS?

> The core V1 application is operational and ready for controlled demonstrations and pilots. Production deployment is provisioned based on the customer's hosting and security requirements.

### Can users receive invitations/password resets by email?

Transactional email is not represented as complete in this stage. Do not demo or promise live invitation/password-reset email until the Resend stage is implemented and certified.

### Can you send scheduled dashboard emails now?

The platform scheduling, export processing, history, and in-app outcomes are operational in the demo. Transactional delivery productization is a separate stage, so this demonstration keeps the schedule disabled and does not promise external delivery.

### Are Reports, Automation, Billing, Marketplace, Favorites, or Dashboard Templates available?

Treat them as roadmap or gated capabilities only. They are outside the V1 demo path and must not be demonstrated.

### Is every number on the dashboard trusted?

Yes for this prepared demo. Total Revenue, Total Orders, the leading Region, and the leading Product Category were compared across the curated PostgreSQL output, semantic query, dashboard, and export.
