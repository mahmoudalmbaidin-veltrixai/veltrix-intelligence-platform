# VIP Enterprise Permissions — Security Report

## 1. Single authoritative precedence
One evaluator, `evaluate_resource_access` (`governance/resource_access.py`), implements the precedence used everywhere:

```
suspended > explicit deny > super-admin > archived workspace > ownership
  > resource allow > role grants (direct + group) > default deny
```

Explicit deny is **fail-closed**: it overrides super-admin and ownership. Locked by `tests/unit/test_authorization_precedence.py`. No duplicate evaluator exists (verified by grepping for precedence logic; all callers go through `check_access` / `effective_access` / `access_overlay` / `enforce_resource_guard`).

## 2. Backend enforcement is mandatory (not frontend-only)
- Every protected route declares its policy via `require_governance(permission, feature, entitlement, quota)`.
- Resource operations additionally call `enforce_resource_guard` (pipeline/dataset/connection/semantic) or the full `access_overlay` (dashboard) at the service layer — the frontend `ResourceShareButton`/dialogs are convenience only and cannot bypass these checks.
- CSRF (`require_csrf`) is enforced on all mutations, including bulk endpoints.

## 3. Tenant isolation & non-disclosure
- All ACL/role/group queries are filtered by `organization_id` (+ `workspace_id` where scoped).
- `load_resource_meta` scopes resource lookups to the caller's org; cross-tenant resource IDs resolve as `not found` (no existence disclosure).
- Simulation and effective-access respect the acting administrator's tenant and require `resource.permissions.read`/`manage`.
- Covered by `test_custom_roles.py` (tenant isolation) and `test_resource_permissions.py`.

## 4. Privilege-escalation controls
- **Custom-role self-escalation:** `role_service._validate_permissions` blocks granting any permission the actor does not already hold, unless the actor is a platform super-admin (privilege ceiling). Tested in `test_custom_roles.py`.
- **Horizontal escalation:** ACL grants are per-(resource, subject) and tenant-scoped; a user cannot grant on resources they cannot manage (`_assert_can_manage`, audited on denial).
- **Group-membership escalation:** group grants only apply to actual, active, non-archived memberships (`group_ids_for_user`).
- **System roles** cannot be modified or deleted (`_protected`).

## 5. Secret non-exposure (connections)
- Secrets remain write-only; no permission or ACL endpoint returns secret values.
- Distinct levels: `use` (read metadata / operate) ≠ `test` ≠ `edit` ≠ `rotate` ≠ `manage`. A `use` grant does not confer edit/rotate/delete; a `test` grant does not confer secret values. Enforced via `enforce_resource_guard` action levels on the connection service (`get`=use, `test`=test, `update`=edit, `rotate credentials`=rotate, `archive`=manage).

## 6. Expiration
- Expired allow/deny entries are ignored by `access_overlay` and `evaluate_resource_access`. Proven for a non-dashboard resource in `test_resource_guard_enforcement.py` (expired deny no longer blocks) and for dashboards in `test_resource_permissions.py`.

## 7. Deny precedence in practice
- A viewer-level deny blocks all higher actions; a developer-level deny blocks developer/owner actions but not viewer reads (rank semantics). Verified in `test_resource_guard_enforcement.py`.

## 8. Caching (fail-closed rationale)
`AUTHORIZATION_CACHE_ENABLED` is **disabled**. Distributed caching of security decisions was deferred because safe invalidation must react atomically to: membership changes, role-assignment changes, ACL grant/deny/expiry, and workspace archival — across tenants and without any stale-allow window. Rather than risk a stale *allow*, the system resolves fresh each request (with per-request `request.state` memoization to avoid intra-request N+1). When enabled in future, keys must be tenant-scoped and invalidated on every mutation; until proven with invalidation tests it stays off (fail-closed).

## 9. Negative tests
- Explicit deny blocks owner and role-holders (fail-closed).
- Duplicate role name rejected; cross-tenant role/group not found; privilege ceiling rejects escalation; system role protected; expired grant ignored; manage-denied attempts audited.

## 10. Residual risks / follow-ups
- **Report resource:** registered in the ACL engine but has no physical backend; report operations are not yet enforceable (gated in UI).
- **Grant-only elevation for pipeline/dataset/connection/semantic:** their strict RBAC route gates remain the coarse allow-gate; the ACL layer currently adds fail-closed *deny* + expiration but does not loosen those gates to grant brand-new access to users lacking the base permission (dashboards do, via loose gates). This is a deliberate no-regression choice; broadening requires converting those routes to feature/entitlement gates + full service-level `check_access`.
- **Semantic-query bypass:** dashboard/explore execution paths against semantic models were not fully audited for a documented service-account policy.
- **Live browser persona tests** were not executed this session (see Test report).

---

## Dataset / Connection / Semantic slice — security properties

- **Single decision point.** All three domains resolve through
  `resource_access_service.authorize_resource` → `check_access` (evaluator
  precedence unchanged). No duplicated precedence logic.
- **Non-disclosure.** Explicit deny → `403 RESOURCE_ACCESS_DENIED`; no grant /
  insufficient level / cross-tenant / expired → non-disclosing `404`. Collection
  lists filter in SQL, so hidden resources never leak via items, totals, pagination,
  or search.
- **Secrets never leave the API.** Connection responses expose only
  `credentials_configured` and per-field `configured` flags. `test_connection` reads
  the secret internally to run the probe and returns only success/health/latency —
  never the value. Rotation requires the `rotate` level.
- **Semantic execution chokepoint.** `execute_query` authorizes the model at the
  `query` level **before** any dataset/connection/secret access, on every surface
  (direct, widgets, exports, delivery worker). A user can never execute a model they
  cannot access; revocation/deny affects future executions immediately; denied paths
  never touch the secret provider or data source.
- **Workers do not bypass authorization.** The dashboard delivery/export worker
  rebuilds the requesting user's real context and runs the semantic guard as that
  user. The dataset-quality worker authorizes at enqueue (certify) and runs in a
  tenant-scoped trusted context. No cross-tenant access is possible.
- **Frontend is not the boundary.** Studios consume the backend `access` block only
  to show/disable controls; every action is independently enforced server-side.
