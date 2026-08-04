# VIP Phase B9.1 — Manual UAT Script

**Date:** 2026-08-04
**Branch:** `phase-b9/connection-semantic-finalization`
**Audience:** reviewer performing acceptance before approving the PR.
**Prereqs:** `docker compose --profile connectors up -d` (postgres, redis, api,
workers, clamav, **mysql**); frontend on `http://localhost:3009`.

> This UAT covers the B9.1C slice deliverables (MySQL discovery, semantic
> re-publish, audit route). Deferred objectives (placeholder gating, UX pass)
> are **out of scope** for this acceptance and are tracked in the finalization
> report.

---

## UAT-1 — MySQL connection discovery (real container)

1. Connection Studio → create a MySQL connection: host `mysql`, port `3306`,
   database `vip_demo`, username `vip_reader`, password `vip_reader_dev`,
   SSL mode `disable`.
2. Test the connection → expect **success**.
3. Run discovery / register dataset from the connection.
   - **Expect:** `vip_demo.customers` (a table) with 4 columns; types render as
     `id → integer`, `name/email → string`.
   - **Expect:** the object/field lists are bounded and return promptly.
4. Edit the connection, change the password to an invalid value, re-run discovery.
   - **Expect:** a clear failure ("discovery failed"), **no** secret echoed in
     any message or log; the connection is not corrupted.

**Pass criteria:** real MySQL objects appear with correct normalized types;
credential failures surface honestly without leaking the secret.

---

## UAT-2 — Semantic model re-publish

1. Semantic Studio → open (or create) a model with at least one dimension and one
   metric; validate → **valid**; Publish → **version 1**.
2. Edit the published model (rename it, or change a field).
   - **Expect:** the model returns to **draft**; Publish becomes available again;
     version 1 remains visible/immutable in history.
3. Publish again → **version 2**. Repeat once more → **version 3**.
   - **Expect:** version history shows 1, 2, 3 as distinct immutable snapshots.
4. With no unpublished changes, attempt Publish again.
   - **Expect:** blocked — "no unpublished changes to publish."
5. As a user without manage rights on the model, attempt to publish.
   - **Expect:** blocked (not found / forbidden); no new version created.

**Pass criteria:** repeatable publishing with sequential immutable versions;
edit re-enables publish; clean model cannot double-publish; unauthorized publish
is denied.

---

## UAT-3 — Audit Center

1. Perform a few auditable actions (publish a model, register a dataset, deny an
   unauthorized action).
2. Open **Audit Center**.
   - **Expect:** real audit events across domains render (no placeholder data).
3. Exercise filters: search, actor, action/event type, resource type, date range,
   pagination.
   - **Expect:** filters narrow results; pagination advances; tenant context is
     respected (only the current org/workspace's events).

**Pass criteria:** the Audit Center shows real, filterable, tenant-scoped events
from the canonical `/api/v1/audit-events` endpoint.

---

## Reviewer sign-off

| UAT | Result (Pass/Fail) | Notes |
|-----|--------------------|-------|
| UAT-1 MySQL discovery | | |
| UAT-2 Semantic re-publish | | |
| UAT-3 Audit Center | | |

**Overall B9.1C acceptance:** ☐ Approved ☐ Changes requested

---

## UAT-4 — Placeholder-module gating (live mode)

1. As an org admin, confirm the sidebar shows **no** Reports, Insights,
   Marketplace, or Billing entries (nor AI Studio / Developer / Automation).
2. Navigate directly to `/reports`, `/insights`, `/marketplace`, `/billing`.
   - **Expect:** each redirects to a wall — the **"not available on this
     workspace"** upgrade page when the module is merely disabled, or the
     Forbidden page if you also lack the permission. The empty/fake module
     surface is never shown.
3. Confirm the upgrade wall names the specific module and states it's disabled
   (not a permission error), distinguishing disabled from unauthorized.

**Pass criteria:** placeholder modules are unreachable in live mode, with no dead
nav, no empty pages presented as complete, and no fake API keys/billing surfaced.

---

## UAT-5 — Semantic modeling audit trail

1. In Semantic Studio, open a model and add/edit/delete a dimension, a measure, a
   metric and a KPI; run Validate; Publish.
2. Open **Audit Center** and filter by the model.
   - **Expect:** a distinct event for each change
     (`semantic_dimension.created`, `…measure.updated`, `…kpi.deleted`,
     `semantic_model.validated`, `semantic_model.published`, …), each showing the
     actor, timestamp, correlation ID, and a before/after snapshot in the detail
     drawer.
   - **Expect:** no secrets or raw SQL appear in any snapshot (the drawer states
     sensitive fields are redacted).

**Pass criteria:** every modeling mutation and validation is captured as a
tenant-scoped, before/after audit event with no sensitive data.

---

## Reviewer sign-off (round 2)

| UAT | Result (Pass/Fail) | Notes |
|-----|--------------------|-------|
| UAT-4 Placeholder gating | | |
| UAT-5 Semantic audit trail | | |

All B9.1C objectives (Connection/MySQL, Semantic re-publish + audit, Audit route,
placeholder gating, core UX, live persona matrix) are now in scope for acceptance;
no items are deferred.
