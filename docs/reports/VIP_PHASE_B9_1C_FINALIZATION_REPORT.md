# VIP Phase B9.1C — Connection, Semantic, Audit & Finalization Report

**Date:** 2026-08-04
**Branch:** `phase-b9/connection-semantic-finalization` → PR into `frontend/enterprise-ui-enhancement`
**Rollback tag (unchanged):** `6254d60d445f9b3849fa88d5151bd56cd770f339`
**Verdict:** `B9.1C PARTIALLY COMPLETE — MORE WORK REQUIRED`

---

## 1. Scope delivered in this slice

This slice closed the highest-value, lowest-risk gaps toward B9.1 core-product
completion and honestly defers the remainder. Every change is additive and
scoped to the Connection, Semantic, and Audit domains — Dashboard, Pipeline, and
Dataset were not modified.

| # | Objective | Status | Evidence |
|---|-----------|--------|----------|
| 1 | Connection Studio — real MySQL discovery | ✅ Delivered | Live discovery against the real `mysql` container (§2) |
| 2 | Connection discovery performance/safety | ✅ Verified | Bounded lists, timeouts, `validate_host` SSRF, tenant scoping reused from PG adapter |
| 3 | Semantic Studio production readiness | ◑ Partial | Re-publish state machine fixed + tested; broader model-CRUD audit gaps remain |
| 4 | Semantic query safety | ✅ Verified (no change) | All exec paths already funnel through `execute_query` chokepoint (prior slice) |
| 5 | Semantic versioning/publishing | ✅ Delivered | Sequential immutable versions, re-draft on edit, deny paths — integration-tested (§3) |
| 6 | Semantic permissions/UI states | ✅ Verified | FE consumes backend `access` effective decision (prior slice) |
| 7 | Audit Center canonical route | ✅ Delivered | Dead `/audit` code + URL spec canonicalized to `/audit-events` (§4) |
| 8 | Placeholder-module gating | ⚠️ Deferred | AI/Developer/Automation/Billing already OFF by default; route-level gating of Reports/Insights deferred (would break `route-smoke.spec.ts` without coordinated e2e work) |
| 9 | Core UX consistency | ⚠️ Deferred | No focused UX pass in this slice |

**Honest classification:** this is a *partial* completion. Objectives 1, 5, and 7
are production-ready and verified; objectives 8 and 9 are explicitly deferred to
avoid CI-breaking, cross-cutting changes that this slice was not scoped to land
safely.

---

## 2. Objective 1 — MySQL metadata discovery (headline deliverable)

`MySQLDiscoveryAdapter` was added to `apps/api/src/vip_api/datasets/discovery.py`,
mirroring the PostgreSQL adapter's contract, caps, timeouts, and SSRF host
validation. MySQL has no separate catalog/schema, so the database name is the
schema. Analytics (preview/profile/query) remain PostgreSQL-only **by design** —
MySQL connections do not advertise the `read_only_analytics` capability, so this
is an honest scope boundary, not a hidden gap. MySQL = discovery + dataset
registration.

**Type normalization** (`normalize_mysql_type`): tinyint/int/bigint/year →
`integer`; decimal/float/double → `decimal`; bit/bool → `boolean`; date →
`date`; datetime/timestamp → `datetime`; time → `time`; binary/blob →
`binary`; json → `json`; char/varchar/text/enum/set → `string`; unknown →
`unknown`.

### Live evidence (real container, NOT mocked)

```
# Happy path — discovery of the real vip_demo database
OK objects=1 truncated=False
  - vip_demo.customers [table] fields=4
    sample=[('id','int','integer'), ('name','varchar','string'), ('email','varchar','string')]

# Error path — wrong credentials
bad-creds -> DISCOVERY_FAILED status=502 (secret not echoed: OK)
```

- Discovery succeeded against the live `mysql` container (`vip_demo.customers`,
  4 fields), with correct physical→normalized type mapping.
- Bad credentials produce a typed `DISCOVERY_FAILED` (502); the supplied secret
  never appears in the error message.
- Bounded by `METADATA_DISCOVERY_MAX_OBJECTS` (+1 truncation probe) and
  `METADATA_DISCOVERY_MAX_FIELDS_PER_OBJECT`; per-query `asyncio.wait_for`
  timeouts; `validate_host` SSRF guard; pool closed in `finally`.

The adapter is registered in `MetadataDiscoveryAdapterRegistry`
(`postgresql` + `mysql`); unsupported connectors return `DISCOVERY_UNSUPPORTED`
(422).

---

## 3. Objective 5 — Semantic re-publish state machine

The semantic publish path previously raised `SEMANTIC_MODEL_IMMUTABLE`, blocking
any re-publish — the same defect fixed earlier in the pipeline domain. Fixed in
`apps/api/src/vip_api/semantic/services.py`:

- Editing a published model (`_model(editable=True)`) reopens it as `draft`; the
  previously published version snapshot stays immutable.
- `publish_model` requires a `draft` (else `SEMANTIC_MODEL_NOT_DRAFT`, 409),
  validates, then mints the next sequential published version computed as
  `max(existing version_number) + 1` — decoupled from the draft edit counter, so
  re-publish after edits never collides or skips. Mirrors the pipeline numbering.
- `manage`-level authorization enforced via the centralized `authorize_resource`.

**Frontend:** `SemanticBuilderView.vue` `isEditable` no longer requires
`status === 'draft'` — a published model can be edited (the backend re-drafts,
the view refetches).

Integration-tested (§3 tests): publish v1 → edit → v2 → edit → v3; exactly three
immutable version rows numbered [1,2,3]; clean published model rejects re-publish
with `SEMANTIC_MODEL_NOT_DRAFT`; an outsider with no membership/ACL cannot
publish and leaves no version rows behind.

---

## 4. Objective 7 — Audit Center canonical route

The canonical backend audit route is `/api/v1/audit-events` (already served and
already consumed by the live Audit Center via `governance/auditService.ts`). The
stale `/audit` path survived only in dead code (`operations.service.ts::listAudit`)
and the URL contract spec. Both were canonicalized to `/audit-events`; no live
request path changed, so no compatibility redirect is required (the old path was
never wired to a live view). Nav, router, and the live Audit Center were already
correct.

---

## 5. Files changed

```
apps/api/src/vip_api/datasets/discovery.py      (+MySQL adapter, normalize, registry)
apps/api/src/vip_api/semantic/services.py       (re-publish state machine)
apps/api/tests/integration/test_semantic_republish.py   (new)
apps/api/tests/unit/test_mysql_discovery.py             (new)
src/modules/operations/operations.service.ts    (audit path canonicalization)
src/modules/semantic/SemanticBuilderView.vue    (editable published models)
src/shared/lib/apiClient.services-url.spec.ts   (audit URL contract)
```

Dependency `aiomysql>=0.2,<1` was already present in `apps/api/pyproject.toml`.

---

## 6. Deferred / remaining work (why B9.1C is PARTIAL)

- **Objective 8 (placeholder gating):** Reports/Insights are still route-reachable
  in live mode. Route-level gating requires coordinated updates to
  `route-smoke.spec.ts` (which navigates `/reports` and `/insights` directly) or
  it breaks CI. AI Studio, Developer Portal, Automation, and Billing are already
  OFF by default via entitlements. **Not landed** to avoid a CI-breaking,
  cross-cutting change out of this slice's scope.
- **Objective 9 (core UX pass):** no focused loading/empty/error/retry
  consistency sweep in this slice.
- **Objective 3 (semantic CRUD audit):** dimension/measure/metric/KPI mutations
  are not yet audit-logged (model create/update/publish are).
- **Live Chromium persona UAT** across Viewer/Query/Editor/Manager/Denied states
  was not re-run for this slice.

These are documented, not hidden. See the assessment update for the running
production-readiness ledger.

---

## 7. Quality gates — all green (see companion test report)

Backend: `ruff check` ✓ · `ruff format --check` ✓ · `mypy src tests` ✓ ·
240 unit ✓ · alembic upgrade+check clean ✓ · **58 integration ×2 both green** ✓.
Frontend: typecheck ✓ · lint ✓ · format ✓ · 279 unit ✓ · build ✓.

No `.env`, credentials, outbox, screenshots, traces, build output, test DBs, or
venvs are committed. The rollback tag is unchanged.
