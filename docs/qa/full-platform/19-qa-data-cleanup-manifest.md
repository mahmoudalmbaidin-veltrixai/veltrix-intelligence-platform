# QA Data Cleanup Manifest

Final cleanup was intentionally not executed because the QA estate is retained for manual UAT. Cleanup must be ID-scoped.

Primary retained roots:

- QA A organization `17a4e171-ced9-40cf-883d-e42ff2dc4267`
- QA B organization `e1520ab1-01e5-4623-91d2-1e6b4cb70696`
- browser-created organizations `0e350eca-90d5-46ea-88a4-7f7e958ca6b6` and `0ae1abab-07c3-443b-bc42-6a322e8cb4be`
- four connection IDs in `qa-resource-manifest.json`
- 38 exact user IDs in `qa-users.json`

An older pre-existing `E2E Org A` and `E2E Client 615398` are protected and excluded because they pre-date this run.

Before cleanup, expand descendants from the exact organization/user/resource IDs into a fresh manifest containing table, record ID, tenant/workspace, storage key, job/Redis references, and reason. Delete in dependency order described in `04-safe-cleanup-plan.md`. Preserve audit rows or use the product's approved retention mechanism. Do not use `LIKE 'QA_%'` as the deletion criterion.

The authoritative local runtime manifests are under ignored `artifacts/qa/full-platform/`; they include resource IDs, connection results, partial-seed cleanup evidence, backups, and encrypted credentials.
