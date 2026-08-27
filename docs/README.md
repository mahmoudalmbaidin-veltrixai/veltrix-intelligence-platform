# VIP documentation

This index separates current operating guidance from historical implementation and QA evidence. Use the current documents below for a new checkout; treat any report that names a commit SHA as evidence for that revision only.

## Start here

- [Architecture overview](architecture/OVERVIEW.md)
- [Deployment architecture](architecture/DEPLOYMENT_ARCHITECTURE.md)
- [Local setup](deployment/LOCAL_SETUP.md)
- [Production deployment contract](deployment/PRODUCTION_DEPLOYMENT.md)
- [Environment variables](deployment/ENVIRONMENT_VARIABLES.md)
- [Operations runbook](operations/RUNBOOK.md)
- [V1 capabilities](product/V1_CAPABILITIES.md)
- [Known limitations](product/KNOWN_LIMITATIONS.md)
- [Development setup](development/DEVELOPMENT_SETUP.md)
- [Testing](development/TESTING.md)
- [Demo environment](demo/DEMO_ENVIRONMENT.md)

## Detailed references

- `backend/` documents domain implementation and security boundaries.
- `architecture/system-workflow/` contains the source diagram, rendered PDF, workflow documentation, and its validation report.
- `qa/`, `reports/`, and `validation/` contain historical evidence. They do not certify later revisions.
- `certification/` contains organized release/productization evidence and repository-readiness reports.

Avoid duplicating environment values or release identifiers in new documents. Link to `.env.example`, the current workflow, or an immutable certification report instead.
