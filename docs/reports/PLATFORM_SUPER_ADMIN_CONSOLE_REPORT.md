# VIP — Platform Super-Admin Console (Build Report)

Date (UTC): 2026-07-27
Branch: `frontend/enterprise-ui-enhancement`

## A. Summary

Added a production-grade, cross-tenant **Platform Super-Admin console** so a SaaS operator can
manage every organization, workspace and user from one place, while every normal tenant remains
fully isolated. Delivered backend + frontend + migration + CLI + tests, verified live and via
Playwright.

Verdict: **READY** — backend and frontend gates pass; live-verified (admin 200 / non-admin 404 /
unauth 401); no cross-tenant leakage introduced.

## B. Security model (most important)

- Platform admin is a **user-level flag** `users.is_platform_admin`, **outside** the per-org
  membership/role model. It is never self-granted; only the operator grants it via CLI.
- Every `/api/v1/platform/*` route is gated by a single dependency `require_platform_admin`, which
  returns a **non-disclosing 404** for non-admins (the console's existence is not advertised).
- Coverage is test-enforced: a unit test asserts **every** platform route carries
  `require_platform_admin`; the governance route-policy test still passes for all other routes.
- Mutations require CSRF. All platform actions are audited (`platform.organization.*`,
  `platform.user.*`). Suspending an org/user takes effect on their next request (status is enforced
  server-side), and an admin cannot suspend themselves.
- Live checks: admin `/platform/overview` → 200; tenant-b (non-admin) → 404; unauthenticated → 401;
  non-admin suspend → 404.

## C. Backend

| Endpoint | Purpose |
| --- | --- |
| `GET /api/v1/platform/overview` | Counts: orgs (active/suspended), workspaces, users (active/suspended), platform admins |
| `GET /api/v1/platform/organizations` | All orgs (paged, search) with member + workspace counts |
| `POST /api/v1/platform/organizations` | Create an isolated org; optional `owner_email` assigns an existing user as owner |
| `GET /api/v1/platform/organizations/{id}` | Org detail: members (role/status) + workspaces |
| `POST /api/v1/platform/organizations/{id}/suspend` \| `/activate` | Suspend/reactivate an org |
| `GET /api/v1/platform/users` | All users (paged, search) with org counts, status, admin flag, last login |
| `POST /api/v1/platform/users/{id}/suspend` \| `/activate` | Suspend/reactivate a user |

New module: `apps/api/src/vip_api/platform_admin/` (`dependencies.py`, `schemas.py`, `services.py`,
`routes.py`). Registered in `api/router.py`. CLI: `grant-platform-admin` / `revoke-platform-admin`.

## D. Database migration

`20260727_0012_platform_admin_flag.py` — adds `users.is_platform_admin boolean not null default
false` (reversible). Standard, additive DDL; existing rows default to non-admin. No data backfill.

> Ops note: applying `ALTER TABLE users …` requires no open transaction to hold a lock on `users`;
> run migrations with the app stopped or during a maintenance window (as usual for DDL).

## E. Frontend

- `src/modules/platform/platform.service.ts` — typed API client.
- `src/modules/platform/PlatformConsoleView.vue` — Overview (stat tiles), Organizations (search,
  suspend/activate, create-org dialog, detail dialog with members + workspaces), Users (search,
  suspend/activate). Errors use `safeErrorText`.
- Route `/platform` (`requiresPlatformAdmin`, no org/workspace required); guard returns `not-found`
  for non-admins (mirrors the backend 404).
- `is_platform_admin` flows through the `/auth/me` contract → auth service → platform store
  (`platform.isPlatformAdmin`).
- Sidebar "Platform Admin" entry is shown only to platform admins (`platformAdminOnly` gate).

## F. Tests

- Backend unit: `tests/unit/test_platform_admin.py` (route gating, non-disclosing gate, governance
  policy still complete) — passes.
- Frontend e2e: `e2e/platform-admin.spec.ts` — (1) platform admin opens the console (overview,
  orgs, users); (2) normal tenant user has no nav entry and `/platform` does not render the console.
  Both pass in real Chromium.
- CI: `quality-gate.yml` grants `tenant-a@vip.demo` platform admin during browser-test seeding.

## G. Gate results

| Gate | Result |
| --- | --- |
| Backend ruff / format / mypy | PASS (194 files fmt; mypy 176 files) |
| Backend unit | PASS (89) |
| Backend integration | PASS (25) |
| Frontend typecheck / lint / format | PASS |
| Frontend unit | PASS (178) |
| Frontend production build | PASS |
| Playwright (platform-admin) | PASS (2) |
| Live API (admin/non-admin/unauth) | 200 / 404 / 401 |

## H. How to use

Grant an operator, then sign in and open **Platform Admin** in the sidebar (or `/platform`):

```bash
# from apps/api
python -m vip_api.cli grant-platform-admin --email you@company.com
```

## I. Limitations / not in scope (honest)

- No user **impersonation** and no **hard-delete** of orgs/users (suspend/archive only) — deliberate
  for safety; can be added later with extra confirmation + audit.
- Org/user lists are paged at up to 100 with server-side search; no CSV export yet.
- Creating an org from the console assigns an **existing** user as owner (by email) or the operator;
  it does not create new user accounts (invite flow lives in per-org admin).
