# VIP Enterprise Permissions & Access Control — Implementation Report

**Branch:** `enhancement/pipeline-dashboard-studios`
**Base SHA:** `2590248ba51cd0d8da37c000efaed754bac070df`
**Working tree:** uncommitted (per instruction — do not commit/push)
**Environment:** Docker Compose (postgres, redis, clamav, dashboard-worker, pipeline-worker, mysql, api) healthy; API `http://localhost:8000` healthy/ready; frontend `http://localhost:3009` (HTTP 200); Alembic head `20260728_0018` (single head; `alembic check` → "No new upgrade operations detected").

This report covers the full enterprise permissions enhancement delivered across two slices, and is the index for the companion Database, API, Security, Test and UAT reports.

---

## 1. Architecture overview

Authorization is layered and single-sourced:

1. **Tenant resolution** — `X-Organization-ID` (required) + optional `X-Workspace-ID` → `TenantContext`.
2. **RBAC / governance** — `AuthorizationContext` (role permissions, entitlements, feature flags, quotas) enforced at routes via `require_governance(...)`.
3. **Resource ACL** — a single evaluator, `evaluate_resource_access` (`governance/resource_access.py`), wired to persistence by `governance/resource_access_service.py`. There is **exactly one** precedence implementation; every caller resolves through `check_access` / `effective_access` / `access_overlay` / `enforce_resource_guard`.

### Authoritative precedence (Phase C — resolved)

```
suspended/deleted subject
  > explicit resource deny (non-expired)
    > platform super-admin
      > archived workspace / resource
        > ownership
          > resource allow grant (ACL)
            > direct + group role grants (RBAC/custom)
              > default deny
```

The earlier contradiction (super-admin vs. explicit deny) is resolved **fail-closed**: an explicit deny overrides super-admin and ownership. This is enforced in `evaluate_resource_access` and locked by `tests/unit/test_authorization_precedence.py`.

---

## 2. What was delivered

### Custom roles (Phase B / K / O)
- `roles` table extended (tenant columns, slug, status, editable flag, audit + soft-delete + `row_version`); new `user_role_assignments`, `group_role_assignments` (migration `20260728_0018`).
- `role_service.py` — create/read/update/clone/archive/restore/delete/list/search with duplicate-name, scope, and **privilege-ceiling** validation (an admin cannot grant permissions they do not hold unless super-admin). System roles are protected.
- `role_assignment_service.py` — user/group assign, unassign, list, and **bulk** assignment with per-item success/failure.
- Custom + group role permissions are merged into `AuthorizationContext` in `resolve_authorization_context`, so every existing route guard honours them automatically (no duplicate evaluator).
- API: `role_routes.py` (`/permission-catalog`, `/roles*`, `/roles/{id}/assignments*`). Frontend: `RolesView.vue` (categorized permission matrix, search, select-all/clear, clone, assignments dialog).

### Groups & resource ACLs (Slice B, verified in Phase A)
- `groups`, `group_memberships`, `resource_access_entries` with allow/deny, expiration, and group inheritance.
- Generic APIs: grant/revoke/list/effective/simulate for all registered resource types; principal search; resource-type + resource **search** (`search_resources`).
- Frontend: `GroupsView.vue`, `AccessControlView.vue`, reusable `ResourceShareDialog.vue`, `ResourcePicker.vue`, and enhanced permission inspector (Phase L).

### Backend enforcement by resource (Phases D–H)
A shared, additive guard `resource_access_service.enforce_resource_guard(...)` enforces **explicit deny + expiration** as defense-in-depth on top of the route RBAC gate — it never loosens existing access. Wired into service choke points:

| Resource | Levels | Wired operations (action level) |
|----------|--------|-------------------------------|
| Pipeline | viewer/operator/developer/owner | read (viewer), run (operator), cancel/retry (operator), save/publish/restore (developer), archive (owner) |
| Dataset | query/export/edit/certify/manage | get (query), update/field (edit), quality rule/evaluation (certify), archive (manage) |
| Connection | use/test/edit/rotate/manage | get (use), test (test), update (edit), rotate credentials (rotate), archive (manage) |
| Semantic model | view/query/edit/manage | read (view), edit (edit), publish/archive (manage) |
| Dashboard | view/interact/edit/manage | full `access_overlay` (allow + deny + ownership) in `dashboards/services.py::_access` |
| Report | view/interact/edit/manage | **registered only** — no physical report table exists (see Known Limitations) |

Dashboards retain the richer full overlay (they grant *new* access via loose route gates). For pipeline/dataset/connection/semantic the RBAC route gate remains the coarse allow-gate and the ACL guard adds fail-closed deny + expiration; brand-new grant-only elevation for those types is available through the generic access APIs and inspector but is not wired to loosen their strict route gates (documented limitation).

### Studio integrations (Phase I + D–G frontend)
New reusable `ResourceShareButton.vue` wraps the level lookup + manage check + `ResourceShareDialog`. Wired into Pipeline Studio, Dataset detail, Connection detail, Semantic builder. Dashboards already expose sharing via `DashboardShareDialog` in studio + viewer.

### Audit (Phase N)
Every permissions mutation records a persistent governance audit event via `record_audit` (actor, tenant, workspace, resource, action, before/after metadata, correlation id): group/membership changes, custom-role changes, role assignments, ACL grants/denies, revocations, and manage-denied attempts. Surfaced through the existing Activity/Audit area.

### Caching (Phase M)
`AUTHORIZATION_CACHE_ENABLED` remains **disabled** (default `False`). Per-request context caching (`request.state.authorization_context`) already removes redundant resolution within a request. Distributed caching is intentionally deferred — see Security report §Caching for the fail-closed rationale.

---

## 3. Quality gates (this slice)

| Gate | Result |
|------|--------|
| `ruff check src tests` | pass |
| `ruff format --check` | 198 files formatted |
| `mypy src tests` | Success: no issues in 198 files |
| `pytest -m "not integration"` | **180 passed** |
| `alembic check` (dev DB) | No new upgrade operations |
| `pytest -m integration` (vip_test) | **31 passed** (run twice, stable) |
| `npm run typecheck` | pass |
| `npm run lint` | pass |
| `npm run format:check` | all files pass |
| `npm run test` | **218 passed** (38 files) |
| `npm run build` | built successfully |

See the Test report for the full breakdown.

---

## 4. Verdict

See the final chat response for the overall verdict and Known Limitations. This enhancement is functionally complete and green across static, unit, integration, and build gates, with the honest exceptions documented in each report (report backend absence, non-dashboard grant-only elevation, distributed caching, and live browser persona runs).

---

## Pipeline ACL Grant Elevation (slice — core delivered)

**Problem.** Pipeline routes hard-gated on the broad `pipeline.read` workspace
permission (`gate("pipeline.read")`), so a tenant member holding only a resource
ACL grant was rejected *before* the centralized evaluator ran. `_pipeline`
already layered deny-only `enforce_resource_guard`, but that never elevates.

**Change (additive, no second engine).**
- `pipelines/routes.py`: `show` (GET `/{id}`) and `index` (list) now use
  `pipeline_capability = require_capability("pipeline_studio","pipeline_studio")`
  — feature/entitlement gate with **no** `pipeline.read` requirement. `show`
  then calls the new resource-aware guard.
- `pipelines/services.py`:
  - `require_pipeline_access(db, ctx, pipeline_id, level)` runs the shared
    `resource_access_service.check_access` (role ∪ direct/group ACL ∪ ownership,
    minus deny/expired) and returns a non-disclosing 404 when denied.
  - `list_pipelines` is visibility-filtered: broad-role users see all
    (unchanged); otherwise the query restricts to owned ∪ non-expired ACL-allowed
    (direct or group) resource ids, minus viewer-level denies — filtered in SQL
    (no N+1, no fetch-all-then-authorize).
- Precedence is the single centralized model (suspended → deny → super-admin →
  archived → owner → grant → default deny); no pipeline-specific precedence.
- Create / workspace-admin operations retain their broad RBAC gates.

**Verified (integration, vip_test):** `test_pipeline_acl_elevation.py` — a viewer
with **no** `pipeline.read` opens the shared pipeline (elevation), cannot open
another (404), cannot reach `developer` (404), the list shows only the shared
pipeline, the owner still sees all, an explicit deny overrides the allow and
hides it from the list, and an expired grant is ignored. Gates: `ruff check` ✓,
`ruff format --check` ✓ (224 files), `mypy src tests` ✓ (200 files), backend
unit **180** (route-policy still complete), new integration test **1 passed**.

**Remaining for the full Pipeline slice (not yet done):** elevate the mutating/
execution routes (run/retry/cancel/update/publish/versions/logs/artifacts) to
`pipeline_capability` + `require_pipeline_access(<level>)` for full
Operator/Developer/Owner action enforcement via ACL; Pipeline Studio frontend
role-state rendering + sharing-button visibility; focused live Chromium
Playwright persona test; frontend component tests. Note: the full integration
run showed 2 `test_tenancy` failures that pass in isolation — a pre-existing
`vip_test` cross-test ordering/state artifact, unrelated to this change.

---

## Pipeline ACL — Complete Action Matrix + Live UAT (slice completed)

The remaining items above are now delivered. Pipeline authorization is enforced
for **every** resource-bound action through the single centralized evaluator; a
Pipeline ACL authorizes exactly the requested capability without any unrelated
broad workspace permission, while creation and workspace-wide administration keep
their broad RBAC gates.

**Action → level (service-enforced via `_pipeline`/`_run` → `check_access`):**

| Level | Actions |
|-------|---------|
| Viewer | open, metadata, graph read, versions list, runs list, run detail, logs, artifacts |
| Operator | Viewer + create run, cancel run, retry run |
| Developer | Viewer + save editor, validate, publish, restore version |
| Owner | all + archive/delete; sharing management (Owner **or** tenant admin only) |

**Backend changes (additive, one engine).**
- `pipelines/routes.py`: every resource-bound route now uses
  `pipeline_capability` (feature/entitlement, no broad permission). Create keeps
  `pipeline.create` (+quota); run-create and retry keep `pipeline.execute` /
  `pipeline.runs.retry` (+`pipeline_runs.monthly` quota) because quota consumption
  is only wired at those two gates (documented; ACL still deny/expiry-enforced via
  the service `_run` guard).
- `pipelines/services.py`: `_pipeline`/`_run` call the new `_authorize_pipeline`
  (full `check_access`): **EXPLICIT_DENY → 403 `RESOURCE_ACCESS_DENIED`**, any
  other denial → non-disclosing **404**. Each service function passes its action
  level (save/validate/publish/restore → developer; archive → owner; create/
  cancel/retry run → operator; reads → viewer).
- `get_editor`/`create_pipeline` responses now carry an **`access`** block
  (`PipelineAccess`) computed by `pipeline_access()` → `effective_access` (the same
  evaluator), so the client renders viewer/operator/developer/owner (and denied)
  states from the enforced decision. `show` passes the caller's platform-admin flag.
- Sharing management is unchanged and already correct: `_assert_can_manage` →
  `can_manage_resource` = platform-admin **or** actual owner **or**
  `pipeline.update` manage permission. A Developer/Operator/Viewer whose access is
  only a resource ACL grant is rejected `403 RESOURCE_MANAGE_DENIED`.

**Frontend (`src/`).**
- `usePipelinePermissions` derives `canView/canRun/canEdit/canManage` + `denied` +
  `level` from the backend `access` block (fallback to broad permissions only for
  brand-new drafts / offline mock). Pipeline Studio disables Validate/Save/Publish
  (developer), Run/Cancel/Retry (operator), hides Share unless owner, shows a
  read-only ribbon and an access-level badge, and routes to `/forbidden` when the
  backend denies the load.
- Router/nav: `/pipelines`, `/pipelines/:id`, `/pipelines/:id/runs` gate on the
  `pipeline_studio` **entitlement** (not `pipeline.read`), so an ACL-only user
  reaches their shared pipelines; the list is backend visibility-filtered.

**Verification.**
- Backend static: `ruff check .` ✓, `ruff format --check .` ✓ (228 files),
  `mypy src tests` ✓ (203 files).
- Backend tests (container, fresh `vip_test`, `alembic upgrade head` + `alembic
  check` clean): **unit 196**, **integration 34 ×2** (both green). The earlier
  2 `test_tenancy` failures were the stale nested `/app/tests/tests` duplication
  artifact; with a clean flattened tree they do not recur.
- New tests: integration `test_pipeline_action_matrix.py` (full matrix, 30+
  assertions: level bands, group elevation, revocation, deny, expiry, collection
  visibility, cross-tenant inertness), `test_pipeline_sharing_authorization.py`
  (owner/admin allowed; developer/viewer ACL grantees rejected); unit
  `test_pipeline_authorization_mapping.py` (16, action↔level + precedence);
  `test_pipeline_persistence.py` seeds `OrganizationMembership` (the invariant the
  now-enforcing load path requires).
- Frontend: `typecheck`/`lint`/`format:check` ✓, tests **232** (was 218; +14 in
  `usePipelinePermissions.spec.ts`), `build` ✓.
- **Live Chromium** (`VITE_API_MODE=live`, API :8000, FE :3009), governance-demo
  personas + seeded ACL matrix:
  - Owner (admin) → Share visible, all authoring/run enabled.
  - Developer ACL (editor) → developer badge, authoring/run enabled, **no Share**.
  - Viewer ACL (viewer) → viewer badge, **READ-ONLY**, Validate/Save/Run/Publish
    disabled, name field read-only, no Share.
  - **Elevation**: `restricted` (no `pipeline.read` role) opened an elevation
    pipeline via a **developer ACL** → fully editable (proves grant-only
    elevation now works for pipelines, not just dashboards).
  - **Explicit deny**: `restricted` on a deny pipeline → **GET returned HTTP 403**
    (server-enforced `RESOURCE_ACCESS_DENIED`) → routed to `/forbidden`.
  - **Collection**: `restricted`'s list showed only the elevation pipeline; the
    no-grant and deny pipelines were hidden (no leaked names).
  - Chromium only was exercised; Firefox/WebKit were not run.

---

## Dataset / Connection / Semantic Resource Authorization (final slice — complete)

The last three protected domains now use the **same centralized architecture** as
Pipeline. No second engine, no duplicated precedence: every decision resolves
through `resource_access_service.check_access` / `effective_access` (evaluator
precedence: suspended → explicit deny → super-admin → archived workspace →
ownership → grant/role → default deny).

### Shared, centralized additions (no per-domain duplication)
`apps/api/src/vip_api/governance/resource_access_service.py`:
- `authorize_resource(db, ctx, *, resource_type, resource_id, action_level, is_platform_admin)`
  — the one guard every domain calls: full `check_access`; **EXPLICIT_DENY → 403
  `RESOURCE_ACCESS_DENIED`**, any other denial → non-disclosing **404**. ACL grants
  elevate without a broad workspace permission.
- `can_manage_access(...)` — sharing authority = platform-admin **or** owner **or**
  the resource's `manage_permission` (mirrors `_assert_can_manage`).
- `collection_visibility_subqueries(resource_type, subjects, now)` — returns
  `(allowed_ids, denied_ids)` SELECTs for SQL-level list filtering (no N+1, no leak).
- `resource_access_summary(...)` → `ResourceAccessSummary` (level, allowed_levels,
  can_manage_access, source, reason).
`apps/api/src/vip_api/governance/access_view.py`: `ResourceEffectiveAccess`
pydantic block embedded on read responses.

### Capability → level mappings (ladders from `LEVEL_ORDERS`)

| Domain | Ladder (low → high) | Action → level (service-enforced) |
|--------|---------------------|-----------------------------------|
| **Dataset** | query < export < edit < certify < manage | View/Preview/Query/Fields/Profile/Lineage-read → **query**; Edit/Field-edit/Lineage-write → **edit**; Certify (quality rules & evaluations) → **certify**; Archive/Delete → **manage**; Manage Access → owner/`dataset.update`. *Export* is ACL-grantable (query does not imply export). |
| **Connection** | use < test < edit < rotate < manage | View metadata/Use → **use**; Test → **test**; Edit/credentials-replace → **edit**; Rotate secret → **rotate**; Delete/Archive → **manage**; Manage Access → `connection.update` (no owner column). |
| **Semantic** | view < query < edit < manage | View/metadata/versions → **view**; **Query execution → query**; Edit (model + dimensions/measures/metrics/kpis) → **edit**; Publish/Archive → **manage**; Manage Access → `semantic_model.update`. |

Requirements honored: Query does **not** imply Export; Edit does **not** imply
Certify; Use does **not** imply Edit; Rotate requires the rotate level; Publish is
manage-level. Manage-Access follows existing policy (owner/manage_permission), not
the resource "manage" level.

### Route mappings (elevation)
Resource-bound routes now gate on the **capability** (feature/entitlement) instead
of a broad `*.read/*.update` permission, so an ACL grant reaches the resource; the
service `_guard`/`authorize_resource` makes the real per-resource decision:
- Dataset: `dataset_capability` (+ `data_quality`/`data_lineage` capability gates
  on quality/lineage routes). Create/discover/ingest keep RBAC + quota.
- Connection: `connection_capability`. Create + type-catalog keep RBAC + quota.
- Semantic: `semantic_capability`; query execution → `semantic_query_capability`
  (quota consumed inside `execute_query`). Model/metric creation + glossary keep RBAC.
The route-policy coverage test still passes: `RequireCapability` transitively
depends on `get_authorization_context`, which the validator accepts.

### Collection filtering
`list_datasets` / `list_connections` / `list_models` add an SQL visibility predicate
when the caller lacks a broad role: `owner ∪ non-expired ACL allow (direct or group)
− lowest-level deny`, applied to **both** the count and the page (Dataset/Connection
via a repository `extra_filters` param). No N+1; pagination, totals, and search never
leak hidden resources.

### Semantic execution model (documented)
`semantic/query.py::execute_query` is the **single chokepoint** for every execution
path — direct `POST /semantic-query`, dashboard widgets (`dashboards/query.py::
execute_widget`), dashboard exports and scheduled delivery
(`dashboard_delivery/worker.py`). Immediately after loading the published model it
calls `authorize_resource(..., "semantic_model", model.id, "query")` **before** any
dataset/connection/secret access. Therefore a user can never execute a model they
cannot access, from any surface; because the check is live, a revoked grant or new
deny blocks **future** executions immediately. Denied paths never touch the secret
provider or the data source.

### Worker / background propagation (audited)
- **Dashboard delivery/export worker** rebuilds the requesting user's real
  `AuthorizationContext` (org, workspace, roles) from `job.requested_by_user_id`, so
  the semantic execution guard runs *as that user* — revoked semantic access affects
  their scheduled deliveries. Workers do not bypass authorization.
- **Dataset quality worker** reconstructs org/workspace from the persisted
  evaluation row; the per-user certify authorization is enforced at enqueue time
  (route `data_quality` capability + service `certify` guard). Documented as a
  trusted post-authorization system execution (no cross-tenant access; tenant stamped
  on the record).
- **Pipeline worker** (connection secrets) is a trusted tenant-scoped system context
  (unchanged; Pipeline slice).

### Frontend (backend remains authoritative)
`src/shared/lib/resourceAccess.ts` maps the backend `access` block and exposes
`resourceCan(access, level)` / `resourceDenied` / `canManageAccess`. The three
Studios consume it: Connection detail gates Edit/Test/Rotate/Archive + Share;
Dataset detail gates Share (+ Access tab); Semantic builder gates Edit/Publish/
Archive + Share — each falling back to broad permissions only until the detail
response loads. Frontend visibility is never the security boundary.

### Verification (this slice)
- Static: `ruff check .` ✓, `ruff format --check .` ✓ (228 files), `mypy src tests`
  ✓ (204 files).
- Backend tests (fresh `vip_test`, `alembic upgrade head` + `alembic check` clean):
  unit **196**, integration **35 ×2** (both green). New: integration
  `test_resource_authorization_domains.py` (dataset/connection/semantic elevation,
  deny 403, stranger 404, group grant, collection visibility, expiration,
  secrets-never-returned, sharing authority, semantic execution chokepoint).
- Frontend: `typecheck`/`lint`/`format:check` ✓, tests **266** (+6 in
  `resourceAccess.spec.ts`), `build` ✓.
- Live Chromium (`VITE_API_MODE=live`, admin/owner): connection detail response
  carries `access:{level:"manage",allowed_levels:[use,test,edit,rotate,manage],
  can_manage_access:true}` with **no secret values** (only `configured` booleans);
  dataset + semantic details render controls + Share from the effective-access
  decision. Negative personas (deny/stranger/viewer) + execution deny proven by the
  integration test.

### Remaining limitations
- Dataset **export** and connection **rotate** are enforced as ladder levels and
  ACL-grantable, but no dedicated export endpoint exists yet (preview/profile are
  query-level) — export authorization is ready for a future export route.
- Dataset quality worker authorizes at enqueue (not re-checked inside the worker) —
  acceptable trusted-context pattern, documented above.
