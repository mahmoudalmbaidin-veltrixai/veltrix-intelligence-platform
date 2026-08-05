# Protected Data Register

Protected baseline invariants were captured before testing and rechecked after the only cleanup action:

- 15 pre-existing users and 13 pre-existing organizations remained.
- 126 permission definitions and all 7 system roles remained.
- Alembic stayed at the single head `20260803_0019`.
- Existing audit events, encryption metadata, connection secrets, feature flags, entitlements, quotas, storage objects, Redis data, and unknown B5/B8.5 tables were not removed.
- No broad SQL delete, truncate, schema drop, database recreation, volume deletion, or storage-file deletion was executed.

Machine-readable baseline: `protected-records.json`. Backups are under ignored local path `artifacts/qa/full-platform/backups/`.
