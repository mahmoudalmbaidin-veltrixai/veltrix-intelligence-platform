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
| 2 | Dashboard wrong-card / export-mismatch **investigation** | `ce2190f` | Investigated — no reproducible defect in current code |
| 3 | Resolve the 10 failing backend tests (hermetic test fixture) | `2bd56e4` | Verified — root-caused + fixed; 132/132 unit pass |
| 4 | Select/Rename schema-validation **integration** test (real DB) | `71e9c43` | Verified — DB-backed integration passing |
| 5 | Select/Rename **worker-transform parity** with validation | `7046433` | Verified at transform level; live source-read/queue parity deferred |
| 6 | Dashboard **lifecycle + version-integrity** regression test (real DB) | `4057352` | Verified — not reproduced; lifecycle protected by regression coverage |
| 7 | Dashboard **frontend widget-identity/reconciliation** guards | `211dee4` | Verified — 13/13 editor tests |

### Dashboard lifecycle regression (Deliverable 2 of the UAT sprint) — DONE
`tests/integration/test_dashboard_lifecycle_integrity.py` drives the real
services through create → save (2 pages, widgets A–D) → reload → edit A →
delete B → add E → duplicate C → reorder widgets → resize/reposition → reorder
pages → save → publish → edit → publish, asserting: stable widget ids after
save/reload; unique duplicate identity; deleted widgets gone (and never in the
snapshot); new widgets present; edited config current; exact widget + page
order; exact layout coordinates; published `DashboardVersion` snapshot bound to
the intended version and containing exactly the intended widgets (the snapshot
the export worker reads); first published version immutable after later edits;
stale `expected_version` → `DASHBOARD_VERSION_CONFLICT`. Frontend guards
(`useDashboardEditor.spec.ts`): duplicate identity + deep-clone, no cross-widget
mutation, and save-response reconciliation of temp `w_` ids to server UUIDs.
**Result: Not reproduced; dashboard lifecycle is now protected by automated
regression coverage.**

## UAT Test-Readiness verdict (this sprint)

**NOT READY FOR UAT — BLOCKERS REMAIN.**

Completed & verified this program: schema-aware Select/Rename frontend + backend
validation, the hermetic test-fixture fix (full unit suite 132/132), a
DB-backed Select/Rename validation integration test, and worker-transform parity
for Select/Rename. These are real, tested, committed.

The sprint's mandatory exit criteria are largely **not met**. Blockers, each with
severity and next action:

| # | Blocker | Sev | Next action |
|---|---------|-----|-------------|
| B1 | Full Select/Rename worker+queue parity with a **live source read** not executed (only the real `transform()` + validation parity is covered) | High | Seed a real source table + connection secret; drive `execute_snapshot` / the pipeline-worker queue; compare worker result values |
| B2 | ~~Dashboard lifecycle regression test~~ **DONE** (`4057352`, `211dee4`) | — | Resolved — not reproduced, protected by regression coverage |
| B3 | Per-widget exact data export (CSV/JSON/XLSX) **not implemented** (no endpoint, no widget action) | High | Implement export using `dashboards.query` + generic jobs/files framework |
| B4 | Dashboard card-editing completeness/reliability **not implemented** this program | High | Audit + extend `WidgetInspector` with typed controls |
| B5 | Dashboard PDF/PNG rendering fidelity + visual-regression fixtures **not done** | High | Add deterministic readiness signals + baseline image diffs |
| B6 | Remaining pipeline nodes (Join/Aggregate/Union/Pivot/Unpivot/Filter/Sort/Formula) schema propagation still **opaque** for join/aggregate/pivot | Medium | Extend `schema_flow` per node |
| B7 | Builder productivity (undo/redo, copy/paste, multi-select, etc.) **not started** | Low | After B2–B4 |
| B8 | Cross-browser E2E (Chrome/Edge/Firefox, 20 journeys), performance runs **not executed** | High | Playwright matrix + seeded perf data |

No global production-ready or UAT-ready verdict is issued: only a subset of the
required modules are complete and validated.

## Priority 0 — Closing validation gaps (this session)

### The 10 previously-failing backend tests — resolved
All 10 failures shared a single root cause: the suite was being executed **inside
the live API container**, which exports `TRUSTED_HOSTS=localhost,127.0.0.1,api`
for the running server. pydantic-settings read that env var, so
`TrustedHostMiddleware` was enabled and rejected the TestClient `testserver`
host with **400** — before requests reached FastAPI validation (expected 422) or
the readiness endpoint. It was a **test-environment/config issue, not a code
regression**. Fix: the `settings` fixture now forces `TRUSTED_HOSTS=["*"]`
(matching the certified CI default, which leaves it unset), making the suite
hermetic. No assertion weakened or skipped.

Exact tests, cause, final status:

| Test | Cause | Final status |
|------|-------|--------------|
| test_application.py::test_validation_error_uses_standard_error | TrustedHost 400 before 422 | Pass |
| test_application.py::test_unexpected_exception_is_safe | TrustedHost 400 | Pass |
| test_application.py::test_unknown_route_uses_standard_error | TrustedHost 400 | Pass |
| test_application.py::test_cors_preflight_allows_frontend_context_and_csrf_headers | TrustedHost 400 | Pass |
| test_application.py::test_health_is_live_without_starting_external_resources | TrustedHost 400 | Pass |
| test_application.py::test_metrics_are_prometheus_compatible_and_can_require_bearer_auth | TrustedHost 400 | Pass |
| test_application.py::test_version_schema | TrustedHost 400 | Pass |
| test_readiness.py::test_ready_when_all_dependencies_are_healthy | /ready 400 via TrustedHost | Pass |
| test_readiness.py::test_not_ready_when_database_is_unavailable | /ready 400 via TrustedHost | Pass |
| test_readiness.py::test_not_ready_when_redis_is_unavailable | /ready 400 via TrustedHost | Pass |

Evidence: full unit run in the raw dev container after the fix →
**`132 passed`** (was 122 passed / 10 failed).

### Select/Rename integration test (real DB)
`tests/integration/test_pipeline_schema_validation.py` seeds a real
ConnectionType→Connection→Dataset→DatasetField chain in `vip_test` and drives
the actual `validate_graph` service path. Verifies real source-schema
resolution, a valid Select→Rename chain, `PIPELINE_COLUMN_NOT_FOUND`,
`PIPELINE_RENAME_COLLISION`, and `PIPELINE_INVALID_COLUMN_NAME`. Run with
`RUN_INTEGRATION_TESTS=1 APP_ENV=test DATABASE_URL=…/vip_test` → **1 passed**.

Deferred within Priority 0: live worker-execution parity (needs a real source
table + worker run) and lineage assertion — validation-level parity is
guaranteed by `schema_flow` mirroring the worker's Select/Rename semantics and
is unit-covered.

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
| Pipeline Select/Rename backend validation | Implemented + integration-validated; worker-execution live parity deferred |
| Backend unit-test environment (10 failures) | Verified production-ready (132/132) |
| Dashboard wrong-card / export-mismatch | Investigated — mechanisms verified correct, no reproducible defect (integration regression test deferred) |
| Per-card data export | Not started |
| Dashboard card editing | Not started |
| Dashboard export rendering fidelity | Not started |
| Remaining pipeline nodes | Not started |
| Builder productivity features | Not started |
