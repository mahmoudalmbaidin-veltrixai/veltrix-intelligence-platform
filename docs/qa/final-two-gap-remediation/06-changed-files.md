# Changed Files and Classification

## Source and tests

- `apps/api/src/vip_api/api/operation_coverage.py` — automated certification framework;
  executable dimension rules and evidence validation.
- `apps/api/tests/integration/test_production_api_contract_sweep.py` — real personas,
  owned/cross-tenant resources, ACL sequences, suspended sessions, payload boundaries,
  and exact operation observations.
- `apps/api/tests/integration/test_dashboard_delivery_scheduler.py` — real persisted
  PostgreSQL-backed 20-widget four-format scheduler/worker/storage/email lifecycle.
- `apps/api/tests/unit/test_operation_coverage.py` — regression tests for classification
  honesty and rejection of unsupported or missing evidence.

## Sanitized certification evidence

All files below `docs/qa/final-two-gap-remediation/` are QA reports or selected
sanitized machine/visual evidence suitable for repository history. The PDF, PNG, CSV,
and JSON artifacts are outputs of the real lifecycle integration test.

No product feature file, migration, dependency lock, environment file, credential,
browser trace, database backup, storage volume, or unrelated working-tree change is
included.
