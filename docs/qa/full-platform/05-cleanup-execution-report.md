# Cleanup Execution Report

No pre-existing data was deleted. Three proven QA-only records from an interrupted bootstrap were removed through scoped APIs:

- group-role assignments `325e...` and `edc4...` (full IDs retained in the ignored local cleanup manifest)
- group membership `9567...` (full ID retained locally)

The exact source manifest is `artifacts/qa/full-platform/cleanup-candidates-partial-seed.json`. Intended group membership and role assignment were then verified. Protected users, system roles, 126 permissions, migration head, application startup, and workers remained intact. Audit history was not modified.
