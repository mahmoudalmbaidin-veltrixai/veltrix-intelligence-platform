# Dashboard & Pipeline Studio Enhancement — Progress Report

## 1. Executive summary
Incremental, independently-tested enhancement of Pipeline Studio and Dashboard
Studio. Each slice is committed separately with its own tests, gates, and
verification. This report is updated as slices land. **No global
production-ready verdict is claimed** — status is tracked per area below.

## 2. Accepted baseline and starting commit
- Branch: `enhancement/pipeline-dashboard-studios`
- Certified base: `53ee2f98b6963479593a85b59a3e42ea2929387e` (B0–B8 certified)
- Accepted prior slice: schema-aware Select/Rename **frontend** editors (`eee02dd`)

## 3. Completed slices
| # | Slice | Commit | Status |
|---|-------|--------|--------|
| 0 | Pipeline Select/Rename schema-aware **frontend** editors | `eee02dd` | Implemented, tested, live-verified |
| 1 | Pipeline Select/Rename **backend** schema propagation + structured validation | `f1abea9` | Implemented but further (integration/live) validation required |
| 2 | Dashboard wrong-card / export-mismatch **investigation** | (report) | Investigated — no reproducible defect in current code |

## 4–5. Problems reproduced / root causes
- **Select/Rename had no backend schema-aware validation.** `validate_graph`
  only checked config *shape* and validated columns for *source* nodes; there
  was no intra-graph schema propagation, so a Select/Rename referencing a
  column that does not exist upstream produced no structured error (the worker
  silently returned nulls / dropped columns). Root cause: no propagation pass.
- **Dashboard wrong-card / export-mismatch (Priority 2): investigated, not
  reproducible in the current certified code.** The full lifecycle was traced:
  - `save_editor` (services.py) full-replaces pages/widgets/filters using
    **stable ids** (`widget.id or uuid4()`) under an optimistic `row_version`
    lock — not array-index or positional identity.
  - The frontend serializes widget ids UUID-guarded
    (`UUID.test(widget.id) ? widget.id : undefined`), so only genuinely-new
    widgets get a server-assigned UUID; and after every save/autosave the editor
    is **rebuilt from the server response** (`editor.value = useDashboardEditor(saved)`),
    so ids reconcile to server UUIDs and repeat saves cannot duplicate widgets.
  - Export/delivery reads an **immutable published snapshot** bound to
    `job.dashboard_version_id` filtered to `version_type == "published"` — export
    is version-pinned and cannot silently switch versions.
  - Vue render keys use stable `w.id` / `p.id` (no index keys).
  Conclusion: the widget-identity and export-version-integrity mechanisms are
  correctly implemented; no fix applied (a fabricated change would add risk).
  Deferred: an integration regression test (DB) that asserts save→reload→publish
  →export preserves exact widget set/ids and version binding.

## 6. Frontend changes
- (Slice 0) `NodeColumnSelect.vue`, `NodeRenameMap.vue`, `NodeInspector.vue` —
  schema-aware editors driven by `node.inputSchema`.

## 7. Backend changes
- (Slice 1) New `pipelines/schema_flow.py` (pure propagation + Select/Rename
  validation). `pipelines/validation.py` builds resolved source schemas from
  `DatasetField` and runs propagation inside `validate_graph`.

## 8. API changes
- No endpoint or request/response contract changes. New structured
  `ValidationIssue` codes only, using the existing validation envelope:
  `PIPELINE_COLUMN_NOT_FOUND`, `PIPELINE_RENAME_COLLISION`,
  `PIPELINE_INVALID_COLUMN_NAME` (errors); `PIPELINE_DUPLICATE_COLUMN`,
  `PIPELINE_EMPTY_OUTPUT_SCHEMA` (warnings).

## 9. Database / migration impact
- None. Single Alembic head unchanged.

## 10. Security and tenant isolation
- Propagation uses only tenant-scoped `DatasetField` rows already resolved by
  `validate_graph` under the org/workspace filter. No new data exposure.

## 11. Tests added
- `apps/api/tests/unit/test_pipeline_schema_flow.py` — 16 tests (select, rename,
  propagation, opaque-node blocking, unknown-schema safety).
- Frontend (slice 0): `NodeColumnSelect.spec.ts` (6), `NodeRenameMap.spec.ts` (5).

## 12–13. Commands executed / results
- `ruff check` / `ruff format --check` — clean (touched files).
- `mypy` — clean (touched files).
- Backend: `pytest tests/unit/test_pipeline_schema_flow.py tests/unit/test_pipelines.py` → **24 passed**.
- Full backend unit run: 122 passed / 10 failed — the 10 are pre-existing
  environmental failures in `test_application.py` + `test_readiness.py`
  (TestClient host-validation + dependency-health inside the dev container),
  unrelated to pipelines.
- Frontend (slice 0): typecheck, lint, 11 component tests, 203-test suite, build — all green.

## 14. Live verification evidence
- Slice 0: verified in the running app — adding a Select Columns node mounts the
  new schema-aware editor (prompts to connect an upstream node), no console errors.
- Slice 1: backend-validation slice verified via automated unit tests; full
  integration/live validation with a real dataset source is a deferred item.

## 15. Commit SHAs
- `eee02dd` — schema-aware Select/Rename frontend editors
- `f1abea9` — schema-aware Select/Rename backend validation

## 16. Deferred items
- Integration test of `validate_graph` propagation against a real seeded dataset
  (needs `RUN_INTEGRATION_TESTS=1` + DB).
- Preview-execution parity assertion for Select/Rename.

## 17. Known risks
- Propagation models a subset of node output schemas precisely; opaque nodes
  (join/aggregate/pivot) intentionally yield unknown downstream schema, so
  Select/Rename immediately downstream of those are not schema-validated.

## 18. Production-readiness status by area
| Area | Status |
|------|--------|
| Pipeline Select/Rename frontend | Implemented but further validation required |
| Pipeline Select/Rename backend validation | Implemented but further validation required |
| Dashboard wrong-card / export-mismatch | Investigated — mechanisms verified correct, no reproducible defect (integration regression test deferred) |
| Per-card data export | Not started |
| Dashboard card editing | Not started |
| Dashboard export rendering fidelity | Not started |
| Remaining pipeline nodes | Not started |
| Builder productivity features | Not started |
