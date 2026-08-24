# VIP Stage 4 Enterprise Demo Certification

## Verdict

**A — ENTERPRISE DEMO ENVIRONMENT CERTIFIED**

Certified on 2026-08-24 for the local `development` environment. The starting branch was `feat/vip-productization-p1` at `670a4ca879a22f5c413ff7eed3b965b83c351bc0`. The database was at the single Alembic head `20260808_0025`.

## Recovery and cleanup evidence

- Verified custom-format dump: `artifacts/demo-stage4/backups/vip-stage4-baseline-20260824-153257.dump`
- SHA-256: `029B308C020D32C37D772E2EEA2752F738CD3E213F9ACE9549F581339F689E59`
- Isolated restore: passed; migration and baseline counts matched; isolated database removed afterward.
- Runtime volumes: snapshotted under `artifacts/demo-stage4/backups/runtime-volumes-20260824-153409/`.
- Removed tenant: `veltrix-demo-organization` (`af0c6248-0f0d-4f12-af09-2d3819369f0f`) and its exact `vip_demo_sales` data schema.
- Preserved: all other tenants, system/reference data, RBAC definitions, migrations, feature configuration, audit infrastructure, settings, platform administrator, and unrelated working-tree changes.

## Runtime inventory

| Area | Certified result |
|---|---:|
| Fictional organizations | 3 |
| Workspaces | 9 (3 per organization) |
| Demo users | 24 (8 per organization) |
| Source coverage | PostgreSQL, CSV, XLSX in each organization |
| Datasets | 21 |
| Pipelines | 9 succeeded / 0 failed |
| Semantic models | 9 published |
| Dashboards | 9 published |
| Flagship exports | 3 PDF + 3 PNG completed |
| Safe schedules | 3 paused |
| Quality evaluations | 9 controlled negative-fixture evaluations |

All 24 demo users have password hashes and `must_change_password=true`. The platform operator has zero active Stage 4 tenant memberships (the three bootstrap memberships are marked removed), and its password is excluded from the general register.

## Security and functional evidence

The API validator recorded 22/22 passed checks across all three organizations: admin authentication, viewer published access, viewer pipeline creation rejection (403), viewer export rejection (403), editor membership administration rejection (403), unauthorized workspace dataset rejection (404), cross-organization dashboard rejection (404), and the all-user password hash/must-change check.

The final Playwright run used retries disabled and passed 6/6 tests in 55.0 seconds:

- Chromium: admin journey passed; viewer/read-only/direct-route/isolation journey passed.
- Firefox: admin journey passed; viewer/read-only/direct-route/isolation journey passed.
- WebKit: admin journey passed; viewer/read-only/direct-route/isolation journey passed.
- Artifact credential scan: zero findings.

Quality gates:

| Gate | Result | Duration |
|---|---|---:|
| Frontend ESLint, Prettier, typecheck, production build | Passed | 35.81s |
| Frontend Vitest | 425 passed / 0 failed | 29.36s |
| Backend Ruff, format, mypy, non-integration pytest | 303 passed / 0 failed / 25 skipped | 29.38s |
| Backend migration + integration pytest | 104 passed / 0 failed | 168.88s |
| Stage 4 contract + artifact sanitizer unit tests | 4 passed / 0 failed | 6.69s |

## Register and repeatability

The ignored local workbook is `outputs/vip-stage4/VIP_Enterprise_Demo_Environment_and_User_Access_Register.xlsx`. It contains ten requested sheets, 24 approved temporary demo-user credentials, no Platform Super Admin credential, eight formulas with zero formula-error cells, ten filterable tables, five data-validation blocks, conditional status formatting, and frozen header panes on every sheet. Its final SHA-256 is recorded during handoff.

Repeatable generation, guarded provisioning, reset, validation, and private credential viewing live under `scripts/demo-stage4/`. The scenario contract and deterministic seed assets live under `demo-data/stage4/`.

## Limitations

- Demo limitation: schedules are configured but paused; no external message is sent.
- Existing V1 boundary: external transactional email delivery and unsupported connectors are not demonstrated.
- Product defect: none open from Stage 4 certification.
- Future enhancement: automate workbook creation inside a supported cross-platform artifact runtime and add a friendlier UI redirect after tenant-scoped dashboard 404 responses.

Open defects: P0 0, P1 0, P2 0.
