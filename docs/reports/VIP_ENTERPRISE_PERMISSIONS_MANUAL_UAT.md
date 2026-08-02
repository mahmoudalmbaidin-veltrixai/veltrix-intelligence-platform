# VIP Enterprise Permissions — Manual UAT Guide

**Frontend:** http://localhost:3009
**API:** http://localhost:8000 (`/health` healthy, `/ready` ready)
**All Docker services running and healthy.**

## Local-only demo credentials

> These accounts and the password below are for the **local development environment only**. They are not production credentials and are safe to use for this review. Passwords were provisioned idempotently via `python -m vip_api.cli configure-governance-demo` (never stored in the repo).

| Persona | Email | Password | Intended role |
|---------|-------|----------|---------------|
| Admin | `governance-admin@vip.demo` | `Enterprise review 2026!` | Org/workspace admin — create roles, groups, share |
| Editor | `governance-editor@vip.demo` | `Enterprise review 2026!` | Editor/developer |
| Viewer | `governance-viewer@vip.demo` | `Enterprise review 2026!` | Read-only |
| Restricted | `governance-restricted@vip.demo` | `Enterprise review 2026!` | Target for explicit deny |

Login verified: `POST /auth/login` for `governance-admin@vip.demo` → HTTP 200.

The UI uses tenant-scoped **resource pickers** and **principal search** — you should not need to paste UUIDs anywhere for the review.

---

## Review checklist

### A. Roles (Administration → Roles)
1. Open **Roles**. Confirm system roles are listed and locked (no edit/delete).
2. **Create custom role**: name it "Curator", pick permissions from the categorized matrix (try Select-all in a category, then Search, then Clear). Save.
   - *Expected:* role created; duplicate name is rejected; you cannot select permissions you don't hold (privilege ceiling) unless super-admin.
3. **Clone** "Curator" → "Curator Copy". *Expected:* new editable role with the same permissions.
4. **Archive** then **Restore** a custom role. *Expected:* status toggles; archived roles hidden unless "include archived".

### B. Role assignment
5. In the role's **Assignments** dialog, search a **user** (principal search) and assign. Assign to a **group** too.
6. Use **bulk assign** with several users. *Expected:* per-item success/failure; no partial silent failure.
7. Log in as the assigned user in another tab. *Expected:* the new permissions are in effect (backend `AuthorizationContext`), not just UI.

### C. Groups (Administration → Groups)
8. Create a group, rename it, add/remove members (principal search). Archive/restore.
   - *Expected:* optimistic-lock conflicts surface a clear message; every change is audited.

### D. Resource sharing (each Studio)
9. **Dashboards** — open a dashboard in Studio/viewer → **Share**: search a user/group, pick a level, set an expiration, save; then **revoke**.
10. **Pipelines** — Pipeline Studio → **Share** button → grant/deny.
11. **Datasets** — Dataset detail → **Share**.
12. **Connections** — Connection detail → **Share** (confirm no secret is ever shown).
13. **Semantic models** — Semantic builder → **Share**.
   - *Expected:* the same dialog everywhere; grant/deny/expiration/revoke; read-only mode if you lack `resource.permissions.manage`.

### E. Explicit deny (backend-enforced)
14. As Admin, grant `governance-restricted@vip.demo` an **explicit deny** on a pipeline (viewer level).
15. Log in as Restricted and open that pipeline.
   - *Expected:* access blocked with `RESOURCE_ACCESS_DENIED` (server-enforced — not just a hidden button). Deny overrides any inherited allow and even ownership.

### F. Expiration
16. Grant a short-lived allow (expiry a few minutes out) and confirm it works, then expires.
   - *Expected:* expired entries are ignored by the engine.

### G. Effective access / inspector (Administration → Access Control)
17. Pick a resource (via the resource picker), pick a subject, run the inspector / **Simulate**.
   - *Expected:* final decision, effective level, allowed actions, source (owner/role/ACL/deny), super-admin status, and evaluation timestamp — no persisted change.

### H. Audit
18. Open the Activity/Audit area. *Expected:* every grant/deny/revoke, role change, assignment, and group/membership change appears with actor, tenant, resource, action, and timestamp.

---

## Reset / re-provision (if needed)
```bash
docker compose exec \
  -e VIP_GOVERNANCE_ADMIN_PASSWORD='...' \
  -e VIP_GOVERNANCE_EDITOR_PASSWORD='...' \
  -e VIP_GOVERNANCE_VIEWER_PASSWORD='...' \
  -e VIP_GOVERNANCE_RESTRICTED_PASSWORD='...' \
  api python -m vip_api.cli configure-governance-demo
```

## Pipeline ACL — full action matrix + grant-only elevation (this slice)

Pipeline authorization is now enforced per-resource for **every** action through
the centralized evaluator, and — like dashboards — a Pipeline ACL grant now
**elevates** access without any broad `pipeline.*` workspace permission.

Levels: **Viewer** (open/read, versions, runs, logs, artifacts) < **Operator**
(+ run/cancel/retry) < **Developer** (+ edit/save/validate/publish) < **Owner**
(+ archive/delete + manage sharing). Sharing management requires **Owner or a
tenant admin** — a Developer/Operator/Viewer ACL grantee cannot re-share.

**Reproduce with the demo personas:**
1. As **Admin**, open a pipeline in **Pipeline Studio → Share**.
2. Grant `governance-viewer@vip.demo` a **Viewer** level. Log in as Viewer and open
   the pipeline. *Expected:* opens read-only — a **viewer** badge + **READ-ONLY**
   indicator; Validate/Save/Publish/Run disabled; the name field is read-only; no
   Share button.
3. Grant `governance-restricted@vip.demo` (who has **no** pipeline role permission)
   a **Developer** level on a different pipeline. Log in as Restricted and open it.
   *Expected:* **elevation** — a **developer** badge, full authoring + run enabled,
   no Share. (The route no longer requires `pipeline.read`; the backend authorizes
   the specific resource.)
4. Grant an **Owner** level (or use the pipeline's owner). *Expected:* Share button
   visible, archive/delete allowed.
5. Add an **explicit deny** (Viewer level) for Restricted on a pipeline they can
   otherwise see. Log in as Restricted and open it. *Expected:* blocked — the API
   `GET /api/v1/pipelines/{id}` returns **HTTP 403 `RESOURCE_ACCESS_DENIED`** and
   the UI shows the **Forbidden** page (server-enforced, not a hidden button).
6. Open **Pipelines** (list) as Restricted. *Expected:* only pipelines they can see
   appear — denied/ungranted pipelines are hidden (no leaked names or totals).

Verified live in Chromium (`VITE_API_MODE=live`) against the running stack.

## Notes / limitations to keep in mind during review
- **Reports** have no physical backend table yet; report sharing is registered in the engine but report operations are not enforceable (gated). Do not treat report sharing as production-ready.
- **Pipelines, Datasets, Connections, and Semantic models all support grant-only ACL elevation** (as of the final resource-authorization slice): a user without the base `*.read` workspace permission can be granted a resource level on a specific dataset/connection/semantic model and will reach exactly that capability band — enforced server-side, reflected in the Studio UI (see the Dataset/Connection/Semantic UAT below). Only **Reports** remain registered-but-not-enforceable (no physical table).
- **Pipeline sharing** requires the resource Owner or a tenant admin (`pipeline.update`); a Developer/Operator/Viewer whose access is only an ACL grant cannot re-share (server returns `RESOURCE_MANAGE_DENIED`).

---

## Dataset / Connection / Semantic Resource Authorization — Manual UAT

**Frontend:** http://localhost:3009 · **API:** http://localhost:8000 · live mode.
**Demo credentials (governance-demo org, local only):**

| Persona | Username | Password |
|---------|----------|----------|
| Admin (owner/manage) | `governance-admin` | `Enterprise review 2026!` |
| Editor | `governance-editor` | `Enterprise review 2026!` |
| Viewer | `governance-viewer` | `Enterprise review 2026!` |
| Restricted (deny target) | `governance-restricted` | `Enterprise review 2026!` |

Capability ladders: Dataset `query<export<edit<certify<manage`; Connection
`use<test<edit<rotate<manage`; Semantic `view<query<edit<manage`. Sharing requires
Owner or the manage permission.

### Dataset UAT
1. As Admin, open a dataset (e.g. **LIVE-UAT-Customers**). *Expected:* detail loads;
   **Share** button visible (admin can manage access); Access tab present.
2. Open the dataset's **Share** dialog → grant `governance-restricted` a **query**
   level. Log in as Restricted, open that dataset → opens read-only (metadata,
   fields, preview) but **no Share**, no edit. This proves elevation without
   `dataset.read`.
3. As Admin, add an **explicit deny** (query) for Restricted on a dataset they could
   otherwise see. As Restricted, open it → **blocked** (`GET /api/v1/datasets/{id}`
   → 403 `RESOURCE_ACCESS_DENIED`).
4. Open **Datasets** list as Restricted → only datasets they can see appear; the
   denied/ungranted ones are hidden (no leaked names/totals).

### Connection UAT
1. As Admin, open a connection (**LIVE-UAT-Enterprise-Sales-PostgreSQL**). *Expected:*
   Edit / Test connection / Archive / **Share** render; the response shows
   `credentials_configured:true` and per-field `configured` flags but **no secret
   values**.
2. Grant Restricted a **use** level → they can view metadata + open detail but see no
   Edit/Test/Rotate/Share. Grant **edit** → Edit appears; **rotate** → the credential
   form appears. Proves Use does not imply Edit; Rotate requires explicit authorization.
3. As Restricted with no grant → the connection is hidden from the list and
   `GET /api/v1/connections/{id}` → 404.

### Semantic UAT
1. As Admin, open a semantic model (**LIVE-UAT-Sales-Model**). *Expected:* Save
   draft / Validate / Publish / Archive / **Share** render.
2. Grant Restricted a **query** level → they can view + run queries on it; grant
   **edit** → editing appears; **manage** for publish. Sharing stays admin/owner-only.
3. **Execution enforcement:** add an explicit **deny** (view/query) for Restricted on
   a model used by a dashboard widget. As Restricted, open that dashboard →
   the widget's `POST /api/v1/dashboards/{id}/widgets/{wid}/data` (which runs the
   model) returns **403** — a user can never execute a model they cannot access, even
   via a dashboard. Revoking the grant blocks future runs immediately.

### Expected permission behavior (summary)
- ACL grant → capability works **without** the broad workspace permission.
- Explicit deny → 403 and hidden from lists; expired grant → ignored.
- Stranger / cross-tenant → non-disclosing 404.
- Secrets are never returned by any connection API.
- Sharing is Owner / Manage-Access only.
