# VIP Enterprise Permissions — Database Report

**Alembic head:** `20260728_0018` (single head)
**Parity:** `alembic check` → `No new upgrade operations detected.`
**Migration strategy:** additive only; no destructive rewrites of existing data.

## Migrations added (uncommitted, this enhancement)

| Revision | Down-rev | Purpose |
|----------|----------|---------|
| `20260728_0016_resource_access_entries` | prior head | Resource-level ACL table |
| `20260728_0017_groups_and_memberships` | `…0016` | Groups + memberships |
| `20260728_0018_custom_roles_and_assignments` | `…0017` | Custom-role columns + user/group role assignments |

Downgrades are implemented for all three (safe for these uncommitted migrations).

## New tables

### `resource_access_entries`
Per-(resource, subject) ACL grant/deny.
- Columns: `id`, `organization_id`, `workspace_id`, `resource_type`, `resource_id`, `subject_type` (user|group), `subject_id`, `access_level`, `effect` (allow|deny), `expires_at`, `granted_by_user_id`, `created_at` (NOT NULL), `updated_at` (NOT NULL).
- Indexes on `(resource_type, resource_id)` and `(organization_id)`; tenant-scoped FKs.

### `groups` / `group_memberships`
- `groups`: tenant-scoped, `name`, `description`, `status`, `archived_at`, `deleted_at`, `row_version`, audit fields; unique `(organization_id, normalized_name)`.
- `group_memberships`: `(group_id, user_id)` unique; FK to groups + users.

### `user_role_assignments`
- `id`, `organization_id`, `workspace_id` (nullable), `user_id`, `role_id`, `scope`, `assigned_by_user_id`, `created_at`.
- Unique `(organization_id, workspace_id, user_id, role_id)`; indexes on `(organization_id, user_id)`, `(role_id)`.

### `group_role_assignments`
- `id`, `organization_id`, `workspace_id` (nullable), `group_id`, `role_id`, `scope`, `assigned_by_user_id`, `created_at`.
- Unique `(organization_id, workspace_id, group_id, role_id)`; indexes on `(organization_id, group_id)`, `(role_id)`.

## Modified tables

### `roles` (extended, additive)
Added: `organization_id` (nullable → tenant custom roles), `workspace_id` (nullable), `slug` (nullable), `status` (default `active`), `is_editable` (default `false`), `created_by_user_id`, `updated_by_user_id`, `row_version` (default `1`), `archived_at`, `deleted_at`.
- Added unique `uq_roles_org_slug (organization_id, slug)`.
- Added indexes `(organization_id, scope)`, `(workspace_id)`.
- System (seeded) roles keep `organization_id IS NULL`, `is_editable = false` and are protected in code.

## Tenancy, integrity, and lifecycle conventions
- **Tenant scoping:** every new table carries `organization_id` (+ `workspace_id` where scoped); composite/tenant-scoped FKs.
- **Soft deletion:** `deleted_at` on `groups`, `roles`; ACL revocation is a hard delete of the entry (audited).
- **Optimistic locking:** `row_version` on `groups`, `roles`.
- **Audit timestamps:** `created_at` / `updated_at` NOT NULL on ACL and lifecycle tables (the `resource_access_entries` nullability drift observed on the shared dev DB was reconciled with an explicit `ALTER … SET NOT NULL`; a freshly-migrated `vip_test` DB is clean).

## Fresh-DB verification
`vip_test` is created fresh, `alembic upgrade head` applied, and the full integration suite (31 tests) runs green against it. `alembic check` reports parity between ORM metadata and migrations.

## Indexes relevant to authorization performance
- ACL lookups: `(resource_type, resource_id)`.
- Group membership resolution: `group_memberships (user_id)` + join on `groups (organization_id)`.
- Role-assignment resolution: `(organization_id, user_id)` / `(organization_id, group_id)` + `(role_id)`.

See the Security report for the query strategy and N+1 analysis.

---

## Dataset / Connection / Semantic slice — schema impact

**No new migrations.** The final resource-authorization slice reuses the existing
`resource_access_entries` (allow/deny, `expires_at`, subject user|group, org+ws
scoping), `groups`/`group_memberships`, and role tables. Ownership is read from each
resource table's `owner_user_id` where present:

| Resource type | Table | owner_column | Notes |
|---------------|-------|--------------|-------|
| dataset | `datasets` | `owner_user_id` | ownership grants all levels |
| connection | `connections` | *(none)* | no ownership — role/ACL only |
| semantic_model | `semantic_models` | *(none)* | `created_by_user_id` is a display owner only, not wired to the evaluator |

Collection visibility is enforced by parameterized `SELECT resource_id FROM
resource_access_entries WHERE resource_type=… AND subject_id IN (…) AND effect=… AND
(expires_at IS NULL OR expires_at > now)` sub-selects combined with the resource
table's `owner_user_id`/`id` — no schema change, no denormalization. Alembic head
unchanged (`20260728_0018`, single head, `alembic check` clean).
