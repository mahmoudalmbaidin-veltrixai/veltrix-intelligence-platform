# VIP Stage 4 Enterprise Demo Runbook

## Purpose and architecture

Stage 4 is a repeatable, non-production client demonstration environment layered on the certified VIP V1 stack. It provisions three exact fictional tenants without modifying migrations, RBAC definitions, feature flags, reference data, or unrelated tenants.

| Organization | Flagship workspace | Supporting workspaces | Source mix |
|---|---|---|---|
| Northstar Retail Group | Sales & Commercial | Supply Chain; Executive Management | PostgreSQL, CSV, XLSX |
| Crestline Telecom Services | Network Operations | Field Maintenance; Quality & Performance | PostgreSQL, XLSX, CSV |
| Meridian Facilities Solutions | EHS & Compliance | Maintenance Operations; Service Performance | XLSX, PostgreSQL, CSV |

The scenario contract is `demo-data/stage4/scenarios.json`. Deterministic source files use seed `240824`; flagship sources contain 603 rows, supporting sources contain 261 rows, and each flagship has a five-row regional target lookup. Every source is labeled synthetic and contains controlled missing, invalid, normalized, and duplicate cases for quality demonstrations.

## Safety gates

Provisioning refuses to mutate data unless all of the following are true:

- `VIP_DEMO_ENVIRONMENT=stage4`
- `VIP_STAGE4_BACKUP_VERIFIED=TRUE`
- `-ConfirmNonProduction` is supplied
- the API reports `development` or `test` and readiness is green
- Alembic is at one current head
- a verified custom-format PostgreSQL backup passes `pg_restore --list`
- cleanup targets match only the three configured slugs and exact `vip_demo_*` schemas

The optional legacy cleanup is limited to `veltrix-demo-organization`. No wildcard tenant deletion, database drop, table drop, migration reset, or schema recreation is used.

## Generate, preview, provision, and reset

```powershell
.\scripts\demo-stage4\generate-synthetic-data.ps1

$env:VIP_DEMO_ENVIRONMENT='stage4'
$env:VIP_STAGE4_BACKUP_VERIFIED='TRUE'
$env:VIP_STAGE4_POSTGRES_PASSWORD='<private local value>'

.\scripts\demo-stage4\provision-enterprise-demo.ps1 `
  -Mode DryRun `
  -ConfirmNonProduction `
  -VerifiedBackupPath '<verified custom-format dump>'

.\scripts\demo-stage4\provision-enterprise-demo.ps1 `
  -Mode Apply `
  -ConfirmNonProduction `
  -VerifiedBackupPath '<verified custom-format dump>' `
  -IncludeLegacyStage2Cleanup
```

On the first apply, also provide the platform-operator username/password through the documented environment variables. They are protected separately with Windows DPAPI and are never written to source or logs.

Reset is idempotent and reuses the same gates:

```powershell
.\scripts\demo-stage4\reset-enterprise-demo.ps1 `
  -ConfirmNonProduction `
  -VerifiedBackupPath '<verified custom-format dump>'
```

Run `scripts/demo-stage4/validate-enterprise-demo.ps1` after provisioning. It temporarily enables the named users for authentication checks, tests positive and negative server-side authorization, and restores all 24 accounts to `must_change_password=true` in a `finally` block.

## Access and credential rules

- General demo-user secrets: `%LOCALAPPDATA%\Veltrix\VIP\stage4\demo-user-credentials.dpapi`
- Platform operator secret: `%LOCALAPPDATA%\Veltrix\VIP\stage4\platform-operator.dpapi`
- The stores are separate and outside Git.
- All 24 demo-user passwords are unique, hashed in PostgreSQL, temporary, and marked must-change.
- Use `show-demo-credentials.ps1 -AcknowledgeSensitiveOutput` only in a private, non-recorded session.
- Never copy the Platform Super Admin password into the access register.
- The Excel register under `outputs/vip-stage4/` is Git-ignored and ACL-restricted to the current Windows user and Local System.

## Backup and restoration

The certified baseline is the custom-format PostgreSQL dump and matching runtime-volume snapshot under `artifacts/demo-stage4/backups/`. The recorded dump SHA-256 is in `artifacts/demo-stage4/environment-manifest.json`.

Recovery procedure:

1. Stop the API and worker services.
2. Restore the custom-format dump with `pg_restore --exit-on-error` into an isolated database first.
3. Confirm the recorded migration, organization/workspace/user counts, and core asset counts.
4. Only if replacement is required, restore the local `vip` database and the exact files, pipeline artifacts, dashboard artifacts, email outbox, and Redis snapshots.
5. Restart services and verify `/health`, `/ready`, the single Alembic head, and baseline counts.

Do not expose database credentials in recovery evidence.

## Recommended demonstration

Use `northstar.org.admin` for the Northstar Sales & Commercial flagship and `northstar.commercial.viewer` for the read-only close. Allow 12–15 minutes:

1. Authenticate and enter Sales & Commercial.
2. Open the synthetic raw dataset, profile, and controlled quality results.
3. Reopen the flagship pipeline and explain input, lookup join, filter, conversion, formula, validation, rename, sort, aggregate, output, and file-export nodes.
4. Use the saved successful run and curated output.
5. Open the published semantic model and dashboard.
6. Apply date and region filters; review KPIs, trends, comparisons, and detail table.
7. Show completed PDF and PNG evidence, audit activity, and notifications.
8. Switch to the viewer; confirm published access, no authoring controls, a rejected authoring route, and rejected cross-tenant object access.

If a live action is slow, use the retained successful run and completed export evidence and continue from the published dashboard. Do not edit the pipeline or dashboard during a client meeting.

## V1 boundaries and troubleshooting

Supported in this demo: authentication, tenancy, RBAC, PostgreSQL, CSV/XLSX upload, datasets, profiling, quality, pipelines, semantic models, dashboards, publishing, PDF/PNG export, paused schedules, notifications, audit, and help.

Do not claim AI Studio, Automation, Billing, Marketplace, unsupported connectors, external transactional email delivery, or production hosting. Email schedules remain paused so the demo cannot send externally.

Troubleshooting:

- Gate refusal: verify the two Stage 4 flags, `-ConfirmNonProduction`, backup path, API readiness, and migration head.
- Authentication redirect: reset only the named demo user through the provisioner/validator; never change the auth contract.
- Missing asset: rerun DryRun, then the idempotent reset; inspect `artifacts/demo-stage4/environment-manifest.json`.
- Dashboard/export delay: use the completed flagship export artifact and continue the narrative.
- Suspected tenant leakage: stop immediately and rerun the API/RBAC validator before any demonstration.
