# VIP Phase 2 Dashboard Export Remediation Report

## Executive Summary

VIP-BUG-003 is fixed and verified. Scatter now has one canonical ordered X/Y
contract from Studio validation through save, publish, query shaping, PDF, PNG,
and the real worker lifecycle. Invalid legacy Scatter remains Scatter, is
reported explicitly, and cannot fall through to Bar.

VIP-BUG-002's historical blank artifact is not reproducible on the retained
evidence. Independent inspection found that the exact retained PDF and PNG
already contain the reported Pivot headers and values. The original dashboard
was cleaned by its fixture and no alternate blank artifact was retained. The
current architectural gap was nevertheless real: Pivot had no matrix contract
and fell through chart shaping before being rendered as a flat table. A
canonical matrix contract and dedicated PDF/PNG Pivot dispatch now preserve
row dimensions, column dimensions, multiple measures, null cells, and stable
known cells. Current persisted and worker-backed Pivot certification passes.

Final classification: **PHASE 2 CONDITIONALLY COMPLETE — ORIGINAL PIVOT FAILURE NOT REPRODUCIBLE, CURRENT EXPORT MATRIX PASSES**.

## Environment

- Branch: `feat/post-core-p1-p2-connectors-scheduling-versions`
- Claude starting SHA: `524055b`
- Claude ending / Sol starting SHA: `3a1445b93b86324c70a9a35f33c55eb2ef161c30`
- Sol implementation/test head before this evidence-only report commit: `6426b35`
- Working tree at start: dirty with documented unrelated user changes; all preserved.
- Services: API, PostgreSQL, Redis, dashboard worker, pipeline worker and ClamAV healthy.
- Frontend: production build and local preview verified.
- Alembic current/head: single `20260808_0021 (head)`; no migration added.

## Review of Claude Commits

### `c37bed8`

Every changed line was reviewed. The PDF and PNG Scatter branches are terminal,
so invalid Scatter cannot reach Bar. No non-Scatter dispatch was changed. The
patch was preserved and extended because it inferred arbitrary numeric columns,
converted nulls to zero, clamped negative domains, and lacked upstream
validation.

### `3a1445b`

The initial harness verified only a small subset and relied on whole-image
non-blank checks. It was replaced by an authoritative 20-widget inventory,
dispatch capture, known semantic values, decoded PDF streams, and per-widget
PNG body inspection.

## VIP-BUG-003 — Scatter

### Root cause

The persisted schema accepted a one-metric Scatter. Live code duplicated that
metric as both axes, while export dispatch could infer unrelated returned
numeric columns and previously fall through to Bar. Null and negative values
also had inconsistent semantics.

### Implementation

- X is the first ordered metric and Y is the second; the first dimension is an
  optional group/label.
- Both axes must be numeric semantic metrics. Null/non-finite pairs are omitted,
  not converted to zero. Negative and zero domains are retained.
- Studio displays missing-X, missing-Y and determinable type errors. Incomplete
  Scatter does not query, save, or publish.
- Backend save/publish and widget query return authoritative
  `DASHBOARD_SCATTER_INVALID` errors.
- Legacy invalid Scatter is loaded without mutation, remains Scatter, and shows
  an explicit invalid state in live/PDF/PNG output.
- PDF and PNG use the configured keys and terminal Scatter dispatch.

### Verification

- Pure contract, component, Studio save/publish and service round-trip tests pass.
- Real governed-tenant browser save/reload/publish passes in Chromium, Firefox and WebKit.
- Real worker JSON contains configured `orders`/`orders_y` points for Region A
  `(333,333)` and Region B `(777,777)`.
- Invalid Scatter PDF/PNG artifacts contain the explicit state and zero chart
  data marks; renderer dispatch capture proves no Bar fallback.

Status: **FIXED + VERIFIED**.

## VIP-BUG-002 — Pivot

### Original evidence recovery

- Retained dashboard: `46156077-2b53-45a6-97b4-3d2151ec7b30`.
- Retained published version: `d0b8dec0-6b96-4655-9c84-9dceee62368d`.
- Retained PDF SHA-256: `140dbdc45791ac79bae6bd249a11ebea495e42286b33022600bce4f140ce8af7`.
- Retained PNG SHA-256: `941bdfab2bd68f4917ec11962081d2d7312dffe627201afae28499e3124715c1`.
- PDF page 4 and the retained PNG visibly contain Category/Orders and
  Dammam/Jeddah/Riyadh values 5/8/12. The structured JSON contains the same rows.
- The original dashboard/version no longer exists because the fixture cleans it.

Therefore the written “blank” observation contradicts the exact retained
artifact set. No distinct blank artifact, worker log, or persisted snapshot was
found, so the original transient condition is not identified.

### Proven current gap and implementation

`dashboards/query.py::_shape()` had KPI and Table cases but no Pivot case, so
Pivot received chart-oriented categories/series shaping. Export then rendered
flat rows. VIP now defines a canonical matrix: preceding dimensions are row
axes, the final dimension is the column axis, metrics expand across column
tuples, stable order is retained, and absent combinations remain null. Live,
PDF and PNG all consume this contract; PDF/PNG use dedicated terminal Pivot
dispatch rather than chart fall-through.

### Verification

- Deterministic matrix: A/Q1=111, A/Q2=222, B/Q1=333, B/Q2=444.
- Additional contract coverage includes multiple measures, nulls and negatives.
- Real save → reload → publish → schedule → job → dashboard worker → storage →
  file record → PDF/PNG/CSV/JSON → email attachment lifecycle passes.
- Stored PDF and PNG independently assert Pivot labels/cells and matrix-header pixels.
- Browser save/reload/publish passes in Chromium, Firefox and WebKit.
- The five browser dashboards created across diagnostic/certification runs were
  enumerated by exact ID and deleted after evidence retention; zero
  `qa-phase2-pivot-scatter-*` dashboards remain.

Status: **NOT REPRODUCIBLE ON CURRENT SHA — ORIGINAL FAILURE CONDITION NOT IDENTIFIED; CURRENT PIVOT MATRIX VERIFIED**.

## Semantic Parity Harness

The authoritative widget inventory is the backend `WidgetType` literal, not a
duplicated document list. The test fails if that inventory diverges from the 20
certified types. Assertions combine:

- immutable definition checks;
- exact chart dispatch capture;
- known categories, series and values;
- decoded PDF content streams;
- single-widget PNG body crops;
- color-area bounds that distinguish Scatter points from Bar-sized marks;
- explicit invalid-state checks;
- real persisted worker artifacts and hashes.

Harness result: 24 passed. The complete table is in
`VIP_PHASE2_EVIDENCE/parity-matrix.md`.

## 20-Widget Worker Lifecycle

Dashboard `4368c167-f516-4eea-be7d-ff44517c704b`, published version
`17807a69-8b29-475d-964e-62ca2d3098a5`, traversed database create, editor save,
editor reload, publish, scheduler, platform job, generic worker, artifact
storage, file record and email attachment. All 20 widgets were visible and all
four formats passed. The fixture dropped its source table and tenant data.

Artifact hashes:

- PDF `4e8bfa8058086b8bee8ba97f353f70a949ec410c96a0670b326032cabaee35b5`
- PNG `8b2ace725cc1ff334437d6feaac549127cebfffde97327b8e4c756d7860b5375`
- CSV `fc8f0b3c2739c387a5a4e4425ce27063dc9446f8a8fa852e44c951a1f2e9dd79`
- JSON `c53f1ab58c5b61bd7a13b10362f7bb1b09f36157721c300a42b872315afe9d4b`

## Filter Parity

- Dashboard filters: PASS; published filter definitions and runtime filter
  state are immutable in JSON/CSV metadata and included in PDF/PNG summaries.
- Widget filters: PASS; saved/reloaded/published definitions retain filters and
  query execution only accepts mapped fields.
- Date filters: PASS; deterministic selected date state is present in the
  semantic harness and canonical export definition.

## Number Formatting

Integer, decimal, percent, currency, negative, zero, null, date text and large
compact values pass deterministic export formatting tests. KPI,
metric-comparison, gauge and progress now aggregate the same rows as live Vue
rendering instead of using only the first export row.

## Security

Owner/admin, viewer/direct ACL, explicit deny, cross-workspace,
cross-organization, anonymous and signed-download checks pass. Tokens bind user,
organization, workspace and export and remain single use. Details are in
`VIP_PHASE2_EVIDENCE/security-results.md`.

## Phase 1 Regression

Chromium, Firefox and WebKit pass the retained Phase 1 test: one dataset list
request on the module, zero per-dataset quality requests, three bounded selector
requests including search/reset, one active create on double-click, recoverable
failure/retry, stable ID, and graph/dataset reload parity.

## Full Regression

- Backend unit: 270 passed.
- Backend integration: 94 passed; 2 excluded known failures are the explicitly
  out-of-scope OpenAPI 255-versus-256 assertions.
- Frontend: 315 passed in 54 files.
- Chromium / Firefox / WebKit Phase 2 flow: PASS / PASS / PASS.
- Ruff check/format: PASS / PASS.
- Changed-module mypy: PASS. Full mypy retains two unrelated Settings call-site errors.
- Frontend scoped lint, typecheck, Prettier and production build: PASS.

## Performance

- Semantic harness: 24 tests in 20.88 seconds.
- Real four-format 20-widget worker lifecycle: 15.17 seconds.
- Browser configured Pivot/Scatter lifecycle: Chromium 6.0s, Firefox 9.6s,
  WebKit 8.9s.
- Phase 1 request bounds remain constant rather than dataset-count dependent.

## Files Changed

Production: dashboard rendering/query/services/contracts; Dashboard Studio,
inspector, service hydration, query hook, VisualRenderer, and Pivot projection.
Tests: backend contracts/renderer/lifecycle/parity, frontend validation/rendering/
service/Studio, Playwright browser lifecycle and local certification runner.
Evidence/report files are under `VIP_PHASE2_EVIDENCE/` and this report.

## Remaining Risks

1. The exact historical blank Pivot condition cannot be reconstructed; retained
   artifacts contradict the original narrative.
2. The excluded OpenAPI contract sweep expects 255 operations while current
   OpenAPI contains 256.
3. Repository-wide ESLint traverses retained generated Playwright trace
   JavaScript under an unrelated untracked evidence directory; scoped source lint passes.
4. Full-project mypy retains two unrelated `Settings()` errors in
   `vip_api/core/config.py:358`; changed production modules pass.

No unrelated issue was remediated.
