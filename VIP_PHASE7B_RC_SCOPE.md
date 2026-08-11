# VIP Phase 7B — Release Candidate Scope Freeze

## Included

- All commits already on `feat/post-core-p1-p2-connectors-scheduling-versions` through Phase 7A Data Quality performance (`4b8aacf` and ancestors): Pipeline/Dataset, Dashboard export parity, Security headers, Scheduler audit ordering, XLSX ingestion, API operation manifest, Dataset versions, WebKit tooltip, PDF document language, Quality aggregate APIs.
- Outstanding workspace-administration remediation: soft-delete workspace, make-default, last-active/default guards, RBAC tests, admin UI.
- Mutation query-cache invalidation so lists/switchers refresh without re-login.
- Login brand-panel presentational polish (no authentication semantics change).
- Semantic audit snapshot `Decimal` JSON serialization fix.
- Phase 7B static-gate hardening only: Ruff/format, mypy typing correctness, Prettier, ESLint ignore scope for evidence artifacts, `types-openpyxl` for typed XLSX imports.

## Excluded

- Local credentials workbook (`VIP Credentials.xlsx`) and any secret-bearing env files.
- Generated certification evidence trees (`VIP_*_EVIDENCE`, `VIP_TEST_EVIDENCE`, recert workbooks, `outputs/`, `reports/`).
- Uncommitted `docs/qa/platform-capability-and-uat/` inventory generated against a different historical SHA.
- Unrelated unfinished product work not present as intentional RC source.

## Known documented limitations (non-blocking for RC hygiene)

- Pivot long-label PDF/PNG presentation edge cases.
- PDF structural tagging / full accessibility certification beyond document language declaration.
- Legacy certification-data cleanup hygiene outside deterministic fixture registry.
- Production TLS/edge termination, external SMTP, backup/restore/DR, and incomplete preview modules.

These limitations are documented product/ops gaps; they do not excuse static-gate or cleanliness failures.
