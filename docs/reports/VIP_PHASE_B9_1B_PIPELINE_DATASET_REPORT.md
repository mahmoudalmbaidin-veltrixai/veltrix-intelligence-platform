# VIP Phase B9.1B — Pipeline and Dataset Completion Report

**Date:** 2026-08-03  
**Branch:** `phase-b9/pipeline-dataset-completion`  
**Base:** `frontend/enterprise-ui-enhancement` @ `27fd8fff4fbadb8082a9a4550b499e73b2372b95`  
**Rollback tag (unchanged):** `pre-phase-b9-enterprise-baseline` → `6254d60d445f9b3849fa88d5151bd56cd770f339`

## Summary

B9.1B completes Pipeline resource-level run authorization, Pipeline Studio read-only/operator surfaces, artifact list/download UX, Dataset Studio live tabs (no mock rows), and Dataset certify/revoke with certify-gated API + audit.

## Pipeline

### Authorization (M1)
- `POST …/runs` and `POST …/retry` now use `pipeline_capability` (feature/entitlement only).
- Operator+ is enforced by the centralized resource evaluator inside `create_run` / `retry_run` / `cancel_run`.
- Monthly `pipeline_runs.monthly` quota is consumed in the service layer (orthogonal to ACL).
- Worker claim re-auth uses `require_pipeline_access(..., "operator")` instead of broad `pipeline.execute`.
- Formula language endpoints use `pipeline_capability` so ACL authors are not blocked by broad `pipeline.read`.

**Policy (unchanged ladder):** Viewer < Operator < Developer < Owner. Developer includes operator (run) because the ladder is inclusive — documented consistently backend/frontend/tests.

### Runtime / artifacts (M3)
- Studio Results tab lists artifacts (node, type, size, created, expires) with signed download.
- Runs view gates Retry/Cancel with `canRun` and surfaces the same artifact download flow.
- Failure reason shown when `safe_error_message` is present; row counts show unavailable when null.

### Studio usability (M2)
- Palette / Canvas / Inspector / keyboard mutations honor `canEdit`.
- Undo/Redo disabled without edit access.
- Viewer/operator can inspect; only Developer+ mutates the graph locally.

## Dataset

### Live tabs (M4)
- Access → `accessService.listResourceAccess`
- Lineage → `GET /datasets/{id}/lineage`
- Activity → new `GET /datasets/{id}/activity` (query-gated audit feed)
- Versions → honest unavailable state (no history API; concurrency version only)

### Certification (M5)
- Migration `20260803_0019`: `certified_by_user_id`, `certified_at`, `certification_note`
- `POST /datasets/{id}/certify` and `POST /datasets/{id}/certification/revoke` (certify-gated)
- `certification_status` removed from `DatasetUpdate` (edit cannot certify)
- Audit: `dataset.certified`, `dataset.certification.revoked`
- Overview UI: status/by/at/note + Certify/Revoke gated by `resourceCan(..., 'certify')`

### Preview / quality / permissions
- Preview gated in UI by query access; API remains authoritative.
- Quality tab continues to use live rules; create/run remain in Data Quality workspace (certify-gated backend).
- Query vs Export and Edit vs Certify remain distinct ladder levels.

## Tests added
| Suite | Addition |
|---|---|
| Backend unit | `test_dataset_certification_schema.py` (+2) → **216** total |
| Backend integration | `test_dataset_certification.py`, `test_pipeline_acl_operator_run.py` (+2) → **56** total |
| Frontend unit | `NodePalette.spec.ts`, `datasetLiveTabs.spec.ts` (+4) → **279** total |
| Chromium | `tests/e2e/b9-1b-pipeline-dataset.spec.ts` (2 focused live checks) |

## Validation (exact totals)
| Gate | Result |
|---|---|
| Backend `ruff check .` | passed |
| Backend `ruff format --check` | passed (240 files) |
| Backend `mypy src tests` | passed (215 files) |
| Backend unit | **216 passed** |
| Integration run 1 (fresh `vip_test`) | **56 passed** |
| Integration run 2 | **56 passed** |
| Alembic | single head `20260803_0019`, `alembic check` clean |
| Frontend typecheck / lint / format:check | passed |
| Frontend unit | **279 passed** |
| Frontend build | passed |
| Focused Chromium B9.1B (`chrome-desktop`) | **2 passed** |
| Full chrome-desktop suite | Not certified green in this environment — authenticated fixtures expect org `Organization Alpha` while the live governance demo tenant is `Governance Demo` (pre-existing fixture/env mismatch; not introduced by B9.1B). Focused B9.1B + unit/integration gates are the authoritative slice evidence. |
| Accessibility suite | Same fixture/org mismatch as above |

## Database
Additive migration only: `20260803_0019_dataset_certification.py`. Rollback tag untouched.

## Out of scope (not started)
Connection Studio completion, Semantic Studio completion, Audit finalization, placeholder gating, B9.2, Reports, AI Studio, Billing, Marketplace.
