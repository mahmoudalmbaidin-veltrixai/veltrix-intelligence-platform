# VIP Phase B9.0 — Critical Stabilization Report

**Date:** 2026-08-03
**Branch:** `phase-b9/critical-stabilization`
**Baseline (merge of PR #2):** `886eb4f7511a153d9a85dd3f3ba17b507636bf11`
**Rollback tag:** `pre-phase-b9-enterprise-baseline` → `6254d60d…` (unchanged)
**Scope:** the four confirmed B9.0 blockers from the production-readiness assessment. No B9.1+ work, no placeholder-module work, no architecture redesign.

This branch resumes and completes the partial B9.0 work started earlier: Part 1 (role-assignment security) and Part 2 (pipeline re-publish) were recovered intact from the working tree; Part 3 (schema restoration) and Part 4 (password recovery + forced change) were implemented here.

---

## 1. Role-assignment privilege escalation (security) — FIXED

### Root cause
`role_assignment_service.assign_user_role` / `assign_group_role` performed **no authorization** beyond the route's `require_permission("role.assign")`. Unlike membership updates (`tenancy/services.py`) and invitations, they omitted the privilege ceiling, `is_assignable`, and self/rank guards. A holder of `role.assign` could therefore assign `organization_owner`/`organization_admin` to anyone (including themselves) or package `role.assign` into a custom role handed to a low-privilege member — a tenant-takeover path.

### Enforcement added (`role_assignment_service.py`)
A single fail-closed guard `_authorize_assignment` now runs before any assignment is staged, applied identically to the **user and group** paths (closing the group back-door):
- **Archived/inactive role** → refused for everyone (`ROLE_ARCHIVED`, 409). Deleted roles were already unresolved by `get_role`.
- **Platform super-admins** bypass the ceiling/assignable checks (they hold every permission) but never the archived guard.
- **`is_assignable == False`** (e.g. Organization Owner) → refused for tenant admins (`ROLE_NOT_ASSIGNABLE`, 403).
- **Permission ceiling** → the role's permission set must be a subset of the actor's own permissions, else `ROLE_ESCALATION_DENIED` (403). Mirrors `role_service._validate_permissions`.
- **Administrative-rank ceiling for system roles** → a system role's priority may not exceed the actor's effective membership rank (`max(org, workspace)` priority), else `ROLE_ESCALATION_DENIED`. Custom roles are bounded by the permission ceiling instead.
- **Cross-tenant / cross-workspace** are already blocked upstream: `get_role` scopes to the actor's org (or a global system role), the subject loaders require active membership in the actor's org, and the assignment binds to the actor's own workspace context.
- Every denial is **audited** (`role.assignment.denied`, non-disclosing message). During bulk assignment the denial audit is written with `commit=False` so it does not prematurely commit other staged rows; the single-assignment path commits it so it survives the route's rollback.

The routes (`role_routes.py`) now thread `is_platform_admin=auth.user.is_platform_admin` through single and bulk assignment.

### Tests (`tests/integration/test_role_assignment_security.py`, 6 assertions/cases)
Equal-or-lower assignment allowed; higher/protected (Owner) denied incl. self; permission ceiling; administrative-rank ceiling (holds perms but lower rank); self-escalation; group-path parity; platform-admin bypass; archived refused even for platform admin; cross-tenant subject → `SUBJECT_NOT_FOUND`; cross-org role → `ROLE_NOT_FOUND`; denial auditing. Existing `test_custom_roles.py` (legitimate admin assignment) still green.

---

## 2. Pipeline re-publish — FIXED

### Root cause
The backend already supported sequential immutable versions (`publish_pipeline` mints `max(version_number)+1`). The defect was the **state machine + UI**: `save_editor` never returned a published pipeline to `draft`, so the pipeline still read as `published` and the frontend Publish button was permanently disabled (`status === 'published'`).

### Fix
- **Backend (`pipelines/services.py`):** `save_editor` now sets `status = "draft"` on every saved draft. The last published version stays viewable/runnable via `published_version_id` (unchanged) and existing runs keep their original `pipeline_version_id`.
- **Frontend (`PipelineStudioView.vue`):** the Publish button is gated by a new `canPublish` computed — enabled when there are unpublished changes (`status !== 'published' || dirty`), disabled only for a clean, already-published pipeline.

### State-transition design
create → save (draft) → validate → publish v1 (published) → edit + save (draft) → validate → publish v2 (published) → … Each publish creates a new immutable `PipelineVersion` with a distinct content hash; versions are sequential; runs are linked to the version they were created from; optimistic `expected_version` is enforced; invalid graphs are refused.

### Tests (`tests/integration/test_pipeline_republish.py`, 2 tests)
Publishes v1→v2→v3 sequentially; asserts draft-after-publish, version immutability/sequence, run/version linkage across republish, latest-version selection for new runs, optimistic conflict on a stale version, and that an incomplete graph cannot publish. Frontend `canPublish` + save-after-publish (status→draft mapping) is covered by the schema-restoration spec's use of the live `mapEditor` status field and validated live.

---

## 3. Pipeline schema restoration on load — FIXED

### Root cause
On load, `mapEditor` did not reconstruct source-node schema, and `usePipelineEditor` never propagated schema at construction. Source nodes therefore had no `outputSchema`, so the downstream Select / Rename / Formula editors opened blank until the user perturbed the graph.

### Fix
- **`pipelines.service.ts`:** `mapEditor` now rebuilds a `source-dataset` node's `outputSchema` from its persisted `config.schema_snapshot` (`[{name,type,nullable}]`), normalized to the editor's `SchemaColumn` (`{name, dataType}`) via a type mapper. Returns nothing when no valid snapshot exists — so a genuinely unavailable schema surfaces a clear empty state rather than invented columns, and saved config is never erased.
- **`usePipelineEditor.ts`:** `propagateSchemas()` is now invoked once at construction (before the saved snapshot is captured, so a freshly-loaded pipeline is never marked dirty), flowing upstream columns into every downstream node's `inputSchema`/`outputSchema`.

### Resulting behavior
On reopening a saved pipeline: Select shows upstream columns with the saved selection restored; Rename shows upstream columns with old→new mappings preserved; Formula shows field suggestions from the propagated schema with the saved expression intact. Re-propagation still runs on every mutation.

### Tests (`src/modules/pipelines/schemaRestoration.spec.ts`, 5 tests)
`mapEditor` snapshot→`outputSchema`; propagation on construction with no dirty flag; Select/Rename/Formula restoration; missing-schema state (no invented columns, config preserved).

---

## 4. Password reset + forced password change — IMPLEMENTED

### Backend API (`auth/routes.py`, mounted at `/auth`)
- `POST /auth/password-reset/request` `{identifier}` — accepts username or email; **always** returns `202 {status:"accepted"}` (non-disclosing); rate-limited per IP+identifier (`password_reset_rate_limited`, fails open on Redis outage so recovery stays possible); issues a single-use token and emails a link via the existing provider abstraction; audits `auth.password_reset.requested`.
- `POST /auth/password-reset/confirm` `{token, new_password}` — validates token by hash+purpose+expiry, single-use; on success rotates the password, clears `must_change_password`, and revokes all sessions; audits `auth.password_reset.completed`. Password-policy failures now return `422 PASSWORD_POLICY` (previously an unhandled 500).
- `POST /auth/change-password` `{current_password, new_password}` — session + CSRF required; verifies the current password, applies the new one, clears the flag, revokes all sessions; audits `auth.password_changed`.

### Token security
Reuses the existing `PasswordResetToken` model: `secrets.token_urlsafe` value, stored only as a purpose-separated SHA-256 hash (`hash_token(token, "password-reset")`), TTL from `PASSWORD_RESET_TOKEN_TTL_MINUTES`, single-use (prior unused tokens invalidated on new request; `used_at` set on consume). The raw token is never persisted or logged and never returned by a normal API response (delivered only via the email link).

### Email / outbox
New `auth/email.py::send_password_reset_email` composes the message and delivers via `get_email_provider(settings)` (the same `file`/`smtp` abstraction as dashboard delivery). Delivery is best-effort — a transport failure never changes the non-disclosing response. Locally the `file` provider (compose default) writes `<uuid>.eml` to `/data/vip-email-outbox`.

### Forced-change enforcement
- `AuthenticatedUser` (schema + FE contract) now carries `must_change_password`, surfaced by `/auth/login` and `/auth/me` so the client can route into the forced-change flow.
- **Server-side chokepoint:** `get_tenant_context` raises `403 PASSWORD_CHANGE_REQUIRED` for a flagged user. Every tenant-scoped business route depends on it, while session-only endpoints (`me`/`logout`/`change-password`/`password-reset`) do not — so a flagged user can reach only the change-password flow. This runs before any tenancy/authorization bootstrap to avoid a guaranteed 403 during resolution. The flag is cleared only by a successful reset or change.

### Frontend
- New blank-layout views: `ForgotPasswordView.vue`, `ResetPasswordView.vue`, `ForcePasswordChangeView.vue` (accessible labels, loading/error/success states, password-policy guidance, non-disclosing messaging, invalid/expired/used-token states).
- Router: `/forgot-password`, `/reset-password`, `/force-password-change` routes; the guard redirects a flagged authenticated user to the forced-change screen (and away from it once cleared) before any tenancy/authorization bootstrap, so a direct deep link cannot bypass it.
- `LoginView` "Forgot password?" now links to the real flow (the previous static toast was removed).
- Auth service (`apiAuthService.ts`) gains `requestPasswordReset`/`confirmPasswordReset`/`changePassword`; the auth store exposes a `mustChangePassword` computed.

### Tests (`tests/integration/test_password_recovery.py`, 8 tests + `apiAuthService.spec.ts` +5)
Non-disclosing request (known vs unknown identical; username accepted); suspended user issues no token; confirm rotates password + revokes sessions + old password rejected + new accepted + single-use; invalid/expired token → 400; password policy → 4xx; change-password wrong-current → 400, success revokes sessions; `must_change_password` blocks a business route (`PASSWORD_CHANGE_REQUIRED`) while `/me` stays reachable and is cleared after change; rate-limit burst. Existing `test_authentication.py` updated for the new `(token, user)` return and a precise secret-leak assertion.

---

## API changes (all additive)
`POST /auth/password-reset/request`, `POST /auth/password-reset/confirm`, `POST /auth/change-password`. `AuthenticatedUser` responses gain `must_change_password`. New error codes: `PASSWORD_CHANGE_REQUIRED`, `PASSWORD_POLICY`, `ROLE_ARCHIVED`, `ROLE_NOT_ASSIGNABLE`, `ROLE_ESCALATION_DENIED`.

## Database changes
**None.** No migration was required — `must_change_password` and `password_reset_tokens` already exist. `alembic check` on a fresh `_test` database reports a single head (`20260728_0018`) with no drift.

## Files changed
Backend: `auth/{routes,password_reset,email,rate_limit}.py`, `schemas/auth.py`, `governance/{role_assignment_service,role_routes}.py`, `pipelines/services.py`, `tenancy/dependencies.py`, `core/config.py`. Frontend: `modules/auth/{LoginView,ForgotPasswordView,ResetPasswordView,ForcePasswordChangeView}.vue`, `modules/pipelines/{PipelineStudioView.vue,pipelines.service.ts,usePipelineEditor.ts}`, `app/router/index.ts`, `shared/services/auth/{apiAuthService,types}.ts`, `shared/contracts/apiContracts.ts`, `shared/stores/auth.ts`. Tests: 4 new backend integration files, 1 new FE spec, and updates to `test_authentication.py` + `apiAuthService.spec.ts`.

---

## Validation (exact totals)
| Gate | Result |
|---|---|
| Backend `ruff check .` | passed |
| Backend `ruff format --check` | passed (234 files) |
| Backend `mypy src tests` | passed (209 files) |
| Backend unit (`pytest -m "not integration"`) | **196 passed** |
| Backend integration run 1 (fresh `_test` DB) | **49 passed** |
| Backend integration run 2 | **49 passed** |
| Frontend `typecheck` | passed |
| Frontend `lint` | passed |
| Frontend `format:check` | passed |
| Frontend unit (`vitest`) | **275 passed** (43 files) |
| Frontend `build` | passed |
| Alembic | single head `20260728_0018`, `alembic check` clean |

## Live evidence (running stack)
- New endpoints on the running container: request → `202`, confirm(bad token) → `400`, change-password(no auth) → `401`.
- **End-to-end reset via the email outbox:** request for `governance-viewer@vip.demo` → `202`; `.eml` written to `/data/vip-email-outbox`; token extracted; confirm → `200`; token reuse → `400`; login with the new password → `200`.
- **Forced change:** flagged user login → `200` with `must_change_password:true`; business route `GET /api/v1/roles` → `403 PASSWORD_CHANGE_REQUIRED`; `GET /auth/me` → `200`; flag then cleared. (Persona passwords were restored to their documented value so UAT is unaffected.)

> The in-app browser pane was not displayable in this environment, so the browser-driven visual pass was substituted with the equivalent full-stack live checks above and the `TestClient`-driven end-to-end integration suite (which drives the real routes, CSRF, sessions, and the `must_change_password` chokepoint).

## Regression check
Backend unit (196) + integration (49 ×2) cover login/logout/refresh, roles/groups/ACLs, dashboards/pipelines/datasets/connections/semantic authorization, tenancy, and workers with no failures. Frontend unit (275) + typecheck/lint/build pass. Existing `test_custom_roles`, `test_authentication`, and `test_pipeline_persistence` remain green.

## Remaining B9 work (not in this branch)
B9.1 — dashboard delivery scheduler + real cron; pipeline run/retry via resource evaluator; read-only pipeline surfaces; pipeline artifacts UI; dataset mock tabs; dataset certify gating; AuditCenter path; MySQL discovery; export fidelity. B9.2 — global security headers; rate-limit hardening; authz N+1s; DB indexes/FKs; retention; SSRF TOCTOU; secret-key rotation. B9.3 — schema-driven form validation; confirm-dialog coverage; a11y expansion; settings persistence. B9.4 — build Reports/AI/Automation/Billing/Marketplace/Developer backends (gated off until then).

## Known limitations
- MFA remains absent (B9 enhancement).
- Reset-email delivery depends on a configured provider; local UAT uses the `file` outbox.
- Change-password revokes all sessions (requires re-login) — a deliberate security choice, not session rotation.
