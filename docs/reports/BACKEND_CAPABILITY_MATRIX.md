# Backend Capability Matrix — Lifecycle (Archive / Restore / Delete)

Verified by direct inspection of the locked backend at `apps/api/src/vip_api/**` (routes + services) and the frontend live adapters. The backend was **not modified**. Baseline commit: `46b2de6`.

## Headline findings (critical, honesty-driven)

1. **There is no hard / permanent delete anywhere.** Every resource's `DELETE` handler calls the same `archive_*` service (sets `archived_at`) as its `POST /archive` endpoint. Verified:
   - `dashboards/routes.py` `delete_dashboard()` → `archive(...)`
   - `pipelines/routes.py` `@router.delete(...)` handler is literally named `archive()` → `archive_pipeline(...)`
   - `datasets/routes.py` `datasets_delete()` → `archive_dataset(...)` (same function as `datasets_archive()`)
   - `connections/routes.py` `delete_connection()` → `archive_connection(..., permission="connection.delete", audit_event="connection.deleted")`
   The only difference between "archive" and "delete" is the **required permission** and the **audit event**.
2. **There is no resource-level restore / un-archive endpoint for any of the four.** The only `restore` routes are *version* restores (`/versions/{id}/restore`), which are **not** the same as un-archiving a resource. → No restore UI is implemented anywhere.
3. **Archived listing is supported only for datasets** (`GET /datasets?status=archived`). Dashboards force `archived_at IS NULL` and only accept `status=draft|published`; connections `list` has no status/archived param.

## Matrix

| Resource | Archive endpoint | Delete endpoint | Delete = soft-archive? | Restore / un-archive | Archived list filter | Optimistic concurrency | 409 conflict codes |
|---|---|---|---|---|---|---|---|
| **Dashboard** | ✅ `POST /dashboards/{id}/archive` (204) | ✅ `DELETE /dashboards/{id}` (204) | ✅ yes (sets `archived_at`) | ❌ none (version-restore only) | ❌ list excludes archived; `status` ∈ {draft,published} | ✅ `expected_version` (both) | `DASHBOARD_VERSION_CONFLICT`, `DASHBOARD_SLUG_CONFLICT` |
| **Pipeline** | ❌ none (no separate archive) | ✅ `DELETE /api/v1/pipelines/{id}` (204) | ✅ yes (handler `archive_pipeline`) | ❌ none (version-restore only) | ❌ | ✅ `expected_version` (required) | `VERSION_CONFLICT`, `RUN_NOT_RETRYABLE`, `RUN_RETRY_LIMIT` |
| **Dataset** | ✅ `POST /datasets/{id}/archive` (204) | ✅ `DELETE /datasets/{id}` (204) | ✅ yes (both call `archive_dataset`) | ❌ none | ✅ `GET /datasets?status=archived` | (service-level `VERSION_CONFLICT` exists) | `VERSION_CONFLICT` |
| **Connection** | ✅ `POST /api/v1/connections/{id}/archive` (204) | ✅ `DELETE /api/v1/connections/{id}` (204) | ✅ yes (both call `archive_connection`) | ❌ none | ❌ (list has no status param) | version fields on credential ops | `CONNECTION_NAME_CONFLICT`, `CONNECTION_VERSION_CONFLICT` |

## Frontend implementation decision (per resource)

| Resource | Archive UI | Delete UI | Restore UI | Archived filter UI | Notes |
|---|---|---|---|---|---|
| Dashboard | ✅ Implemented (warning) | ✅ Implemented (danger, typed) | ❌ Not implemented | ❌ Not implemented | Both call real endpoints w/ `expected_version`; honest "no in-app restore" copy |
| Pipeline | ❌ Not applicable (no archive endpoint) | ✅ Implemented (danger, typed) | ❌ Not implemented | ❌ Not implemented | Delete sends `expected_version` from list row |
| Dataset | ✅ Implemented (warning) | ✅ Implemented (danger, typed) | ❌ Not implemented | ⚠️ Backend-supported, **UI deferred** | Only resource where an archived filter is contract-supported |
| Connection | ✅ Implemented (warning) | ✅ Implemented (danger, typed) | ❌ Not implemented | ❌ Not implemented | Secrets never shown in dialog or logs |

## BACKEND CAPABILITY REQUIRED — NOT IMPLEMENTED (backend is locked)

- **Restore / un-archive for Dashboard, Pipeline, Dataset, Connection** — no resource-level restore endpoint exists. Version-restore ≠ un-archive.
- **Pipeline archive** — no separate archive endpoint; only DELETE (which soft-archives).
- **Archived-list filter for Dashboard and Connection** — list contracts exclude archived and expose no archived status filter.
- **True permanent/hard delete** — not offered by any endpoint; all deletes are soft-archives.
