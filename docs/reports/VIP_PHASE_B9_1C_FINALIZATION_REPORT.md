# VIP Phase B9.1C — Connection, Semantic, Audit & Finalization Report

**Date:** 2026-08-04
**Branch:** `phase-b9/connection-semantic-finalization` → PR into `frontend/enterprise-ui-enhancement`
**Rollback tag (unchanged):** `6254d60d445f9b3849fa88d5151bd56cd770f339`
**Verdict:** `B9.1 CORE PRODUCT COMPLETION COMPLETE — READY FOR PR REVIEW`

> **Update (2026-08-04, round 2):** the items previously deferred (Objectives 8 &
> 9 — placeholder-module gating and the core UX consistency pass) plus semantic
> audit logging and the live persona matrix are now complete and verified. The
> status table and §§6–10 below reflect the finished state. See
> **§8 Placeholder-module gating**, **§9 Core UX consistency**, **§10 Semantic
> audit logging**, and the test report for the live persona matrix.

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
| 3 | Semantic Studio production readiness | ✅ Delivered | Re-publish (§3) + full modeling audit trail (§10) |
| 4 | Semantic query safety | ✅ Verified | All exec paths funnel through `execute_query` chokepoint; parameterized, authorized, audited |
| 5 | Semantic versioning/publishing | ✅ Delivered | Sequential immutable versions, re-draft on edit, deny paths — integration-tested (§3) |
| 6 | Semantic permissions/UI states | ✅ Delivered | FE consumes backend `access` effective decision; live persona matrix (test report) |
| 7 | Audit Center canonical route | ✅ Delivered | Dead `/audit` code + URL spec canonicalized to `/audit-events` (§4) |
| 8 | Placeholder-module gating | ✅ Delivered | Reports/Insights/Marketplace/Billing gated OFF in live mode; AI/Developer/Automation verified OFF (§8) |
| 9 | Core UX consistency | ✅ Delivered | Retry actions + honest error states + disabled-vs-unauthorized wall on B9.1C surfaces (§9) |

**Classification:** all nine objectives are complete and verified. Placeholder
modules never present an empty/fake surface as complete (§8); every semantic
modeling change is audited (§10); the live persona matrix and gating are proven
end-to-end in Chromium (test report).

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

# Round 2 (Objectives 3, 8, 9 + live persona matrix)
apps/api/src/vip_api/semantic/services.py        (dim/measure/metric/KPI + validate audit)
apps/api/tests/integration/test_semantic_audit.py       (new)
apps/api/src/vip_api/governance/policies.py      (insights/billing capability keys)
apps/api/src/vip_api/governance/seed.py          (drop report_studio/marketplace defaults)
src/app/router/index.ts                          (entitlement gates: reports/insights/marketplace/billing)
src/app/navigation.ts                            (nav entitlement gates + quick action)
src/modules/errors/UpgradeView.vue               (disabled-vs-unauthorized wall)
src/modules/operations/AuditCenterView.vue       (error retry)
src/modules/semantic/SemanticListView.vue        (honest load-error state)
tests/e2e/route-smoke.spec.ts                    (placeholder-gating assertions)
tests/e2e/semantic-personas.spec.ts              (new — live persona matrix)
```

Dependency `aiomysql>=0.2,<1` was already present in `apps/api/pyproject.toml`.

**Supply-chain fix (isolated commit):** the initial PR CI failed only at
`pip-audit`, which flagged three freshly-disclosed 2026 CVEs in the pinned
`cryptography==48.0.1` (a pre-existing repo-wide issue, not introduced by this
slice — the base branch fails identically). Bumped `cryptography>=50.0.0,<51`
(`pyproject.toml`) + `cryptography==50.0.0` (`requirements.lock`); pip-audit is
now clean and all backend gates + integration ×2 re-pass with 50.0.0. See the
test report §6a.

---

## 8. Objective 8 — Placeholder-module gating

An investigation confirmed that **all seven placeholder modules have no
production backend**: Reports/Insights/Marketplace/AI resolve to stub catalog
endpoints that return an empty list, and Billing/Developer/Automation have no
backend route at all (they 404 in live mode). Presenting any of them as complete
would show an empty or fabricated surface.

Gating (entitlement-based, mirroring the existing AI Studio / Developer Portal
precedent — a missing entitlement resolves the route to the upgrade wall and
hides the nav item):

- **Newly gated:** Reports (all routes), Insights, Marketplace (list + detail),
  Billing. `governance/policies.py` recognizes `insights` and `billing` as
  capability keys (default off); `governance/seed.py` no longer grants
  `report_studio` or `marketplace` in `DEFAULT_ORGANIZATION_ENTITLEMENTS`. Route
  meta + nav items + the New Report quick action carry the entitlement gate.
- **Verified already OFF:** AI Studio (`ai_studio` flag+entitlement off),
  Developer Portal (`developer_api` off), Automation (`automation` never granted).

No dead nav (gated items are filtered out of the sidebar/command palette), no
empty pages presented as complete, no live requests to nonexistent APIs, no fake
API keys/billing surfaced. **Future module code is preserved** — re-add the
entitlement to the org defaults when a module ships a real backend. Disabled vs
unauthorized is distinguished at the UI: a disabled module reaches the reframed
`UpgradeView` ("not available on this workspace" — not a permission error), while
a permission failure reaches `ForbiddenView`. `route-smoke.spec.ts` now asserts
the gated routes redirect to a safe wall and never render the module surface.

## 9. Objective 9 — Core UX consistency

A focused pass on the B9.1C surfaces using existing shared components (no visual
redesign):

- **Audit Center:** the "audit events unavailable" alert now offers a **Retry**
  action wired to the query refetch (previously a dead end).
- **Semantic Studio list:** a load failure previously fell through to the "No
  semantic models yet" empty state — presenting an error as an empty workspace. A
  distinct **error alert + Retry** now makes a failed load unambiguous.
- **Disabled-state UX:** `UpgradeView` reframed to name the specific module and
  state it is disabled (not a permission error), distinguishing disabled from
  unauthorized, and no longer links to the gated Billing placeholder.
- **Verified already present:** Connection Studio list/detail (loading, empty,
  error + retry, refresh, toasts, confirm dialogs) and Semantic builder (error +
  retry, validation toasts, unsaved-state refetch) already met the bar.

## 10. Objective 3 — Semantic modeling audit trail

Every semantic modeling mutation now emits a persistent, tenant-scoped audit
event against the parent model via a shared `_audit_child` helper:
create/update/delete of **dimensions, measures, metrics and KPIs** (12 paths),
each carrying actor, org, workspace, resource, entity + entity_id, a correlation
id, and **before/after** snapshots of the declarative definition — never secrets
or raw SQL. Direct `validate_model` requests emit `semantic_model.validated` with
the outcome and error codes (publish validates with `audit=False` so a publish
records a single event). Publish/re-publish, query execution, and sharing/ACL
grants were already audited. Covered by `test_semantic_audit` (all ten event
types persist with correct metadata; before/after reflect an edit; no secret or
raw SQL is captured; an invalid model audits as a failure).

---

## 7. Quality gates — all green (see companion test report)

Backend: `ruff check` ✓ · `ruff format --check` ✓ · `mypy src tests` ✓ ·
240 unit ✓ · alembic upgrade+check clean ✓ · **58 integration ×2 both green** ✓.
Frontend: typecheck ✓ · lint ✓ · format ✓ · 279 unit ✓ · build ✓.

No `.env`, credentials, outbox, screenshots, traces, build output, test DBs, or
venvs are committed. The rollback tag is unchanged.
