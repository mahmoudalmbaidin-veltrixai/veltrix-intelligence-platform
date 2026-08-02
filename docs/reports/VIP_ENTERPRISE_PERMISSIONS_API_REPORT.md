# VIP Enterprise Permissions — API Report

All endpoints are mounted under the API v1 prefix (`/api/v1`). Mutations require CSRF (`Depends(require_csrf)`) and a resolved `AuthorizationContext` (tenant headers). Resource-management endpoints additionally enforce `can_manage_resource` (owner / manage-permission / super-admin) and audit denied attempts.

## Permission catalog & custom roles (`role_routes.py`)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/permission-catalog` | Authoritative list of catalog permissions (backend is the single source) |
| GET | `/custom-roles` | List system + custom roles (`include_system`, `include_archived`, `scope`, `q`). Path is `/custom-roles` so it does not collide with legacy `GET /roles` (system-role catalog for Org Admin). |
| POST | `/custom-roles` | Create custom role (validates name uniqueness, scope, privilege ceiling) |
| GET | `/custom-roles/{role_id}` | Role detail (+ `permission_keys`, `assignment_count`) |
| PATCH | `/custom-roles/{role_id}` | Update role (optimistic `expected_version`) |
| POST | `/custom-roles/{role_id}/clone` | Clone role |
| POST | `/custom-roles/{role_id}/archive` | Archive / restore |
| DELETE | `/custom-roles/{role_id}` | Soft-delete custom role (removes assignments) |
| GET | `/custom-roles/{role_id}/assignments` | List user + group assignments |
| POST | `/custom-roles/{role_id}/assignments` | Assign role to a user or group |
| POST | `/custom-roles/{role_id}/assignments/bulk` | Bulk assign (per-item success/failure) |
| DELETE | `/custom-roles/{role_id}/assignments/{assignment_id}` | Unassign (subject_type query) |

## Groups, principals & resource ACL (`access_routes.py`)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/groups` | List groups (`include_archived`) |
| POST | `/groups` | Create group |
| GET | `/groups/{group_id}` | Group detail |
| PATCH | `/groups/{group_id}` | Rename/update (optimistic) |
| POST | `/groups/{group_id}/archive` | Archive / restore |
| DELETE | `/groups/{group_id}` | Soft-delete (`expected_version`) |
| GET | `/groups/{group_id}/members` | List members |
| POST | `/groups/{group_id}/members` | Add member |
| DELETE | `/groups/{group_id}/members/{user_id}` | Remove member |
| GET | `/principals/search` | Search users + groups by query |
| GET | `/resource-types` | Resource types + their level ladders |
| GET | `/resources/{resource_type}/search` | Tenant-scoped resource picker search |
| GET | `/resources/{resource_type}/{resource_id}/access` | List ACL entries |
| POST | `/resources/{resource_type}/{resource_id}/access` | Grant / deny access |
| DELETE | `/resources/{resource_type}/{resource_id}/access/{entry_id}` | Revoke entry |
| GET | `/resources/{resource_type}/{resource_id}/effective` | Effective access (optional `user_id`) |
| POST | `/resources/{resource_type}/{resource_id}/simulate` | Simulate a user's access (no persistence) |

## Enforcement changes on existing resource APIs (no contract changes)

No request/response schemas changed. The following existing endpoints now enforce per-resource **explicit deny + expiration** (defense-in-depth) via `enforce_resource_guard`, returning `403 RESOURCE_ACCESS_DENIED` when a matching deny applies:

- **Pipelines:** `GET /pipelines/{id}`, `PUT /pipelines/{id}`, `POST /pipelines/{id}/publish`, `POST /pipelines/{id}/versions/{vid}/restore`, `DELETE /pipelines/{id}`, `POST /pipelines/{id}/runs`, `POST …/runs/{run_id}/cancel`, `POST …/runs/{run_id}/retry`.
- **Datasets:** `GET /datasets/{id}`, `PATCH /datasets/{id}`, `PATCH …/fields/{fid}`, `POST …/archive`, quality-rule create/update/delete, quality-evaluation create.
- **Connections:** `GET /connections/{id}`, `PATCH /connections/{id}`, `POST …/test`, `PUT/POST …/credentials(/rotate)`, `POST …/archive`.
- **Semantic models:** `GET /semantic-models/{id}`, edit paths, `POST …/publish`, `POST …/archive`.
- **Dashboards:** unchanged endpoints; full allow+deny+ownership overlay already applied in the service `_access`.

## Response conventions
- Errors follow the platform `ApplicationError` envelope with stable `code` values (`RESOURCE_ACCESS_DENIED`, `RESOURCE_MANAGE_DENIED`, `RESOURCE_TYPE_INVALID`, `ACCESS_LEVEL_INVALID`, `EFFECT_INVALID`, `SUBJECT_NOT_FOUND`, `ROLE_*`, `VERSION_CONFLICT`).
- Role responses include derived `permission_keys` and `assignment_count`; effective/simulate responses include the decision `reason`, `source`, `level`, `allowed_levels`, and `evaluated_at`.

---

## Dataset / Connection / Semantic slice — route → authorization mapping

Resource-bound routes gate on the **capability** (feature/entitlement) and the
service resolves the per-resource decision via `authorize_resource` (centralized
`check_access`). Creation / quota / catalog / glossary routes keep RBAC + quota.

**Datasets** (`datasets/routes.py`): list, `{id}`, fields, preview, profile, PATCH,
archive, DELETE, field-update → `dataset_capability`; quality-* → `data_quality`
capability; lineage-* → `data_lineage` capability. Create/discover/ingest →
`dataset.create`/`dataset.discover` (+`datasets.max`). Service action levels:
query/edit/certify/manage. `GET {id}` embeds `access`.

**Connections** (`connections/routes.py`): list, `{id}`, PATCH, archive, DELETE,
`credentials` (PUT), `credentials/rotate`, `test` → `connection_capability`. Create
+ `types` → `connection.create`/`connection.types.read`. Service levels:
use/test/edit/rotate/manage. `GET {id}` embeds `access`. **No response ever returns
secret values** — only `credentials_configured` + per-field `configured` booleans.

**Semantic** (`semantic/routes.py`): models list/detail/versions/validate/publish/
archive + dimensions/measures/metrics(PATCH,DELETE)/kpis → `semantic_capability`;
`POST /semantic-query` → `semantic_query_capability` (quota consumed inside
`execute_query`). Model/metric creation + glossary keep RBAC + quota. Service levels:
view/query/edit/manage. `GET {id}` embeds `access`. **Query execution is authorized
on the model inside `execute_query`**, covering direct query, dashboard widgets,
exports, and scheduled delivery.

All read-detail responses now carry a `ResourceEffectiveAccess` block:
`{level, allowed_levels, can_manage_access, source, reason}`. Route-policy coverage
test still green (RequireCapability transitively depends on the authorization
context resolver).
