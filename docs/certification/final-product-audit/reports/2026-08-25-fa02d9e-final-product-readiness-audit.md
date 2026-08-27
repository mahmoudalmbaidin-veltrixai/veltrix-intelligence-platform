# VIP Final Adversarial Product Readiness Audit

**Platform:** Veltrix Intelligence Platform (VIP)
**Audit date:** 2026-08-25
**Posture:** Signed certification. Prior reports were not trusted.
**Reference SHA:** `fa02d9e2484f6b603efe5af9e7586975342b485c`
**Letter verdict:** **E — INTERNAL DEMO READY ONLY**
**VIP TOTAL PRODUCT READINESS SCORE: 49/100**

This document is the baseline for demo, pilot, production, enterprise, and resell decisions on this revision. It does not authorize production hosting or a paying customer.

---

## A. Tested Baseline

| Field | Evidence |
| --- | --- |
| Branch | `feat/vip-productization-p1` |
| HEAD | `fa02d9e2484f6b603efe5af9e7586975342b485c` |
| Subject | `docs(demo): add Stage 4 runbook and certification` |
| Remote | `origin` GitHub `veltrix-intelligence-platform`; branch **ahead 3** |
| Working tree | **Dirty / not a release.** Untracked: `DECKS/`, `VIP_CLIENT_DEMO_*.md`, demo xlsx, `demo-data/vip_demo_sales_orders.csv`, `scripts/demo/` |
| Host | Windows 10.0.26200, PowerShell |
| Node / npm | v24.19.0 / 11.17.0 |
| Host Python | 3.14.4 |
| Docker | 29.7.2 |
| Frontend | Vite `0.1.0`, port **3009**. **Was not listening at audit start.** Started during this audit. `.env.local`: `VITE_API_MODE=live` |
| Backend | Compose `vip-api-1` uvicorn reload, `/health` `{"status":"healthy","service":"vip-api","version":"0.1.0"}` |
| Version API | `{"name":"VIP API","version":"0.1.0","environment":"development","commit_sha":null,"build_timestamp":null}` |
| PostgreSQL | healthy `:5432` |
| Redis | healthy `:6379` PONG |
| Alembic | **one head** `20260808_0025`; `alembic current` = head |
| Job worker | `vip-dashboard-worker-1` healthy; heartbeat queue `default,dashboard` seen during audit |
| Pipeline worker | `vip-pipeline-worker-1` healthy |
| Scheduler process | **No live scheduler container.** `worker_heartbeats` still contains a `scheduler` row **stopped 2026-08-16**. Schedule ticks are code-inside the job worker. |
| ClamAV | healthy |
| Storage | local volumes: artifacts, pipeline artifacts, files, email outbox |
| Email | `DASHBOARD_EMAIL_PROVIDER=file`, `DASHBOARD_EMAIL_FROM=no-reply@vip.local`, SMTP host empty |
| Integrations enabled | PostgreSQL + local file (GA). Beta testers: MySQL, MSSQL, Snowflake, BigQuery, S3, REST API (optional drivers). ClamAV on API. |
| Integrations disabled / placeholder | ~100 catalog types `planned` / `requires_agent` / `requires_driver`. AI/Reports/Automation/Billing/Marketplace/Developer gated in live UI. |
| Mocked | Frontend mock adapters remain in tree; live mode hides most. Email is file-outbox. Invitation raw `token` returned because `APP_ENV=development`. Dashboard worker malware scanner `noop`. |
| Development-only | `/docs` + OpenAPI public; `ENABLE_DOCS=true`; `AUTH_COOKIE_SECURE=false`; Compose login rate limit **1000/min**; invitation token echo; `AI_DEVELOPMENT_MOCK_MODE=false` but AI still 403 via feature flag |
| Production-mode | **Not active.** `APP_ENV=development`. Production settings would reject file email, insecure cookies, noop scanner. |
| Extra local noise | `vipcertv2-*` Postgres/Redis/ClamAV also running |

**Reproducibility:** the Git object `fa02d9e` is identifiable. The **database is not**. 85 organizations, 127 users, thousands of QA/e2e leftovers. A second engineer checking out this SHA does not get this dataset. Untracked demo files are also outside the SHA.

---

## PART 2 — Product inventory

Authoritative live surface in `VITE_API_MODE=live` (not navigation fiction):

**Present and backend-connected:** Auth (login/logout/refresh/sessions/idle/profile/password change/reset request), platform console (super-admin), organizations/workspaces/members/roles/groups/ACL/flags/governance, connections (+ catalog), datasets (preview/profile/quality/lineage/versions), pipelines (studio/runs/schedules/nodes listed below), semantic models + glossary, dashboards (studio/viewer/publish/deliveries/export jobs), jobs, files, audit, usage quotas, notifications (job-derived), activity, settings, help (static).

**API:** 272 operations in `apps/api/tests/contracts/api_operation_manifest.json`.

**Hidden / 404 in live UI:** Reports, AI, Automation, Billing, Marketplace, Developer portal, Insights, Explore, Favorites, Dashboard templates.

**Missing routes:** `/invitations/accept` (config `INVITATION_ACCEPT_URL` points at a dead UI). `/jobs/:id` (notification deep links). Role-switcher advertised in `.env.example`, **no UI**.

**Pipeline nodes (registry):** `source-dataset`, `select-columns`, `rename-columns`, `filter`, `sort`, `join`, `union`, `aggregate`, `formula`, `row-validation`, `type-convert`, `deduplicate`, `null-handling`, `output-dataset`, `file-export`.

**Dashboard widgets (schema):** kpi, metric-comparison, table, pivot, bar, stacked-bar, column, line, area, pie, donut, scatter, gauge, progress, text, rich-text, image, filter, date-filter, map.

**RBAC roles:** org `organization_owner` / `organization_admin` / `organization_member`; workspace `workspace_admin` / `editor` / `viewer` / `restricted_user`. There is **no `analyst` role**; authoring is `editor`. Platform admin is a boolean, not a role.

**Workers/jobs:** Redis queues `default,dashboard`; handlers `platform.noop`, `dataset.quality`, `dashboard.export`, `platform.file_lifecycle`. Pipeline runs leased in Postgres. Dashboard export worker + delivery/pipeline scheduler ticks inside the generic worker.

---

## PART 3 — Module scores

Dimensions scored 0–10 then scaled. **80+ would mean deploy-for-pay on this SHA.**

| Module | Functionality | UX | Backend | Reliability | Security | Production | Enterprise | Resell | Overall /100 | Verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Authentication / login / sessions / idle | 8 | 7 | 8 | 7 | 6 | 4 | 3 | 4 | 71 | DEMO READY |
| Forgot / reset password | 6 | 7 | 7 | 6 | 6 | 2 | 1 | 2 | 48 | PARTIAL |
| Profile / settings | 7 | 7 | 7 | 6 | 6 | 4 | 3 | 4 | 66 | DEMO READY |
| Organizations / workspaces / provisioning | 7 | 6 | 8 | 6 | 7 | 3 | 3 | 3 | 64 | PARTIAL |
| Users / RBAC / permissions | 8 | 6 | 8 | 7 | 8 | 5 | 4 | 4 | 76 | PILOT READY |
| Super Admin console | 6 | 6 | 7 | 5 | 4 | 3 | 2 | 2 | 52 | PARTIAL |
| Connections / catalogue | 5 | 5 | 6 | 5 | 6 | 3 | 2 | 2 | 51 | PARTIAL |
| PostgreSQL connector | 8 | 6 | 8 | 7 | 7 | 5 | 4 | 5 | 74 | PILOT READY |
| CSV / XLSX / local file | 7 | 6 | 7 | 6 | 6 | 4 | 3 | 4 | 66 | DEMO READY |
| Datasets / preview / profile | 7 | 6 | 8 | 6 | 7 | 4 | 3 | 4 | 68 | DEMO READY |
| Data Quality | 7 | 6 | 7 | 5 | 6 | 4 | 3 | 3 | 62 | DEMO READY |
| Pipeline Studio / engine | 8 | 6 | 8 | 7 | 7 | 5 | 4 | 4 | 72 | PILOT READY |
| Semantic models | 7 | 6 | 7 | 6 | 7 | 4 | 3 | 4 | 68 | DEMO READY |
| Dashboard builder / persist / publish | 7 | 7 | 8 | 6 | 7 | 5 | 4 | 4 | 70 | DEMO READY |
| Charts / filters / pivot / scatter / tables | 7 | 6 | 7 | 6 | 6 | 4 | 3 | 4 | 66 | DEMO READY |
| Published viewer | 7 | 7 | 7 | 6 | 7 | 4 | 3 | 4 | 66 | DEMO READY |
| Public / anonymous sharing | 0 | 0 | 0 | 0 | n/a | 0 | 0 | 0 | 5 | NOT IMPLEMENTED |
| PDF export | 6 | 5 | 7 | 5 | 6 | 3 | 2 | 3 | 58 | PARTIAL |
| PNG export | 6 | 5 | 7 | 5 | 6 | 3 | 2 | 3 | 56 | PARTIAL |
| Reports module | 1 | 1 | 1 | 1 | 2 | 0 | 0 | 0 | 8 | NOT IMPLEMENTED |
| Scheduling | 6 | 6 | 7 | 5 | 6 | 3 | 2 | 3 | 58 | PARTIAL |
| Email delivery | 2 | 2 | 4 | 2 | 3 | 1 | 0 | 1 | 16 | MOCK / DEVELOPMENT ONLY |
| In-app notifications | 4 | 5 | 4 | 4 | 5 | 2 | 1 | 2 | 38 | PARTIAL |
| Notification preferences | 2 | 4 | 3 | 3 | 4 | 1 | 1 | 1 | 28 | PLACEHOLDER |
| Help & Docs | 5 | 6 | 3 | 5 | 5 | 2 | 2 | 2 | 48 | PARTIAL |
| Audit logs | 8 | 6 | 8 | 7 | 7 | 5 | 4 | 4 | 74 | PILOT READY |
| Favorites | 1 | 3 | 0 | 1 | 2 | 0 | 0 | 0 | 8 | MOCK / DEVELOPMENT ONLY |
| Templates | 1 | 3 | 0 | 1 | 2 | 0 | 0 | 0 | 8 | MOCK / DEVELOPMENT ONLY |
| AI Studio | 0 | 1 | 1 | 1 | 3 | 0 | 0 | 0 | 8 | NOT IMPLEMENTED |
| Automation | 0 | 1 | 0 | 1 | 2 | 0 | 0 | 0 | 5 | NOT IMPLEMENTED |
| Marketplace | 0 | 1 | 1 | 1 | 2 | 0 | 0 | 0 | 6 | NOT IMPLEMENTED |
| Billing | 0 | 1 | 0 | 1 | 2 | 0 | 0 | 0 | 5 | NOT IMPLEMENTED |
| Developer / API product | 2 | 2 | 3 | 2 | 4 | 1 | 1 | 1 | 18 | PLACEHOLDER |
| Feature flags / entitlements | 7 | 5 | 8 | 6 | 7 | 4 | 3 | 3 | 64 | DEMO READY |
| Admin tools | 6 | 6 | 7 | 5 | 5 | 3 | 3 | 3 | 58 | PARTIAL |
| Storage / artifacts | 5 | 3 | 6 | 5 | 5 | 2 | 1 | 2 | 42 | PARTIAL |
| Workers / background jobs | 7 | 3 | 8 | 5 | 6 | 4 | 3 | 3 | 61 | PARTIAL |
| Observability | 4 | 2 | 5 | 4 | 4 | 2 | 1 | 1 | 32 | PARTIAL |
| Security controls (platform-wide) | 6 | 4 | 7 | 5 | 6 | 3 | 2 | 2 | 58 | PARTIAL |

---

## PART 4 — Feature readiness matrix (material items)

| Module | Feature | Status | Evidence | Problem | Severity | Customer impact | Required action | V1 blocker? | Owner |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Auth | Login cookies + CSRF | Connected, persists | Live 200 `POST /auth/login`; `/auth/me` | Compose rate limit 1000/min; Redis fail-open | P1 | Brute force on a mis-copied compose file | Production limits; fail-closed or documented degrade | Pilot | Backend |
| Auth | Forgot password UI | UI + API | Browser `/forgot-password`; API 202 | Copy says “we'll send you a secure link”; transport is file outbox | P0 | Customer waits for email that never arrives | Change copy until SMTP is live; then SMTP | Demo honesty / Pilot | Product + Backend |
| Auth | Reset token | Backend real | `password_reset_tokens`; `.eml` “Reset your Veltrix password” written this run | Not internet email | P0 | Recovery unusable off-laptop | SMTP + DNS | Pilot | Infra |
| Auth | MFA / SSO | Absent | Grep zero SAML/OIDC/TOTP in API/src | Enterprise table-stakes | P2 | Procurement no | Decide V1 “password only” in writing | Enterprise sale | Product |
| Tenancy | Invite | API 201 | Live create; `token` field exists for development | No mail; no `/invitations/accept`; accept requires **already logged-in matching email**; no public signup | P1 | Cannot onboard a user without an operator | Invite email + accept page + join model | Pilot | Full-stack |
| Tenancy | Demo users in helper script | Broken | `demo.admin@vip.example` **suspended** | Current `scripts/demo` helper is a trap | P0 | Demo login fails | Restore or retire script | Demo | Demo ops |
| Catalog | Connector list | Misleading | API **117** types; junk `pg-*` “Postgres” planned; Salesforce etc. visible if unfiltered | Looks like a 100-connector product | P0 | Sales lie even if default filter is Available | Purge test types; never show planned in customer demo | Demo | Backend + Demo |
| Connections | PostgreSQL | Real | Live list 13 connections in QA org | Private-network allow in Compose | P2 | Fine locally | Keep allowlist strict in hosted | Production | Backend |
| Notifications | Feed | Partial | 30 job-derived rows; mark-read 200 | Not an event product; links `/jobs/:id` **no route**; archive is RAM; prefs saved and **ignored** by list and generator | P1 | Badge lies relative to prefs; clicks 404 | Fix links; apply prefs or remove UI; persist archive or remove | Demo | Full-stack |
| Email | All templates | File only | 75–76 `.eml`; latest password reset + dashboard subjects | No Resend/SES/SMTP live | P0 | No invites, no recovery, no scheduled report inbox | SMTP path already coded | Pilot | Infra |
| Dashboards | Export jobs | Partial | 138 completed PDF / 50 PNG; 13+13 failed; 44 export **dead_letter** | Failures not explained to customers; email of export is file | P1 | “Export” ≠ “received email” | Ops on DLQ; don’t demo email | Pilot | Backend |
| Platform admin | Memberships | Dangerous locally | `qa_platform_super_admin` is `workspace_admin` on **dozens** of orgs including named “customers” | Operator is a tenant user everywhere | P1 | Isolation story collapses in console | Separate operator identity; no auto-membership | Pilot | Backend + Ops |
| UI | Sidebar version | Misleading | Hardcoded `VIP · v0.1.0 · hybrid local` in live mode | Looks unfinished / mock | P0 | Client reads “hybrid local” | Bind real version; drop hybrid in live | Demo | Frontend |
| Gated modules | Reports/AI/etc. | Hidden live | `featureAvailability.ts`; AI API 403; reports API `[]` | Empty APIs still 200 if called | P2 | Direct API explorers see stubs | Keep 404; don’t 200 empty “product” | Later | Backend |
| Legal | ToS/privacy/DPA/SLA | Absent | Repo glob zero | Cannot contract | P2 | No signature | Legal pack | Production | Business |

---

## PART 5 — Customer journeys

### Journey 1 — Platform Super Admin

**Not fully executed as a mutating console walk.** Live facts: four `is_platform_admin` users exist (`admin@vip.local`, a personal mailbox, `tenant-a@vip.demo`, `qa_platform_super_admin@vip.qa.local`). Platform login with the documented governance password **failed**. QA platform-admin password from the local helper **failed** in one attempt (stale vault vs hash). Viewer hitting `/api/v1/platform/organizations` returned **404**. Audit table has 39853 events. **Tenant isolation of resources: cross-org dashboard GET → 404 ORGANIZATION_NOT_FOUND.** Platform admin is simultaneously workspace_admin on a large fraction of orgs — that is not a clean super-admin model.

### Journey 2 — Organization Admin

Live login `qa_organization_admin@vip.qa.local` **200**. Sees 1 org `QA_Enterprise_A_20260804`. Tenant-scoped connections/datasets/pipelines/dashboards **200**. Invitation create **201**. Workspace list without org header **400 TENANT_CONTEXT_REQUIRED** (API shape is header-centric).

### Journey 3 — Analyst (editor)

**Not rebuilt end-to-end in the browser this audit.** Database already contains 609 pipelines, 1841 datasets, 35 semantic models, 976 dashboards, 249 successful pipeline runs. That proves the engine has been used; it does **not** prove a clean analyst can do it without this landfill. Pipeline node set is real in code. Semantic query is PostgreSQL-centric per prior code audit.

### Journey 4 — Viewer

Live `qa_workspace_viewer@vip.qa.local` **200**. `POST /pipelines` **403 PERMISSION_DENIED**. Dashboards list **200** (50). Platform console **404**. Browser published-viewer chrome not re-checked this run.

### Journey 5 — Notification lifecycle

Triggering a new job was not required: feed already had 30 items. Mark-read **200**. Unread count endpoint **200**. Feed is **recent jobs**, capped 30, not user-targeted events. Duplicate prevention is “latest jobs,” not a notification idemptotency key. Logout persistence of **read** markers is DB (`notification_reads`) — real. Archive is **not**. Preferences **do not** change generation. Relogin hydrates switches only.

### Journey 6 — Email lifecycle

| Event | Live external email? | What actually happens |
| --- | --- | --- |
| Password reset | **No** | File `.eml` this run; subject “Reset your Veltrix password” |
| User invitation | **No** | Token in API in development; **no send()** |
| Scheduled report | **No** | Dashboard delivery writes `.eml` (subjects such as “UAT Finance Dashboard”) |
| Notification email | **No** | Not implemented |
| Security/account alert | **No** | Not implemented |

Provider: **file outbox**. SMTP class exists unused. **No Resend, SES, or SendGrid client in application code.** Terraform SES is definition-only; **no tfstate**.

**UI FUNCTIONAL, DELIVERY INFRASTRUCTURE INCOMPLETE**

---

## PART 6 — Notification system

**Notification Readiness Score: 38/100**

In-app: derived from `jobs` in tenant scope (`home/routes.py`). Categories mapped from `job_type`. Read state per user. Unread count from same 30-row window. No grouping product, no retention policy beyond job history, no deletion API. “Archive” filters the Vue array. Preferences persist on `users.preferences.notifications` and are **not consulted** by `_notification_feed` or `filtered`. Copy: “Choose which categories deliver alerts to you” is false. Architecture: **synchronous request-time SQL**, not a queue. No retry of notification emit (there is no emit). Auditability: jobs/audit exist; notification itself is a view.

To be production-ready: real event types, recipient rules, persist notifications as rows (or keep derived but stop promising preferences), apply prefs, fix `/jobs` links, optional email channel, worker-side emit for long jobs.

---

## PART 7 — Email

**Email Production Readiness Score: 16/100**

Abstraction: `EmailProvider` with `file` | `smtp` | else 503. Config names that actually exist: `DASHBOARD_EMAIL_PROVIDER`, `DASHBOARD_EMAIL_FROM`, `DASHBOARD_EMAIL_OUTBOX_ROOT`, `DASHBOARD_SMTP_HOST`, `DASHBOARD_SMTP_PORT`, `DASHBOARD_SMTP_USERNAME`, `DASHBOARD_SMTP_PASSWORD`, `DASHBOARD_SMTP_STARTTLS`, `DASHBOARD_SMTP_USE_TLS`, `DASHBOARD_SMTP_TIMEOUT_SECONDS`, `FRONTEND_URL`. There is **no** `EMAIL_PROVIDER` / `RESEND_API_KEY` in code.

No bounce handling, no provider webhook, no rate limit specific to mail, Message-ID domain hardcoded `vip.local`.

### If not live — plan

**Application:** invitation `send()`; stop returning tokens outside development; `/invitations/accept` page; optional password-changed mail; log provider message id without tokens.

**Provider:** Resend SMTP **or** SES SMTP into existing `SmtpEmailProvider`. Do not rewrite on HTTP first.

**DNS:** SPF, DKIM, DMARC, domain/sender verification — **required** for anything other than file.

**Env:** `DASHBOARD_EMAIL_PROVIDER=smtp`, `DASHBOARD_SMTP_*`, `DASHBOARD_EMAIL_FROM`, `FRONTEND_URL`.

**Validation:** request reset against a mailbox you control; confirm inbox + outbox empty of the only copy; invite a second mailbox; fail a bad SMTP password and confirm 503/logs without user enumeration.

---

## PART 8 — Forgot password

UI exists. Token hashed, TTL setting 30 minutes, one-time `used_at`, prior tokens invalidated on new request (code). Uniform 202 for known and unknown identifiers **this run**. Rate limit Redis, **fails open**. Reset confirm revokes sessions (code/tests historically). **Real email: no.**

**UI FUNCTIONAL, DELIVERY INFRASTRUCTURE INCOMPLETE**

---

## PART 9 — Connectors

| Connector | Shown in UI | Backend Exists | Credentials Flow | Test Connection | Metadata Discovery | Data Ingestion | Production Ready |
| --- | --- | --- | --- | --- | --- | --- | --- |
| PostgreSQL | Yes | Yes | Yes | Yes | Yes (PG) | Yes | **Pilot, not SaaS-prod until hosted** |
| Local file / CSV | Yes | Yes | Upload | N/A | Parse | CSV/TSV/TXT | Demo/pilot with ClamAV |
| XLSX | Via file | Yes first sheet | Upload | N/A | Parse | Yes | Same |
| MySQL | Yes if not filtered | Beta ping | Yes | Beta | Limited | Not GA | No |
| MSSQL | Yes | Beta | Yes | Optional driver | Limited | Not GA | No |
| Snowflake | Yes | Beta | Yes | Optional | Limited | Not GA | No |
| BigQuery | Yes | Beta | SA JSON | Optional | Limited | Not GA | No |
| S3 | Yes | Beta head-bucket | Yes | Beta | Limited | Not GA | No |
| REST API | Yes | Beta HEAD + SSRF guards | Yes | Beta | No product ingest | Not GA | No |
| Salesforce, Oracle, SAP, Kafka, Power BI, … | Catalog cards | **No** | No | No | No | No | No |
| `pg-*` junk rows | API yes | Test leftovers | — | — | — | — | **Defect** |

### REAL V1 CONNECTORS
PostgreSQL; local file CSV/XLSX (and related text).

### PLACEHOLDER / FUTURE
Everything else, including all beta types for a paying V1 unless a specific customer contract names one beta and staffs it.

**Misleading catalogue is a product defect**, even with an “Available” default filter, because “all” and API still enumerate a fake estate (117 types this run).

---

## PART 10 — Pipeline engine

**Pipeline Engine Score: 72/100**

Live: 249 succeeded runs, worker healthy, schedules table populated (`cert-live` enabled daily). This audit did **not** author a new 12-node canvas in the browser.

| Node | Works | Correct Output | Good UX | Handles Errors | Production Ready |
| --- | --- | --- | --- | --- | --- |
| source-dataset | Yes (code + run volume) | Assumed from succeeded runs | Studio exists | Validation APIs exist | Pilot locally |
| select-columns | Yes | Yes if configured | Adequate | Partial | Pilot |
| rename-columns | Yes | Yes | Adequate | Partial | Pilot |
| filter | Yes | Yes | Adequate | Partial | Pilot |
| sort | Yes | Yes | Adequate | Partial | Pilot |
| join | Yes | Depends on config | Harder UX | Partial | Pilot with care |
| union | Yes | Depends | Harder | Partial | Pilot with care |
| aggregate | Yes | Depends | Adequate | Partial | Pilot |
| formula | Yes | Language endpoint exists | Developer-ish | Partial | Pilot |
| row-validation | Yes | Yes | Adequate | Better than most | Pilot |
| type-convert | Yes | Depends | Adequate | Partial | Pilot |
| deduplicate | Yes | Yes | Adequate | Partial | Pilot |
| null-handling | Yes | Yes | Adequate | Partial | Pilot |
| output-dataset | Yes | Yes | Adequate | Partial | Pilot |
| file-export | Yes | Artifacts volume 261 files | Adequate | Partial | Local storage only |

Row cap `PIPELINE_RUN_MAX_ROWS=100000`. Not hyperscale. `mockOutputSchema()` in UI is empty-array hint only.

---

## PART 11 — Data quality

**Data Quality Score: 62/100**

Code, jobs `dataset.quality`, UI `/datasets/quality`, 9 Stage 4 evaluations claimed historically. **This audit did not run 10 / 100 / 1k / 10k profiling.** Do not upgrade to production on that absence. API fan-out and browser memory at 10k: **NOT VERIFIED this run.**

---

## PART 12 — Dashboards & analytics

**Dashboard & Analytics Score: 70/100**

Commercially: a **narrow V1** versus Power BI/Tableau (no certified semantic marketplace, weak storytelling, no public embed, no mobile app, map/widget depth unknown this run, templates mock). Good enough to **show** governed widgets from PostgreSQL semantics. Not enough to displace an incumbent BI estate.

Live list 50 dashboards in one QA workspace — the product stores real definitions. Publishing/export job pipeline exists. Cross-filter: not verified this run.

---

## PART 13 — Export

Historical DB: PDF 138 completed / 13 failed; PNG 50 / 13; also json/csv. **PDF Export Score: 58/100.** **PNG Export Score: 56/100.** Visual clipping, branding, accessibility metadata, blank-PNG races: **not visually re-tested this run.** Dead-letter **44 export jobs** is a reliability signal. Emailing the artifact is file-outbox, not inboxes.

---

## PART 14 — Scheduling

**Scheduling Score: 58/100**

Means: DB schedules for **pipeline runs** and **dashboard deliveries** (cron/daily/weekly/monthly/one-time, IANA timezone, pause, `FOR UPDATE SKIP LOCKED` in worker). UI exists. `cert-live` enabled with `next_run_at` 2026-08-25 12:41 UTC and a prior `last_run_at`. Many `stale-schedule-cert` paused. Dashboard deliveries: 19 rows.

Does **not** currently mean: email in a customer inbox; a separate always-on scheduler replica (container absent); proven missed-run catch-up after 20h host sleep (workers show 20h uptime this boot — **NOT a restart drill**). Duplicate-fire in multi-worker production: **NOT VERIFIED** (local single worker).

---

## PART 15 — Workers

Queues: Redis `vip:jobs` default+dashboard; pipeline leases in Postgres; DLQ table used (44 export dead letters). Heartbeats persist **stale rows** (58 heartbeat records, many “running” from July). If worker down: exports/schedules/pipeline runs stall; API still serves. Dashboard worker uses **noop** malware scanner while API uses ClamAV — split brain.

---

## PART 16 — Security

**Security Score: 58/100**

**P0**
- Password-recovery UX promises email that is not delivered off-box.
- Connector catalogue pollution + planned connectors present as a catalogue.
- Sidebar “hybrid local” in live mode.
- Demo helper accounts suspended (demo ops / credential confusion).
- OpenAPI `/docs` exposed on this development deployment (expected for APP_ENV, forbidden for a client-facing host).

**P1**
- Login/reset rate limit **fails open** if Redis is down.
- Compose `AUTH_LOGIN_RATE_LIMIT_PER_MINUTE=1000`.
- Invitation token returned in development responses.
- Platform admin seeded as workspace_admin across customer-named orgs.
- Default Compose encryption/download-signing keys are well-known placeholders.
- `show-full-platform-qa-credentials.ps1` dumps plaintext passwords to stdout.
- Historical markdown in `docs/reports` contains plaintext demo passwords.
- No MFA/SSO.
- File storage local only; path traversal is guarded in code but not a hosted bucket.
- Notification deep-link to nonexistent `/jobs/:id`.

**P2**
- CSRF/CORS localhost defaults.
- AUTH_COOKIE_SECURE false.
- Personal mailbox present as platform admin in this DB.
- Users with empty email exist.
- No WAF in front of localhost.
- Metrics endpoint exists (token-optional depending on config).

**P3**
- No pentest evidence on this SHA.
- Stale worker heartbeat rows.

Positive (do not treat as production hosting proof): cookie sessions, CSRF on mutations, lockout settings, hashed reset tokens, cross-tenant 404 this run, viewer 403 on pipeline create, connection secrets encrypted at rest in app design, ClamAV on API ingest.

---

## PART 17 — Production infrastructure gap

**No internet-facing VIP exists in this audit.** Terraform under `infra/aws/` is **unapplied** (no tfstate in repo). Local restore drill doc is historical and **not** AWS PITR.

### REQUIRED BEFORE PRIVATE CLIENT DEMO
Clean tenant (not 85-org landfill); working presenter users; hide planned connectors; hide hybrid local; don’t claim email; HTTPS not required for a conference-room localhost **if** the story is “local demo.” Prefer a dedicated machine/DB snapshot.

### REQUIRED BEFORE PILOT
Hosted URL + TLS; SMTP; backups you have restored; staging vs prod; secrets not Compose defaults; workers+scheduler monitored; malware policy consistent; invitation/onboarding path; written limitations.

### REQUIRED BEFORE FIRST PAYING PRODUCTION CUSTOMER
Managed Postgres+Redis; persistent file storage; SMTP/SES with DNS; monitoring/alerting; on-call; legal pack; backup RPO/RTO tested; environment separation; deploy/rollback actually used; disable docs; secure cookies; rate limits; operator access model.

### CAN WAIT UNTIL SCALE
K8s, multi-region, 90 connectors, AI/marketplace/billing, per-tenant AWS accounts, SOC 2 (start evidence now, don’t block a paid pilot SOW if legal agrees).

---

## PART 18 — Productization / resell

**Resell/Productization Score: 21/100** (category 24 / resell 21)

### Resell Readiness Matrix

| Area | Current State | Required State | Gap | Priority |
| --- | --- | --- | --- | --- |
| V1 boundary | Gated in live UI; login splash lists 5 pillars | Written capability sheet + known limitations PDF | Partial | P0 |
| Navigation | Coherent if gated | Same + no hybrid local | Sidebar | P0 |
| Onboarding | Operator-created users | Invite email + accept | Large | P1 |
| Tenant provisioning | API + console | Runbook + clean install | Dirty DB | P1 |
| Branding | VIP cube | Versioned, not hybrid | Sidebar | P0 |
| Auditability | Strong locally | Retain in prod | Hosted | P2 |
| Customer docs | In-app help articles | Admin+user PDFs | Thin | P1 |
| Legal | Absent | ToS, privacy, DPA | Absent | P2 |
| Pricing/packaging | No | SKU + limits | Absent | P2 |
| SLA | None | Pilot SOW hours | Absent | P2 |
| Deployment docs | Runbooks exist; SHA drift (`4e97591…` vs HEAD) | Match HEAD | Stale | P1 |
| Upgrade/handover | Undefined | Version + notes | Absent | P2 |

---

## PART 19 — Enterprise sales risk

| Enterprise Question | Current Answer | Acceptable for V1? | Required Improvement |
| --- | --- | --- | --- |
| Where is my data stored? | This laptop’s Docker volume. No customer region. | No | Hosting statement |
| Isolated? | App RBAC yes; this DB is a shared landfill; platform admin in many orgs | App yes / env no | Clean tenants + operator model |
| Can your employees access my data? | Super-admin boolean; no documented access control | No | Access policy |
| If platform is down? | No SLA, no status page | No | Pilot SOW |
| Backups? | Local dump scripts historically; no managed backup | No | RDS backup + restore evidence |
| Encrypted? | TLS not on localhost; secrets encrypted in DB design; cookies not Secure | Partial | TLS + Secure cookies |
| Real connectors? | PostgreSQL + files | Yes if honest | Capability sheet |
| SLA? | None | No | Don’t sell SLA yet |
| SSO? | No | Only if waived | Roadmap |
| MFA? | No | Weak | Optional TOTP later |
| Audit logging? | Yes, 39k events locally | Yes for V1 | Retention policy |
| Private host? | Terraform exists, not applied | Definition only | Paid professional services |
| Updates? | Git/CI; no live pipeline proof on this SHA | No | Deploy once for real |
| Scheduled reports? | Jobs + file email | No as “email” | SMTP |
| Email delivery? | File | No | SMTP |
| User invite? | API, no mail, no accept UI | No | Build |
| User leaves? | Memberships/removed_at exist | Partial | Document deprovision |
| Data deletion? | Archive/delete APIs exist in domains | Partial | Document + test |
| Support? | None operational | No | Named human |
| Compliance? | None certified | No | Don’t claim ISO/SOC |

---

## PART 20 — Competitive V1 expectation

### MUST HAVE FOR V1
Honest connector list; hosted HTTPS; SMTP recovery+invite; RBAC that matches demo; PostgreSQL+file analytics path; publish dashboard; export file download; audit log; backup; on-call email; written limits; clean tenant.

### SHOULD HAVE SOON AFTER V1
SSO or MFA; one extra warehouse (customer-driven); notification prefs that work; scheduled email that arrives; object storage; status page.

### V2
Broader connectors, semantic marketplace, better BI, usage billing.

### V3 / LONG TERM
AI studio, automation fabric, 90 connectors, multi-region.

Do not build AI/Marketplace/Billing now.

---

## PART 21 — UI / UX

**UI/UX Product Score: 64/100**

Login and forgot-password are visually professional (browser this run). Splash claims multi-tenant / encrypted secrets / governed access — **partially true in app, false as a hosted product**. Forgot-password copy overclaims delivery. Authenticated shell not fully walked; sidebar hybrid local is amateur on a sales screen. Gating of unfinished modules is the correct UX decision. Empty states/loading: login uses a long branded spinner (observed). Notification archive and prefs are prototype behavior.

---

## PART 22 — Dead / fake / misleading surfaces

| Surface | Problem | User Could Misinterpret It As | Required Action |
| --- | --- | --- | --- |
| Sidebar `hybrid local` | Hardcoded in live | Product is a mock | Remove |
| Forgot password copy | Promises email | Inbox delivery | Relabel until SMTP |
| Connector catalog 117 types / `pg-*` | Test junk + planned | 100 GA connectors | Purge; filter; sales script |
| Login “Multi-tenant” badges | True in code, false as SaaS | Hosted multi-tenant SaaS | Don’t say hosted |
| Notification prefs | Switches do nothing to delivery | Channel control | Wire or remove |
| Notification “Open job” | `/jobs/:id` missing | Broken product | Link to pipeline/dashboard |
| Archive | Not persisted | Mail-client archive | Persist or remove |
| Reports/insights/marketplace API `[]` | 200 empty | Module exists | 404 |
| Favorites/templates | Mock-only | Features exist if env flipped | Keep gated; delete mock IDs |
| Billing mock $4800 | If mock mode | Real billing | Keep gated |
| `scripts/demo` credentials | Suspended users | Demo is ready | Fix data or script |
| Docs with passwords | Credential leak in git | Security maturity | Rotate + purge history later |
| Stage 4 “A certified” paper | Yesterday’s grade | This SHA is market-ready | This audit supersedes |
| Version `0.1.0` + null commit SHA | No build identity | Unreleased | Stamp SHA at build |

---

## PART 23 — Observability & operations

**Operations Supportability Score: 28/100**

“If a customer calls at 10 PM saying their scheduled report did not arrive, can support determine exactly what happened?”

**No.** Locally an engineer can query `dashboard_delivery_runs`, jobs, worker logs, and the file outbox. There is no shared log backend, no email provider dashboard, no paging, no customer-facing delivery id in an inbox. File outbox is not an inbox. Dead-letter exports exist without an operator UI in this audit walkthrough.

---

## PART 24 — Backup & DR

**No production backup strategy is in force.** Historical local `pg_dump` drill is not RDS PITR. Redis AOF is compose-local. Uploads/exports live on Docker volumes. **RPO/RTO: not defined, not tested on this SHA.** If the laptop disk dies, the customer data on it dies.

---

## PART 25 — Performance & scale

| Customer | Fit on this architecture |
| --- | --- |
| Small (1 org, PG, tens of dashboards) | Locally plausible |
| Medium | Pipeline 100k row cap, query byte caps, local disks: **tight** |
| Large | **No** |

Bottlenecks: single-node local storage, in-request notification queries, dashboard query concurrency settings, export worker failures (44 DLQ), 85-org noisy DB. Concurrent user test: **not run**. 10k DQ: **not run**.

---

## PART 26 — Documentation

**Documentation Score: 48/100**

Lots of internal QA/certification markdown (often **SHA-stale**). In-app help covers connect/pipeline/dashboard at a high level. **No** customer privacy/terms. Developer README/env examples exist. Infra runbooks exist but cite older certified SHAs (`4e97591…`). That volume of paper is not the same as a current customer/admin manual.

---

## PART 27 — Demo / seed dependency

A sellable platform must provision empty. **This runtime cannot be shown as empty.** 85 orgs, e2e clients, UAT tenants, Stage 4 fictionals, QA_Enterprise_*. CLI demo seeds exist and are blocked outside dev. `scripts/demo` users **suspended**. Stage 4 users `must_change_password=true`. Hardcoded favorites IDs in mock-only views. **Clean install: not executed this audit.**

---

## PART 28 — Clean install / redeployability

**Deployment Reproducibility Score: 55/100** for **local compose**; **12/100** for **hosted production**.

A new engineer can likely bring up compose from README + `.env.example` **if** Docker and secrets are supplied. They will not reproduce this database. Workers/scheduler/storage paths are documented in compose. Health checks exist. **Production apply: never verified.**

---

## PART 29 — Final scorecard

| Category | Score /100 |
| --- | ---: |
| Product Functionality | 62 |
| UX / UI | 64 |
| Data & Analytics | 68 |
| Pipeline Engine | 72 |
| Dashboarding | 70 |
| Authentication | 71 |
| RBAC / Tenant Isolation | 76 |
| Notifications | 38 |
| Email | 16 |
| Scheduling | 58 |
| Export | 61 |
| Security | 58 |
| Reliability | 55 |
| Performance | 52 |
| Infrastructure Readiness | 18 |
| Operations | 28 |
| Documentation | 48 |
| Enterprise Readiness | 22 |
| Productization | 24 |
| Resell Readiness | 21 |

# VIP TOTAL PRODUCT READINESS SCORE: 49/100

### Demo Readiness: 58/100
### Pilot Readiness: 41/100
### Production Readiness: 19/100
### Enterprise Readiness: 17/100
### Resell Readiness: 20/100

---

## PART 30 — Verdict

### E — INTERNAL DEMO READY ONLY

A trained internal presenter can show PostgreSQL → dataset → pipeline → semantic → dashboard on this laptop **if** they stay inside a prepared tenant and do not open catalogue-all, platform console, notification job links, or claim email/hosting.

This is **not** a client-demo-ready **product state**: advertised demo users are suspended, the database is a QA landfill, the UI says hybrid local, email is a disk folder, and nothing is on the public internet.

Prior Stage 4 “A — ENTERPRISE DEMO ENVIRONMENT CERTIFIED” is **not** adopted.

---

## PART 31 — What must be done next

## P0 — MUST FIX IMMEDIATELY

| Problem | Why | Action | Files | Size | Who |
| --- | --- | --- | --- | --- | --- |
| Demo helper users suspended | Demo script logs in to dead accounts | Re-enable dedicated demo users **or** point scripts at Stage 4 after force-password-change; never both | `scripts/demo/*`, DB | S | Manual + Grok |
| Sidebar `hybrid local` | Sales-visible mock label | Show `APP_VERSION` + git SHA; omit hybrid when `apiMode=live` | `src/app/shell/AppSidebar.vue` | XS | Grok |
| Forgot-password copy vs file email | False delivery promise | Honest copy (“link generated; email provider not configured”) until SMTP | `ForgotPasswordView.vue` | XS | Grok |
| Catalogue junk `pg-*` + 117 types | Looks like 100 GA connectors | Delete leftover `connection_types`; default Available; sales forbid All | DB + `connections/catalog.py` | S | Claude Sonnet |
| Notification → `/jobs/:id` | Instant 404 | Point at pipeline run or dashboard export | `home/routes.py` | S | Claude Sonnet |

## P1 — BEFORE FIRST CUSTOMER PILOT

| Problem | Why | Action | Files | Size | Who |
| --- | --- | --- | --- | --- | --- |
| No SMTP | Recovery/invite/reports | `DASHBOARD_EMAIL_PROVIDER=smtp` + DNS | email.py already; env | M | Manual Infra |
| No invite accept UI / no send | Cannot onboard | Send mail; add `/invitations/accept`; decide logged-in vs signup | `tenancy/services.py`, router | L | Claude Opus |
| Prefs don’t affect notifications | Dishonest settings | Apply or remove | `NotificationsView.vue`, `home/routes.py` | S | Grok |
| Platform admin in every tenant | Isolation story | Strip extra memberships; operator path only | DB + bootstrap | M | Product + Backend |
| Compose secrets/rate limits | Unsafe if copied | Fail production validator (already partly); never ship 1000/min | `docker-compose.yml` | S | Manual |
| Export DLQ 44 | Silent failure | Operator view + alerting | jobs UI | M | Claude Sonnet |
| Hosted URL/TLS | Not a service | Cloudflare/ALB as designed | `infra/aws` apply | L | Manual Infra |
| Stale runbook SHAs | Ops follows wrong revision | Stamp HEAD | `docs/operations/*` | S | Grok |
| Password files in git docs | Credential hygiene | Remove plaintext; rotate those passwords | `docs/reports/*` | S | Manual |
| Clean demo DB | 85 orgs | Dedicated demo volume/snapshot | ops | M | Manual |

## P2 — BEFORE FIRST PAID PRODUCTION CUSTOMER

Backups+restore test, object storage, secure cookies, disable docs, Sentry/uptime, on-call, DPA/ToS/privacy, MFA or written waiver, malware scanner consistent on workers, build SHA injection, legal SOW, staging environment.

## P3 — NEXT PRODUCT

Working notification product; one extra connector by customer demand; SSO; better BI; status page.

## DO NOT BUILD YET

AI Studio, Automation, Marketplace, Billing, 90 connectors, custom white-label email, Kubernetes, SOC 2 theatre without customers, Resend HTTP rewrite (use SMTP).

---

## PART 32 — Live activation checklist

| Item | App supports? | External setup? | Exact action | Blocking |
| --- | --- | --- | --- | --- |
| Production domain | Via `FRONTEND_URL` / CORS / CSRF / TRUSTED_HOSTS | Yes | Register domain | Production |
| DNS | No | Yes | A/CNAME to LB | Production |
| TLS | HSTS in prod middleware | Yes | Cert on proxy | Production |
| Frontend URL | Yes | Yes | Set `FRONTEND_URL` | Pilot |
| API URL | Yes | Yes | CORS allowlist | Pilot |
| PostgreSQL | Yes | Yes | Managed PG; not laptop volume | Pilot |
| Redis | Yes | Yes | Managed Redis AUTH/TLS | Pilot |
| Storage | Local only | Yes for prod | Keep EFS/disk for V1 or implement S3 later | Pilot |
| Workers | Yes | Yes | Run dashboard + pipeline workers | Demo (local already) |
| Scheduler | Tick in job worker | Yes | One worker process must run; don’t assume separate container | Pilot |
| Secrets | Yes | Yes | Non-default keys | Pilot |
| CORS/CSRF | Yes | Yes | Exact origins | Pilot |
| Email provider | SMTP class | Yes | Provider + `DASHBOARD_EMAIL_PROVIDER=smtp` | Pilot |
| Verified domain | No | Yes | Provider console | Pilot |
| SPF/DKIM/DMARC | No | Yes | DNS | Pilot |
| Monitoring | `/health` `/ready` `/metrics` | Yes | Uptime + log drain | Production |
| Backups | Dump exists as skill | Yes | Automated + restore drill | Production |
| Error tracking | Logs only | Yes | Sentry or equivalent | Production |
| Migrations | Alembic | Yes | One-head deploy job | Pilot |
| Admin user | Platform create user | Yes | Bootstrap then rotate | Pilot |
| Org provisioning | API | Yes | Empty org, not QA landfill | Pilot |

**Making notifications “real”:** they already persist read-state; they are not a message bus. Fix links/prefs; do not wait for Kafka.

**Making emails real:** SMTP env + DNS; then reset/invite/delivery use the same provider.

**Background jobs:** already real **if workers run**. This host has them.

**Storage persistent:** Docker volumes persist until `volume rm`. That is not customer durability.

**Internet reachable:** not configured.

---

## PART 33 — Commercial product checklist

### Required before sales conversations
Product name (VIP/Veltrix — consistent); demo script that does not claim email/AWS/100 connectors; V1 capability sheet; known limitations sheet; working **internal** demo tenant; honest login story.

### Required before pilot
Onboarding questionnaire; named support; invite path; hosting statement; backup statement; written V1 limits; DPA draft if processing personal data.

### Required before contract signature
ToS; privacy; DPA; security overview; architecture one-pager; data hosting; SLA **or explicit no-SLA pilot SOW**; pricing; proposal template.

### Can follow after first customers
Public website polish; marketing site; SOC 2; marketplace; billing automation; multi-language UI.

Assessed missing: product website as a company property, pricing, SLA, DPA, privacy, terms, incident process as an operating org (runbooks ≠ a staffed IR function).

---

## PART 34 — CEO summary

1. **Can I confidently demo VIP to a customer today?** **No** as the product currently sits (suspended demo users, landfill DB, hybrid local, email folder). **Yes only** as a tightly scripted internal demo on a prepared tenant with a presenter who will not open the catalogue or claim hosting/email.
2. **Free trial today?** **No.** No self-serve, no email, no hosted URL.
3. **Charge today?** **No** as SaaS. A **paid pilot SOW** would be a business choice against unpaid operational risk, not a product fact.
4. **Host a real customer today?** **No.** Terraform unapplied; laptop Docker is not hosting.
5. **Email operational?** **No.** File outbox. SMTP coded, unused.
6. **Notifications operational?** **Partially.** Job feed + read flags. Not a notification product. Prefs are cosmetic.
7. **Scheduling operational?** **Partially locally.** Schedules fire inside the job worker; they do not deliver email.
8. **Biggest technical weakness:** **Transactional email + hosted runtime** (SMTP/DNS/TLS/backups), not the pipeline SQL engine.
9. **Biggest product weakness:** **Honesty of surface area** (connectors, hybrid local, password email, notifications).
10. **Biggest commercial weakness:** **No packagable offer** (legal, hosting, support, V1 boundary PDF, onboarding).
11. **Top 5 next:** (1) Honest demo environment + UI labels (2) SMTP + invite/reset (3) Dedicated hosted staging (4) Purge catalogue junk / operator memberships (5) Legal+limits PDF.
12. **Do not build:** AI, Automation, Marketplace, Billing, connector sprawl.

---

## PART 35 — Repeatability

Package: `docs/certification/final-product-audit/`.
Collector: `python scripts/certification/collect-baseline.py` or `make product-certification` or `.\scripts\certification\run-product-certification.ps1`.
Live probe: `python scripts/certification/live_api_probe.py` with env credentials (**never commit**).
Future reports: new files under `reports/`; do not overwrite this file.

---

## PART 36 — Regression comparison

Previous public market audit (23 Aug 2026, SHA `dfb74af3…`, Docker **down**, score 51, verdict **C PILOT READY**) is **not** a like-for-like live run. This run had a live stack and is **stricter**.

| Metric | Previous (23 Aug paper) | Current (25 Aug live) | Change |
| --- | ---: | ---: | --- |
| Total readiness | 51 | 49 | -2 |
| Demo readiness | (implied higher than live ops) | 58 | n/a live |
| Pilot readiness | C / ~50 | 41 | down |
| Production readiness | ~20s (infra missing) | 19 | ~flat |
| Enterprise readiness | ~25 | 17 | down |
| Resell readiness | ~31 productization cited | 20 | down |
| P0 count | not comparable | **8** | — |
| P1 count | — | **16** | — |
| P2 count | — | **18** | — |
| Backend tests this run | not run (Docker down) | not run | n/a |
| Frontend tests this run | not run | not run | n/a |
| Browser tests | not run | partial manual | + |
| Notification score | “prod in app” claimed | **38** | restated down |
| Email score | incomplete | **16** | restated |
| Security score | mixed | **58** | restated |
| Productization score | 31 | **24** | down |

The platform did **not** become a hosted product in two days. Live inspection **lowered** confidence in demo hygiene (suspended users, 117 connector types, notification prefs, hybrid local).

---

*End of baseline certification for `fa02d9e2484f6b603efe5af9e7586975342b485c`.*
