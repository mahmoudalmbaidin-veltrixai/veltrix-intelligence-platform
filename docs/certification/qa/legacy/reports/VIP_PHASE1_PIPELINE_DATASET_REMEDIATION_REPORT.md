# VIP Phase 1 Pipeline/Dataset Remediation Report

## Environment

- Branch: `feat/post-core-p1-p2-connectors-scheduling-versions`
- Starting SHA: `3400ed91dd32e1b61ad290e6a214b7298799dcd9`
- Code/test SHA before this evidence commit: `52002dc`
- Ending SHA: the documentation/evidence commit containing this report; the exact
  immutable SHA is recorded in the final remediation response.
- Initial working tree: not clean. Pre-existing user changes were present in
  semantic, tenancy, admin, login, shared API/query, and tenancy service files,
  plus prior QA artifacts. None was overwritten or included in Phase 1 commits.
- Final working tree: Phase 1 files committed; the same pre-existing user changes
  and artifacts remain intentionally untouched.
- Frontend: `http://localhost:3009`
- Backend/API: `http://localhost:8000`
- PostgreSQL 17.10: healthy / accepting connections.
- Redis 8.0: healthy / `PONG`.
- API, ClamAV, dashboard worker, and pipeline worker: healthy.
- Alembic current: `20260808_0021 (head)`.
- Alembic heads: one (`20260808_0021`). No migration was required.

## Original Reproduction

The populated certification organization contained 241 datasets, of which 165
were active/visible to the workspace editor. Before any production edit:

- A 10-item dataset page required 1 list plus 10 quality-summary requests (11
  dataset hydration requests). The cold backend list response was 1,932.86 ms
  and the payload was 8,797 bytes.
- A 100-item page required 1 list plus 100 quality-summary requests (101 dataset
  hydration requests). The backend list response was 525.43 ms and the payload
  was 85,193 bytes.
- Chromium Dataset route settling took 13,223 ms and recorded 106 API requests,
  including 100 per-dataset quality requests.
- Chromium Pipeline source readiness took 6,839 ms and recorded 107 API requests,
  including 100 per-dataset quality requests.
- The representative first save happened to complete in 2,220 ms, but issued one
  POST followed by one PUT. The first transaction had already created a pipeline
  before the graph transaction began, proving the ghost/duplicate failure window.

Evidence is retained under `VIP_PHASE1_EVIDENCE/before/`.

## Root Cause

`datasetService.liveDatasets()` fetched `/datasets?page_size=100` and immediately
ran a `Promise.all()` containing one `/datasets/{id}/quality` request for every
returned row. Dataset List, Pipeline source selection, semantic selectors, and
other consumers inherited that fan-out. Each quality request repeated dataset
lookup, resource authorization, latest-evaluation lookup, and rule counting.

The backend list query itself was already tenant/workspace scoped, ACL/deny
filtered, stably ordered, and paginated. The N+1 was introduced after its response.
The Pipeline selector then applied search and pagination in the browser to only the
first 100 records, so records beyond that cap were not searchable.

First save had a separate atomicity defect. The client posted metadata, waited for
that committed pipeline, and then put the graph. A failed PUT left a persisted
empty pipeline while the editor still had a `new` route; retrying could POST a
duplicate. Visual button loading did not provide a programmatic single-flight
guard for keyboard/double-click entry paths.

During authorization review, graph validation was also found to tenant-filter a
dataset reference without applying current resource ACL/explicit-deny visibility.
That could allow a source whose permission was removed after selection to be saved.

## Architecture Before

```text
Dataset/selector -> GET /datasets (first 100)
                 -> N x GET /datasets/{id}/quality
                    -> N x dataset guard/evaluation/rule queries

First save -> POST pipeline metadata (commit)
           -> PUT graph (second transaction, may fail)
```

## Architecture After

The dataset endpoint returns a bounded list projection. Its normal authorized page
query outer-joins a tenant/workspace-qualified window subquery containing the
latest completed evaluation score. The service performs three database statements
independent of dataset count: group visibility, authorized count, and one projected
page. Full rules/results remain lazy detail resources.

Dataset List uses a 50-row page. Pipeline source selection uses a 20-row page,
300 ms debounced server search, stable backend ordering, and bounded next/previous
navigation. Connections/files are loaded only when their source type is selected.
Initial dataset/source hydration is one dataset request and zero quality requests.

Pipeline create accepts metadata, canvas, nodes, and edges. It validates current
dataset visibility and graph contracts, inserts the aggregate, records audit, and
commits once. The editor uses an explicit NEW/DIRTY/SAVING/SAVED/SAVE_FAILED/
RECOVERABLE state vocabulary and a shared in-flight promise. A failure leaves the
graph dirty and visible; retry reuses the draft; only a confirmed response assigns
the ID and URL.

```text
Dataset/selector -> GET /datasets?page/page_size/search
                 -> 3 bounded SQL statements; 0 item detail requests

First save -> one POST containing metadata + graph
           -> validation + one atomic transaction
```

This combined projection/lazy-detail design was selected over a separate batch
endpoint because every current list consumer needs only the numeric score, the
existing list is already the authorization boundary, and a batch would add another
round trip without reducing SQL work. It does not download unbounded records.

## Files Changed

Production:

- `apps/api/src/vip_api/datasets/repositories.py`
- `apps/api/src/vip_api/datasets/schemas.py`
- `apps/api/src/vip_api/datasets/services.py`
- `apps/api/src/vip_api/pipelines/schemas.py`
- `apps/api/src/vip_api/pipelines/services.py`
- `apps/api/src/vip_api/pipelines/validation.py`
- `src/modules/datasets/DatasetListView.vue`
- `src/modules/datasets/datasets.service.ts`
- `src/modules/pipelines/SourceConfigurationPanel.vue`
- `src/modules/pipelines/PipelineStudioView.vue`
- `src/modules/pipelines/pipelines.service.ts`

Tests/configuration:

- `apps/api/tests/unit/test_pipelines.py`
- `apps/api/tests/integration/test_pipeline_acl_operator_run.py`
- `apps/api/tests/integration/test_pipeline_persistence.py`
- `apps/api/tests/integration/test_pipeline_republish.py`
- `apps/api/tests/integration/test_pipeline_scheduler.py`
- `apps/api/tests/integration/test_resource_authorization_domains.py`
- `src/modules/datasets/datasets.service.spec.ts`
- `src/modules/pipelines/SourceConfigurationPanel.spec.ts`
- `src/modules/pipelines/pipelines.service.spec.ts`
- `tests/e2e/b8-5-pipeline-source.spec.ts`
- `tests/e2e/phase1-pipeline-dataset-remediation.spec.ts`
- `playwright.phase1.config.ts`

Evidence/documentation:

- `VIP_PHASE1_ROOT_CAUSE.md`
- `VIP_PHASE1_DISCOVERED_ISSUES.md`
- `VIP_PHASE1_EVIDENCE/`
- `VIP_PHASE1_PIPELINE_DATASET_REMEDIATION_REPORT.md`

## Performance Results

| Dataset Count | Requests Before | Requests After | Load Before | Load After | First Save Before | First Save After |
|---:|---:|---:|---:|---:|---:|---:|
| 10 | 11 | 1 | 1,932.86 ms cold API | 51.35 ms service | 2,220 ms* | 2,107 ms* |
| 100 | 101 | 1 | 525.43 ms API | 80.59 ms service | 2,220 ms* | 2,107 ms* |
| ~250 | 101 (only first 100) | 1 | 13,223 ms at 241 tenant / 165 visible | 86.39 ms service | 2,220 ms* | 2,107 ms* |
| 1,000 | Not run pre-fix; first-100 cap made the result incomplete | 1 | Not measured | 1,211.06 ms service | Not measured | Not separately measured |

`*` First-save duration was measured once in the representative 241-dataset tenant,
not repeated for each synthetic count. The controlled scale transaction measures
dataset hydration/query behavior. It inserted 10/100/250/1,000 datasets (with
quality evaluations), returned a bounded 50-row page, and rolled back. Cleanup
verified zero remaining fixture datasets.

Additional real-browser comparison in the representative tenant:

- Dataset route: 13,223 ms / 106 API requests / 100 quality requests before;
  873 ms / 6 total bootstrap+module API requests / 1 dataset request / 0 quality
  requests after.
- Pipeline selector: 6,839 ms / 107 API requests / 100 quality requests before;
  465 ms / 5 total bootstrap+module API requests / 1 dataset request / 0 quality
  requests after.
- First save: POST+PUT before; one POST and no PUT after. Graph persisted after
  reload in both the clean measurement and the failure/retry browser test.
- Current-tenant API after: page 10 = 106.32 ms; page 100 = 129.95 ms.

The stale-bundle measurement is explicitly named
`browser-measurements-stale-bundle.*` and is not used as post-fix evidence.

## Security Verification

- Workspace admin / broad role: authorized list and source save pass.
- Analyst/editor: populated-tenant browser create/select/save/reload passes.
- ACL-only viewer: sees only its granted dataset, receives score 96, and can use it
  as a pipeline source.
- Restricted/no-grant user: hidden from dataset collection.
- Explicit deny: hidden even from a broad-role owner; graph persistence returns
  `PIPELINE_SOURCE_UNAVAILABLE` after access removal.
- Group access: query/edit grant remains effective.
- Cross-workspace/cross-organization: the existing integration contract probes pass
  their isolation assertions; forged tenant headers disclose no foreign IDs.
- Deleted source: nonexistent/deleted dataset reference is rejected before create.
- Suspended user: the existing full contract sweep rejects the still-present
  session on all protected operations. The module later fails only its unrelated
  hard-coded operation-count assertion.

Authorization remains in SQL for both count and page. No tenant, workspace, RBAC,
ACL, ownership, group, explicit-deny, or suspended-user check was bypassed.

## Browser Verification

The focused production-bundle E2E deliberately failed the first POST with 503,
double-clicked Save, verified exactly one request, verified SAVE_FAILED plus retained
graph, retried with another double-click, verified one successful POST, reloaded,
verified the same dataset binding, and archived only its disposable pipeline.

- Chromium: pass (18.8 s)
- Firefox: pass (25.4 s)
- WebKit: pass (25.9 s)
- Total: 3/3 pass (2.1 min including build/server lifecycle)

## Regression Results

- Frontend Vitest: 308/308 pass across 51 files.
- Backend non-integration: 265 pass, 1 expected skip, 71 deselected.
- Focused backend pipeline/security integration after final authorization change:
  10/10 pass; focused atomic/query-count pair 2/2 pass.
- Full backend integration: the final aggregate run had 68 pass, one legacy
  schema fixture rejected because it lacked both dataset ownership and read
  permission, and 2 pre-existing operation-count failures. The fixture was then
  corrected to model ownership and passed 1/1, yielding 69 functionally passing
  integration tests. Baseline and post-fix operation sweeps both expected 255 but
  observed 256; no Phase 1 endpoint was added, removed, or reclassified.
- Backend Ruff check: pass.
- Backend Ruff format: 261 files pass.
- Backend mypy strict: 228 source files pass.
- Frontend source lint (generated evidence excluded): pass.
- Phase 1 measurement-script lint and changed-file formatting: pass.
- Frontend typecheck: pass.
- Production build: pass (541 modules).
- Alembic: one current/head revision; unchanged.

## Failure Scenarios

- Temporary save failure: visible inline error/toast; graph retained; retry passes.
- Dataset list failure: component error and retry test passes; no infinite spinner.
- Dataset deleted/unavailable: backend rejects before persistence.
- Permission removed / explicit deny: backend rejects before persistence.
- Double-click Save: one authoritative request per attempt in three browsers.
- Slow engine response: SAVING state remains deterministic; no duplicate create in
  slower Firefox/WebKit runs.

## Remaining Risks

- Two unrelated full-integration assertions hard-code an obsolete total OpenAPI
  operation count (255 vs current 256). This prevents a completely green platform
  regression suite and therefore prevents an unconditional Phase 1 certification.
- A stale duplicate `vip_b5_sales_demo` fixture has a missing physical preview
  source. It was recorded but not deleted or repaired.
- The 1,000-dataset test is backend/service scale plus bounded-query evidence; the
  real browser tenant contained 241 total datasets. Server pagination means the
  browser payload remains 20/50 items, but a live 1,000-row tenant browser run was
  not created to avoid permanent pollution.
- The unqualified lint script includes old generated trace bundles; source lint is
  green with generated evidence excluded.

## Verdict

VIP-BUG-004 is fixed and verified: quality-summary request fan-out is zero, request
and SQL counts are bounded, list quality remains visible, and permissions hold.

VIP-BUG-001 is functionally fixed and verified across Chromium, Firefox, and WebKit
at representative scale, including failure recovery and duplicate suppression.
Because the pre-existing full integration suite still has two unrelated hard-coded
inventory failures, the controlled release verdict is:

## PHASE 1 CONDITIONALLY COMPLETE — NON-BLOCKING ISSUES REMAIN
