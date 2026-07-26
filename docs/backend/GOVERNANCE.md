# Phase B3 governance architecture

## Security boundary and request flow

The backend is authoritative. Authentication resolves the user, tenancy resolves active explicit
organization/workspace memberships, and governance builds an immutable request-scoped
`AuthorizationContext`. Route dependencies and sensitive service methods evaluate that context.
Frontend gates only improve navigation and presentation; clients cannot submit roles, permissions,
feature decisions, entitlements, quota counters, or an authorization context as trusted input.

Every protected backend operation must declare and enforce authentication, tenant scope,
permission, required feature, required entitlement, and quota policy where applicable. Frontend
visibility is never authorization.

Decision order is permission, feature flag, entitlement, then quota. Missing/unknown policy state
fails closed. Denials use stable codes (`PERMISSION_DENIED`, `FEATURE_DISABLED`,
`ENTITLEMENT_REQUIRED`, `QUOTA_EXCEEDED`, `QUOTA_CONFIGURATION_MISSING`) and persist a safe audit
event carrying the request correlation ID. Cross-tenant governance access returns a non-disclosing
404.

## Roles and permissions

Permission keys use stable `resource.action` names. Definitions and system mappings live in
`vip_api.governance.policies`, are inserted by migration, and are synchronized idempotently by the
CLI. Memberships reference role IDs; role scope is checked whenever a role is assigned.

| Role | Scope | Intended policy |
|---|---|---|
| `organization_owner` | organization | Full organization/workspace policy; system-managed assignment |
| `organization_admin` | organization | Organization and workspace administration |
| `organization_member` | organization | Organization/workspace discovery only |
| `workspace_admin` | workspace | Full workspace policy |
| `editor` | workspace | Read/create/update/execute without destructive administration |
| `viewer` | workspace | Read-only resource access |
| `restricted_user` | workspace | Workspace discovery only |

Demo persona mapping is Admin → `organization_admin` + `workspace_admin`, Editor →
`organization_member` + `editor`, Viewer → `organization_member` + `viewer`, and Restricted User →
`organization_member` + `restricted_user`. Unknown roles and cross-scope assignments are rejected.
Self-escalation, casual owner assignment, and demotion/removal of the last active owner are blocked.

Use `require_permission`, `require_any_permission`, `require_all_permissions`, or
`require_governance` on routes. Sensitive service methods additionally require an
`AuthorizationContext`; never call them with IDs alone. The route-policy test rejects new
versioned routes without an explicit governance declaration or reviewed special policy.

## Features, entitlements, and quotas

Feature resolution applies the global definition, then an organization override, then the more
specific workspace override. Active time windows are honored. Feature flags control operational
availability; entitlements are contractual organization grants. They are separate checks.

Organization quotas reference system definitions and usage rows. `consume_quota` locks the grant
row and updates usage in the caller transaction, preventing concurrent over-consumption. New
organizations receive explicit starter entitlements and quotas via
`provision_organization_governance`; this is stored policy, not a frontend default. Quota mutation
must happen before the protected resource is committed.

## Audit model

`audit_events` is append-only through application APIs and indexed by organization/time,
workspace/time, actor, and event/outcome. Events contain actor, tenant scope, correlation ID,
action, safe resource identity, outcome, and reason code. They never store cookies, tokens,
passwords, authorization headers, request bodies, or raw exception/SQL text. `GET
/api/v1/audit-events` is organization-scoped, filtered, paginated, and itself audited.

## Frontend integration

After the server validates selected organization/workspace IDs, the frontend calls `GET
/api/v1/authorization/context`. The Pinia authorization store keeps the response in memory and is
cleared on logout or tenant switch. Route guards, sidebar/command visibility, and
`PermissionGate`, `FeatureGate`, `EntitlementGate`, and `QuotaGate` consume this server-resolved
state and fail closed while unavailable. A normal 403 is rendered as denial and never triggers a
session refresh. Roles and effective feature flags in admin views are backend-backed and read-only
unless an authorized mutation API exists.

## APIs

```text
GET /api/v1/authorization/context
GET /api/v1/roles
GET /api/v1/permissions
GET /api/v1/organizations/{organization_id}/entitlements
GET /api/v1/organizations/{organization_id}/feature-flags
GET /api/v1/organizations/{organization_id}/quotas
GET /api/v1/audit-events
```

Existing organization/workspace/member/invitation mutations retain B1 CSRF enforcement and now
have explicit permission policies.

## Seed and test personas

From `apps/api`:

```bash
alembic upgrade head
python -m vip_api.cli seed-governance
```

Configure the development/test-only demo with secret environment variables (values are never
arguments, committed defaults, or output):

```powershell
$env:VIP_GOVERNANCE_ADMIN_PASSWORD="<secret>"
$env:VIP_GOVERNANCE_EDITOR_PASSWORD="<secret>"
$env:VIP_GOVERNANCE_VIEWER_PASSWORD="<secret>"
$env:VIP_GOVERNANCE_RESTRICTED_PASSWORD="<secret>"
python -m vip_api.cli configure-governance-demo
```

The command is idempotent and provisions four personas, enabled/disabled feature examples,
active/missing entitlements, and available/exhausted quota examples. It refuses staging/production.

```powershell
$env:RUN_INTEGRATION_TESTS="1"
pytest -m "integration or security"
```

From the repository root, provide the four persona password variables and run:

```bash
npx playwright test e2e/governance.spec.ts --project=chromium-desktop
```

## Extending and troubleshooting

Add stable definitions to the checked-in catalog; never silently rename a key. Add a reviewed
migration or synchronization step, declare route and service policy, add allow/deny/isolation/audit
tests, then run both backend and frontend quality gates. `PERMISSION_DENIED` means active roles do
not grant the key; `FEATURE_DISABLED` means effective policy is false; `ENTITLEMENT_REQUIRED` means
no active time-valid organization grant; quota errors mean a missing grant or insufficient hard
limit. Confirm tenant headers, inspect the safe authorization context, then use audit events as an
authorized administrator. Never work around a denial in frontend state.
