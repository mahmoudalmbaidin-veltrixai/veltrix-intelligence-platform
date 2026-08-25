# VIP Stage 4 Enterprise Demo Environment

This directory provisions three exact, fictional local-development tenants for Northstar Retail Group, Crestline Telecom Services, and Meridian Facilities Solutions. It does not change application logic, migrations, system roles, permission definitions, feature flags, or non-demo tenants.

## Safety contract

The provisioning command refuses to run unless all of these are true:

- `VIP_DEMO_ENVIRONMENT=stage4`
- `VIP_STAGE4_BACKUP_VERIFIED=TRUE`
- `-ConfirmNonProduction` is supplied
- `/api/v1/version` reports `development` or `test`
- health/readiness pass and Alembic is at one head
- a structurally readable verified PostgreSQL backup is supplied
- every cleanup target matches an exact configured slug and exists zero or one time
- every demo schema matches the `vip_demo_*` allowlist

Cleanup never uses a wildcard and never resets the schema. It removes only the three configured Stage 4 tenants and, when requested, the exact Stage 2 tenant `veltrix-demo-organization`. All other organizations and system/reference records are preserved. Demo-source schemas are exact and dedicated: `vip_demo_northstar`, `vip_demo_crestline`, and `vip_demo_meridian`.

## Provisioning

Run a preview first:

```powershell
$env:VIP_DEMO_ENVIRONMENT='stage4'
$env:VIP_STAGE4_BACKUP_VERIFIED='TRUE'
.\scripts\demo-stage4\provision-enterprise-demo.ps1 -Mode DryRun -ConfirmNonProduction -VerifiedBackupPath '<verified .dump>' -IncludeLegacyStage2Cleanup
```

For the first apply, provide the protected platform operator and local demo PostgreSQL password through environment variables. These values are not logged or written to Git. The platform operator is stored separately with Windows DPAPI for subsequent local resets; demo-user passwords are held in a different DPAPI file.

```powershell
$env:VIP_STAGE4_PLATFORM_USERNAME='qa_platform_super_admin'
$env:VIP_STAGE4_PLATFORM_PASSWORD='<private local value>'
$env:VIP_STAGE4_POSTGRES_PASSWORD='<private local value>'
.\scripts\demo-stage4\provision-enterprise-demo.ps1 -Mode Apply -ConfirmNonProduction -VerifiedBackupPath '<verified .dump>' -IncludeLegacyStage2Cleanup
```

Reset uses the same gates and exact targets:

```powershell
.\scripts\demo-stage4\reset-enterprise-demo.ps1 -ConfirmNonProduction -VerifiedBackupPath '<verified .dump>'
```

## Synthetic data model

The fixed seed is `240824`. Each workspace receives a scenario-specific 600-row source with deterministic dates, regions, locations, categories, status, quantity, primary value, cost, score, duration, SLA, risk, and an explicit synthetic-data marker. The Northstar Sales & Commercial flagship contains 603 rows and is the single deliberate "before analysis" data-quality scenario: a blank identifier, negative primary value, missing region, lower-case region value, and controlled duplicates. The other eight sources remain clean. Across the nine raw business tables the environment contains 5,403 records; flagship pipelines also join a five-row regional benchmark dataset.

Source coverage is balanced across PostgreSQL landing, CSV upload, and XLSX upload. XLSX files are canonical seed assets whose first worksheet is ingested through the supported governed file path. Every workspace has a tested PostgreSQL landing connection, raw and curated datasets, profiling, quality rules/evaluation, an executed pipeline, a published semantic model, and a published dashboard.

## Credential handling

- General demo-user credentials: `%LOCALAPPDATA%\Veltrix\VIP\stage4\demo-user-credentials.dpapi`
- Platform operator credential: `%LOCALAPPDATA%\Veltrix\VIP\stage4\platform-operator.dpapi`
- The two stores are separate and outside Git.
- All 24 demo passwords are unique, hashed in PostgreSQL, temporary, and marked must-change.
- Use `show-demo-credentials.ps1 -AcknowledgeSensitiveOutput` only in a private, non-recorded session.
- The Platform Super Admin password is never included in the general workbook.

## Backup and restoration

The Stage 4 baseline consists of the verified PostgreSQL custom-format dump plus the runtime-volume snapshot under `artifacts/demo-stage4/backups`. To restore safely, stop API/workers, restore the dump into the local `vip` database using `pg_restore --exit-on-error`, copy the matching file/export/pipeline/Redis snapshots back to their exact named volumes, restart services, and verify `/health`, `/ready`, the Alembic head, and baseline counts. Always rehearse the restore into an isolated database before replacing the local database.

## Demo sequence and limitations

Recommended flagship: Northstar Sales & Commercial. Follow connect/upload → dataset profile and quality → pipeline graph and successful run → curated output → semantic model → flagship dashboard and filters → published viewer → PDF/PNG → audit/notifications → viewer restriction. Allow 20–25 minutes.

V1 boundaries remain unchanged. Demonstrate authentication, tenancy, RBAC, PostgreSQL, CSV/XLSX ingestion, datasets, data quality, pipelines, semantic models, dashboards, publication, PDF/PNG exports, disabled schedules, notifications, audit, and help. Do not claim AI Studio, Automation, Billing, Marketplace, unsupported connectors, external transactional email delivery, or production hosting.

If a live action fails, use the retained successful pipeline run and completed flagship export artifacts, then continue from the published dashboard. Do not modify a pipeline or dashboard live during a client meeting.
