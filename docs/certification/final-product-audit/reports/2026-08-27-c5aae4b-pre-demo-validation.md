# VIP pre-demo platform validation

Independent run against the live local stack. Not a prior certification reuse.

- Date: 2026-08-27
- Branch: `feat/vip-productization-p2`
- HEAD: `c5aae4b560800c947f5e45e8912f85c60aa8e3cd` (`fix: keep demo credentials login-ready`)
- Working tree: **DIRTY** (docs/certification moves, Makefile, scripts, untracked demo/cert files)
- Verdict: **C — INTERNAL DEMO READY**

No application behavior was changed to improve scores. Small live probes created extra pipeline/export jobs and password-reset outbox files.

---

# 1. Starting baseline

| Item | Value |
| --- | --- |
| Branch | `feat/vip-productization-p2` |
| HEAD | `c5aae4b560800c947f5e45e8912f85c60aa8e3cd` |
| Working tree | Dirty |
| Frontend runtime | Vite 6.4.3 on `:3009` (preview after `npm run dev` crashed watching `playwright-report`) |
| Backend runtime | `vip-api-1`, Python 3.12.13, healthy, `:8000` |
| PostgreSQL | `vip-postgres-1` healthy, `:5432` |
| Redis | `vip-redis-1` healthy, PONG |
| Workers | `vip-dashboard-worker-1` (job worker + embedded schedulers), `vip-pipeline-worker-1` — both healthy |
| Scheduler | No dedicated container. Ticks run inside the dashboard/job worker. Defaults enabled; compose does not set scheduler env vars |
| Migrations | Alembic current = `20260808_0025` |
| Alembic heads | Single head `20260808_0025` |
| Application environment | `APP_ENV=development`, version `0.1.0`, `commit_sha=null` |
| Email | `DASHBOARD_EMAIL_PROVIDER=file`, SMTP host empty |
| Demo environment | Stage 4 / Stage 2 reset: 3 synthetic tenants. Credentials in DPAPI under `%LOCALAPPDATA%\Veltrix\VIP\stage4\` |

Counts at audit start (then mutated by probes):

| Object | Count |
| --- | ---: |
| Organizations | 3 |
| Workspaces | 9 |
| Users | 25 (all `active`, `must_change_password=false`) |
| Connections | 9 |
| Datasets | 21 |
| Pipelines | 9 |
| Semantic models | 9 |
| Dashboards | 9 |
| Published dashboards | 9 |
| Jobs | 16 (later 18) |
| Pipeline schedules | 0 |
| Dashboard delivery schedules | 3, all `enabled=false` / `status=paused` |
| Dashboard delivery runs | 0 |
| Notification reads | 17 (later 19) |
| Audit events | 2010 |
| Dead-letter jobs | 0 |
| Pipeline runs | 9 succeeded (later 10) |

**Database classification: CLEAN DEMO**

Not QA landfill. No `QA_Enterprise_*`. No suspended `demo.admin@vip.example` users. Remaining contamination: 15 leftover `pg-*` / `pg-sem-*` / `dc-pg-*` / `por-pg-*` **connection types** (`is_enabled=false`), plus 78 `.eml` files in the local file outbox.

---

# 2. Test suites

## Backend

Host: `apps/api/.venv`, Python 3.14.4 running tests; API container is 3.12.13.

| Invocation | Result |
| --- | --- |
| `pytest -m "not integration"` | **1 failed**, 304 passed, 25 skipped, 104 deselected, 21.86s |
| `RUN_INTEGRATION_TESTS=1 pytest -m integration` | **104 passed**, 330 deselected, 212.58s |
| `RUN_INTEGRATION_TESTS=1 pytest tests/integration/test_export_semantic_parity.py tests/integration/test_tenancy.py` | **31 passed**, 47.35s (these were skipped in the unit run because they lack `@pytest.mark.integration`) |

**Failure:** `tests/unit/test_stage4_demo_provisioning_contract.py::test_stage4_provisioner_has_multiple_fail_closed_guards`

The contract still requires `must_change_password=$true` in `provision-enterprise-demo.ps1`. HEAD `c5aae4b` sets `$false` so demo users can log in. Product intent and unit contract disagree.

Approximate backend total if combined: **439 passed, 1 failed**, plus the 25 skip/deselect accounting overlap. Not a green suite.

## Frontend

| Command | Result |
| --- | --- |
| `npm run lint` | pass (exit 0) |
| `npm run typecheck` | pass |
| `npm test` | **426 passed / 70 files**, ~34.6s |
| `npm run build` / `build:only` | pass, ~12s |

## Browser / E2E

`playwright.config.ts`: retries = 0, workers = 1, projects include chrome, edge, firefox, webkit, high-dpi, mobile.

**Full historical matrix (`tests/e2e/run-local-certification.ps1`) was not runnable.** It requires `QA_Enterprise_A_20260804` / `QA_Enterprise_B_20260804` and QA DPAPI personas. Those tenants are gone after Stage 2/4 reset.

**Stage 4 demo spec** (`tests/e2e/stage4-enterprise-demo.spec.ts`) **was run** on Chrome, Firefox, and WebKit after installing Playwright browsers.

| Browser | Admin journey | Viewer journey |
| --- | --- | --- |
| chrome-desktop | Failed at export dialog locator | Not run (serial) |
| firefox-desktop | Same | Not run |
| webkit-desktop | Same | Not run |

The admin journey **reached** org/workspace chrome, connection test, dataset + Quality tab, 16-node pipeline, published semantic model, dashboard reload, Share → Export. Failure:

```
strict mode violation: getByText('PDF export') resolved to 3 elements
```

Cause: this audit created extra PDF exports; the dialog now lists multiple historical “PDF export” rows. This is a brittle spec, not a broken exporter. API PDF/PNG both completed.

`scripts/demo/run-browser-certification.ps1` uses `ConvertFrom-Json -Depth 40`, which **fails on Windows PowerShell 5.1**. The suite was launched by setting env vars without `-Depth`.

`npm run dev` crashed when Playwright wrote `playwright-report/` (Vite `EBUSY` file watch). Preview was used afterward.

---

# 3. V1 module inventory

| Module | Status | Score /100 | Main issue | Demo safe? |
| --- | --- | ---: | --- | --- |
| Authentication | DEMO READY | 78 | No MFA/SSO; reset is file-outbox; UI vs API invalid-login copy | Yes |
| Login | DEMO READY | 80 | Copy says “Invalid email or password”; API says username or password | Yes |
| Forgot Password | PARTIAL | 55 | Honest UI; still writes `.eml`; OpenAPI still promises email | Yes if explained |
| Password Reset | PARTIAL | 52 | Confirm API exists; no customer email; no in-product admin complete-reset UX in this walk | Avoid live reset |
| Session Handling | DEMO READY | 76 | Cookie + CSRF live; idle TTL 30m not wait-tested this run | Yes |
| Idle Timeout | DEMO READY | 70 | Configured (`AUTH_SESSION_IDLE_TTL_MINUTES=30`); not sat through | Yes |
| Profile | DEMO READY | 72 | Settings profile/security/sessions exist | Yes |
| Settings | DEMO READY | 70 | MFA card correctly “Not available” | Yes |
| Organizations | DEMO READY | 78 | Org admin sees 1 org / 3 workspaces; platform admin sees 3 | Yes |
| Workspaces | DEMO READY | 78 | Switcher and admin APIs live | Yes |
| Users | DEMO READY | 74 | Members list 9 in Northstar; invite has no mail/UI accept | Yes |
| Roles | DEMO READY | 75 | `GET /roles` returned 7 | Yes |
| RBAC | DEMO READY | 80 | Viewer 403 on pipeline create; editor URL fail-closed in spec | Yes |
| Super Admin | DEMO READY | 78 | `vip.demo.platform.admin` lists 3 orgs / 25 users | Yes |
| Organization Admin | DEMO READY | 76 | Platform routes 404 for org admin | Yes |
| Workspace Admin | DEMO READY | 74 | Present in demo personas | Yes |
| Connections | DEMO READY | 70 | PostgreSQL test succeeded; catalog still 117 types | Yes if filter=Available |
| PostgreSQL | DEMO READY | 82 | Health=healthy, test=success, full journey | Yes |
| File Upload | DEMO READY | 72 | Catalog `available` with malware_scan; not re-uploaded this run | Yes |
| Datasets | DEMO READY | 78 | Preview 25×17 in 207ms | Yes |
| Data Preview | DEMO READY | 78 | Works | Yes |
| Data Profiling | PARTIAL | 60 | Quality/profile exist; flagship raw score 0 | Explain score 0 |
| Data Quality | PARTIAL | 62 | Live; largest table ~603 rows; curated outputs `not_evaluated` | Explain, don’t linger on Sales raw |
| Pipeline Studio | DEMO READY | 78 | 16-node flagship saved/executed | Yes |
| Pipeline Nodes | DEMO READY | 76 | 15 kinds in registry; union unused in demo graph | Yes |
| Pipeline Execution | DEMO READY | 80 | New run 202 → succeeded (~5s) | Yes |
| Semantic Models | DEMO READY | 76 | Published v2 | Yes |
| Dashboard Builder | DEMO READY | 74 | Studio exists; demo dashboards already published | Yes |
| Dashboard Viewer | DEMO READY | 78 | Viewer GET 200 | Yes |
| Publishing | DEMO READY | 80 | 9/9 published | Yes |
| PDF Export | DEMO READY | 78 | Live 202 → completed | Yes |
| PNG Export | DEMO READY | 78 | Live 202 → completed | Yes |
| Scheduling | PARTIAL | 42 | 3 paused deliveries; 0 pipeline schedules; 0 delivery runs | Do not present as live email |
| Notifications | PARTIAL | 48 | Derived from last 30 jobs; prefs unused | Show carefully |
| Notification Preferences | PARTIAL | 35 | Persist on user JSON; list does not filter | Do not claim enforcement |
| Audit Logs | DEMO READY | 75 | 50-item page live | Yes |
| Help & Docs | DEMO READY | 65 | Sidebar footer `/help`; tooltip mentions “API reference” | Yes |
| Reports | HIDDEN | 20 | Gated to not-found; API still returns `[]` | No |
| AI Studio | HIDDEN | 15 | Gated; `/api/v1/ai/assistants` 403 FEATURE_DISABLED | No |
| Automation | HIDDEN | 15 | Gated | No |
| Billing | HIDDEN | 15 | Gated | No |
| Marketplace | HIDDEN | 18 | Gated UI; API `[]` | No |
| Developer/API | HIDDEN | 20 | Gated | No |
| Feature Flags | DEMO READY | 68 | Admin page exists | Optional |
| Insights / Explore | HIDDEN | 15 | Gated | No |
| Favorites / Templates | HIDDEN | 10 | `developmentMockOnly` | No |
| Invitations | PARTIAL | 40 | Backend create/accept; no `/invitations/accept` UI; token only in development | No as a product flow |
| Email | PLACEHOLDER | 25 | File provider only | No as “email works” |

---

# 4. Category scores

| Category | /100 |
| --- | ---: |
| Authentication | 78 |
| User Management | 72 |
| RBAC | 80 |
| Tenant Isolation | 85 |
| Connections | 70 |
| File Upload | 72 |
| Datasets | 78 |
| Data Quality | 62 |
| Pipeline Studio | 78 |
| Pipeline Engine | 80 |
| Semantic Layer | 76 |
| Dashboarding | 74 |
| Publishing | 80 |
| PDF Export | 78 |
| PNG Export | 78 |
| Notifications | 48 |
| Notification Preferences | 35 |
| Scheduling | 42 |
| Email | 25 |
| Audit Logs | 75 |
| Admin Experience | 72 |
| Settings | 70 |
| Help & Docs | 65 |
| UX/UI | 72 |
| Reliability | 70 |
| Security | 68 |
| Performance | 75 |
| Demo Readiness | 72 |
| Production Readiness | 38 |
| Enterprise Readiness | 32 |
| Resell Readiness | 28 |

# TOTAL PLATFORM SCORE: 65/100

Mean of the 31 category scores. Not inflated: core governed path works; commercial/ops surfaces do not.

---

# 5. Demo journeys

IDs used: Northstar org `c2cec199-…`, flagship workspace `924dc94a-…` (Sales & Commercial).

## Journey A — Platform / org administrator

| Check | Result |
| --- | --- |
| Org admin login | 200, `must_change_password=false`, not platform admin |
| Organizations | 1 item (Northstar) |
| Workspaces | 3 |
| Members | 9 |
| Roles | 7 |
| Platform org list as org admin | 404 RESOURCE_NOT_FOUND |
| Platform admin login | 200 |
| Platform orgs / users | 3 orgs, 25 users |

## Journey B — Analyst (primary)

Connection → dataset → preview → quality → pipeline → execute → semantic → dashboard → publish (already published) → PDF → PNG.

| Step | Evidence |
| --- | --- |
| Connection | PostgreSQL, health=healthy, last_test=success |
| Test connection | 200 |
| Dataset | Sales Transactions — Synthetic Raw |
| Preview | 200, 25 rows, 17 columns, 207ms |
| Quality | 200 in 205ms; evaluation **failing, score 0** |
| Pipeline | 16 nodes including join, quality gate, both sources, output, file-export |
| Execute | POST 202; poll succeeded |
| Semantic | published, version 2 |
| Dashboard viewer | 200; widgets kpi×4, bar, line, table, donut, column |
| PDF | 202 → completed |
| PNG | 202 → completed |

Playwright on three browsers walked the same path through Share → Export.

## Journey C — Viewer

| Check | Result |
| --- | --- |
| Login | 200 |
| Dashboard viewer | 200 |
| Create pipeline | 403 PERMISSION_DENIED |
| PUT editor with junk body | 422 validation (not a clean 403; body was invalid) |
| Foreign dashboard in own tenant | 404 DASHBOARD_NOT_FOUND |
| Foreign org headers | 404 ORGANIZATION_NOT_FOUND |
| Browser viewer spec | Not executed (serial abort after admin locator fail) |

## Journey D — Notifications

| Check | Result |
| --- | --- |
| Generated from activity | Yes — last 30 jobs, not a notification table |
| Hardcoded feed | No |
| After exports | Sample title `Dashboard export (PNG): succeeded` |
| Category | **System** (job_type is `export`, mapper expects `dashboard_export`) |
| Link | `/jobs/{id}` which **redirects to `/activity`** |
| Unread / mark read / mark all / relogin | APIs 200; unread persisted via `notification_reads` |
| Preferences | Saved to user JSON; **`filtered` ignores them** |
| Archive | Client-side only |
| Email | None |

## Journey E — Scheduling

| Check | Result |
| --- | --- |
| Visible product | “Scheduled Deliveries” in nav |
| What it does today | Persists dashboard email/PDF/PNG schedules; worker tick exists |
| This database | 3 schedules, paused, `next_run_at=null`, **0 runs** |
| Pipeline schedules | 0 |
| Timezone | `Asia/Riyadh` stored |
| Failure behavior | Not exercised (would need enable + real/file send) |
| Worker dependency | Yes — dashboard-worker |
| Delivery today | File provider; enabling would write `.eml`, not customer mail |

A form that saves is not production scheduling.

---

# 6. Complex pipeline

Reused Northstar flagship **Commercial Revenue Quality and Target Attainment** (16 nodes). Did not invent a second graph.

**Registry (all product-supported nodes):**

source-dataset, select-columns, rename-columns, filter, sort, join, union, aggregate, formula, row-validation, type-convert, deduplicate, null-handling, output-dataset, file-export.

| Node | In flagship | Works | Correct | Persisted | Error handling | Demo safe |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| source-dataset (×2) | yes | yes (run succeeded) | assumed via succeeded run | yes | not isolated | yes |
| select-columns | yes | yes | not independently verified | yes | not isolated | yes |
| rename-columns | yes | yes | not independently verified | yes | not isolated | yes |
| filter | yes | yes | not independently verified | yes | not isolated | yes |
| sort | yes | yes | not independently verified | yes | not isolated | yes |
| join | yes | yes | not independently verified | yes | not isolated | yes |
| union | **no** | registry + engine exist | **not executed this run** | n/a | n/a | only if you add it first |
| aggregate | yes | yes | not independently verified | yes | not isolated | yes |
| formula (×2) | yes | yes | not independently verified | yes | not isolated | yes |
| row-validation | yes | yes | not independently verified | yes | not isolated | yes |
| type-convert | yes | yes | not independently verified | yes | not isolated | yes |
| deduplicate | yes | yes | not independently verified | yes | not isolated | yes |
| null-handling | yes | yes | not independently verified | yes | not isolated | yes |
| output-dataset | yes | yes | curated row estimate 598 | yes | not isolated | yes |
| file-export | yes | yes | run succeeded | yes | not isolated | yes |

Per-node UI add/configure/reopen was not repeated; persistence is proven by GET returning 16 nodes after a previous provision, then a successful execute.

---

# 7. Dashboard

Flagship: **Sales and Commercial Performance Dashboard** (published).

| Type | On demo dashboard | Notes |
| --- | ---: | --- |
| KPI | yes (4) | Total Orders, Total Revenue, Average Margin Score, Average Fulfillment Hours |
| Bar | yes | Revenue by Region |
| Line | yes | Revenue Trend |
| Table | yes | Regional Performance Detail |
| Donut | yes | Revenue by Product Category |
| Column | yes | Cost by Status |
| Pivot | no | Supported in builder/tests; **not on this dashboard** |
| Scatter | no | Supported in builder/tests; **not on this dashboard** |

Filters present in Stage 4 provisioning (date, region, category, status). Playwright saw Date and Region. Numbers were not fully recomputed against SQL in this run. Pipeline processed ~7.8k rows historically vs dataset `row_count_estimate` 603 — **do not treat estimates as source of truth on stage**.

Save/reload: Playwright reloaded dashboard with no error banner. Publish: already published. Viewer: API 200. PDF/PNG: completed.

---

# 8. Data quality

**Data Quality Score: 62/100**

| Size | Result |
| --- | --- |
| 10 | Lookup targets have 5 rows; not a profile showcase |
| 100 | Not a distinct fixture |
| ~600 | All main raw/curated tables. Preview/quality ~200ms, no freeze |
| 1,000 / 10,000 | **Not present. Not run.** Would require loading data |

Flagship raw **Sales Transactions** evaluation: score **0**, status **failing**:

- unique business identifier: 3 issues
- non-negative primary value: 1 issue
- not_null business identifier: 1 issue
- region accepted_values: 1 warning

That is useful if you want to show quality gates. It is a trap if you imply the demo warehouse is clean.

8/9 other evaluations are score 100. Curated outputs are mostly `quality_status=not_evaluated`.

No evidence of frontend freeze or backend fan-out at this size.

---

# 9. Notification system

**Notification Score: 48/100**

Answers:

| Question | Answer |
| --- | --- |
| Generated from system activity? | Yes — jobs |
| Hardcoded? | No |
| Preferences persist? | Yes, user.preferences.notifications |
| Preferences enforced? | **No** |
| Unread persist? | Yes, `notification_reads` |
| Links valid? | `/jobs/:id` redirects to activity (not a job page) |
| Dedup? | Feed is last 30 jobs; id includes row_version so updates can look new |
| Survive logout/login? | Yes |
| Depend on workers? | Indirectly (jobs must exist) |
| Email notification? | No |
| Email disabled? | File provider; notification path does not send mail |

Still needed: real notification records, preference enforcement, correct category mapping for `export`/`system` job types, durable archive, non-job events (invites, security), email optional.

---

# 10. Email

### Can VIP send a real external email today?

**NO**

Providers in code: `file`, `smtp`. No Resend/SES classes. Current compose: `DASHBOARD_EMAIL_PROVIDER=file`, empty SMTP host. Password reset wrote to `/data/vip-email-outbox` (78 `.eml` files including this audit).

| Email use case | Backend exists | Real delivery | Missing work |
| --- | ---: | ---: | --- |
| Password reset | Yes (`send_password_reset_email`) | File `.eml` only | SMTP/Resend/SES, templates ops, UI honesty vs OpenAPI |
| Invitation | Create/accept API; **no send** | No | Mailer, public accept page, logged-out accept |
| Scheduled report/dashboard | Delivery worker + file/smtp | Not in this DB (paused; 0 runs) | Enable + real provider + history |
| Notification | No mail path | No | Product decision |
| Security/account alerts | Not a separate product | No | Product decision |

OpenAPI for `/password-reset/request` still says a reset **email is delivered**. The forgot-password **page** says contact an org admin.

Invitations return the raw token only when `APP_ENV` is development/test.

---

# 11. Connector catalogue

Live `GET /connections/types`: **117** types.

| Connector | Visible | Backend | Full analytics journey | Status |
| --- | ---: | ---: | ---: | --- |
| postgresql | yes | yes | **Yes** (this run) | REAL V1 |
| local_file | yes | yes (upload/scan) | Not re-run; catalog available | REAL V1 |
| mysql | yes (beta) | ping/read/metadata | Not run | BETA |
| mssql | yes (beta) | ping/read | Not run | BETA |
| snowflake | yes (beta) | ping/read | Not run | BETA |
| bigquery | yes (beta) | ping/read | Not run | BETA |
| s3 | yes (beta) | ping/read | Not run | BETA |
| rest_api | yes (beta) | ping/read | Not run | BETA |
| Remaining ~101 | if filter=All | catalog metadata | No | ROADMAP |
| `pg-*` leftovers (15) | if filter=All | none | No | BROKEN / MISLEADING |

Default catalog filter is **Available** (2 types). Do not click All statuses in a demo.

Test-connection ≠ full journey. Only PostgreSQL was proven Connection → Dataset → Pipeline → Semantic → Dashboard.

### REAL V1
postgresql, local_file (CSV/XLSX)

### BETA
mysql, mssql, snowflake, bigquery, s3, rest_api (enabled)

### ROADMAP
planned / requires_agent / requires_driver majority of the 117

### BROKEN / MISLEADING
leftover `pg-*` connection_type rows

---

# 12. Demo data quality

### Is this database acceptable to show during a team demo?

**YES** — with the warnings below. It is no longer a QA landfill.

Clean before a **client** meeting (do not delete in this audit):

1. Hide or delete leftover `pg-*` connection types so All statuses cannot embarrass you.
2. Do not open Data Quality on **Sales Transactions — Synthetic Raw** unless you want a score of 0.
3. Do not enable the three paused weekly briefs (file outbox / no real mail).
4. Do not show notification preferences as if they hide categories.
5. Working tree is dirty; demo from this SHA, not from uncommitted doc churn.
6. Users are `@example.com` — fine internally, not a customer tenant.

No QA orgs, no suspended helper users, no duplicate orgs, no `demo.organization.admin` in the user table.

---

# 13. UI / UX

Walked login (screenshot), forgot-password (screenshot + submit), and Playwright flagship screens. Hybrid pill is `config.apiMode === 'mock'` only — not on live.

| Surface | Flag |
| --- | --- |
| Login | Polished; invalid-login copy still says “email” |
| Forgot password | Honest admin copy; submit works; OpenAPI still overclaims |
| Home | API summary 200 |
| Sidebar | Product label “Veltrix Intelligence Platform”; Help in footer |
| Topbar | No Hybrid pill in live |
| Org/workspace switch | Present; org admin has one org |
| Connections | OK if Available filter kept |
| Catalog All | 117 cards including leftover keys — **misleading** |
| Pipeline studio | Flagship graph present |
| Semantic | Published |
| Dashboard | 9 widgets; no error on reload |
| Notifications | Job feed; prefs theater |
| Settings | MFA “Not available” is honest |
| Admin | Platform vs org split works |
| Help | Exists; tooltip “API reference” overreaches if developer portal is gated |
| Gated modules | Direct URL → not-found in live mode |

Vite `npm run dev` watching Playwright output is an operator footgun, not a customer UX bug.

---

# 14. Security / RBAC

Safe tests only.

| Test | Result |
| --- | --- |
| Invalid password | 401 INVALID_CREDENTIALS, generic |
| Unknown user | 401 same (no account oracle) |
| Session cookies | Login sets CSRF; tenant headers required |
| Dashboard without tenant | 400 TENANT_CONTEXT_REQUIRED |
| Cross-org dashboard as Northstar admin | 404 ORGANIZATION_NOT_FOUND |
| Viewer foreign dashboard | 404 |
| Viewer create pipeline | 403 |
| Org admin platform API | 404 |
| Password reset | 202 uniform; file outbox |
| Idle | Config 30m; not wait-tested |
| IDOR via other-org headers | No data returned |

No MFA/SSO. Invitation accept requires an already-authenticated matching user. APP_ENV=development leaks invite tokens in API responses.

---

# 15. Performance (demo-scale)

| Action | Observation |
| --- | --- |
| Login / org APIs | Immediate |
| Preview 25 rows | 207ms |
| Quality summary | 205ms |
| Pipeline run | Succeeded on first 5s poll |
| PDF/PNG create | 113–152ms to 202; completed on first polls |
| Notification list | 6 items, immediate |
| Dataset scale | ~600 rows — not a load test |

Nothing in this dataset is too slow for an internal demo. Do not imply 10k/enterprise scan performance.

---

# 16. Broken routes / dead buttons

| Route / action | Result | Issue |
| --- | --- | --- |
| `/jobs/:id` | Redirect `/activity` | Notification “Open job” is not a job page |
| `/reports`, `/ai/*`, `/billing`, `/marketplace`, `/automation`, `/explore` | not-found in live UI | Correctly hidden; APIs still 200 `[]` or 403 |
| `/favorites`, `/dashboards/templates` | Hidden in live | Mock-only |
| `/invitations/accept` | **No frontend route** | Config default still points here |
| Catalog filter All | Shows leftover `pg-*` | Misleading |
| Notification archive | Local only | Reloads restore item |
| Notification prefs switches | Save toast | Do not change the list |
| `Forgot password` OpenAPI | Claims email | Contradicts UI |
| Full QA E2E script | Cannot start | Wrong tenants |
| `run-browser-certification.ps1` on PS 5.1 | `ConvertFrom-Json -Depth` | Operator break |
| Login error string | “Invalid email or password” | Username is the primary identifier |

---

# 17. Missing (V1-relevant only)

## A. Discuss with the team now

- Real email vs admin-reset vs no self-service reset
- Invitation: mail + public accept vs admin-created users only
- Connector promise: PostgreSQL+file only vs marketing 117
- Notification product vs job activity feed
- Scheduling: in-app only vs email delivery
- Hosting: local compose vs HTTPS customer environment
- Trial/onboarding without Stage 4 DPAPI
- SSO/MFA timing
- Reports / AI / Automation / Billing / Marketplace: keep hidden or fund them

## B. Technical gaps before live pilot

- SMTP/SES/Resend actually configured and monitored
- Hosted HTTPS, backups, restore rehearsal, `commit_sha` in `/version`
- APP_ENV not development
- Invitation flow end-to-end
- Remove leftover connection types
- Notification preference enforcement or remove the UI
- Align DQ score 0 story or recertify flagship raw
- Dedicated ops for workers/scheduler (compose has no scheduler service)
- Contract test vs `must_change_password=$false`

## C. Commercial / product gaps before selling

- Packaging: what is V1 vs roadmap
- Support model, SLA, data retention
- Legal/security pack (SSO, DPA, pentest)
- Customer onboarding without engineers decrypting DPAPI
- Pricing
- Production identity (version still 0.1.0)

## D. Can wait for V2

- AI Studio, Automation, Marketplace, Billing, Insights, Explore
- 90+ connectors
- Pivot/scatter on the flagship dashboard (engine already has them)
- Favorites, dashboard templates
- Union node in the demo graph

---

# 18. Team discussion agenda

| Topic | Current situation | Decision needed | Recommended direction |
| --- | --- | --- | --- |
| Email provider | File outbox only | File / SMTP / SES / Resend | Pick one real provider before any external demo that mentions email |
| Self-service reset | UI: call admin. API: writes `.eml`. OpenAPI: “email delivered” | Admin-only vs real mail | Match OpenAPI, UI, and ops to one story |
| Invitations | API without mail or accept page | Admin-provisioned users vs invite links | Do not sell invites until accept UI + mail exist |
| Connectors | 2 available, 6 beta enabled, 117 listed | What sales may say | Sell PostgreSQL + file; beta only if a named customer asks |
| Scheduling | Paused file deliveries | In-app schedule vs emailed PDF | Keep paused; don’t demo “email every Monday” |
| Notifications | Job feed + unused prefs | Activity feed vs notification product | Call it activity; remove prefs or enforce them |
| Demo environment | Clean 3-tenant Stage 4 | This DB vs a clone for client days | Freeze a restore point; don’t mix QA E2E into it |
| Hosting | Local compose, APP_ENV=development | Shared demo host vs per-customer | No paid customer on this compose stack |
| SSO/MFA | Password only; MFA labeled unavailable | When | After first supervised pilot, unless a CISO blocks |
| Hidden modules | Reports/AI/Automation/Billing/Marketplace gated | Keep hidden vs build | Keep hidden for V1 |
| Password policy on demo users | `must_change_password=false` vs unit test `$true` | Login-ready vs fail-closed seed | Login-ready for demo; fail-closed for production seed |

---

# 19. Bug / gap register

| ID | Module | Finding | Severity | Demo blocker? | Pilot blocker? | Action |
| --- | --- | --- | ---: | ---: | ---: | --- |
| PD-01 | Email | No external delivery | P1 | No | Yes | Provider + templates + monitoring |
| PD-02 | Invitations | No mail, no accept UI | P1 | No | Yes | Build or drop from V1 |
| PD-03 | Notifications | Prefs persist, not applied | P2 | No | Yes if sold | Enforce or remove |
| PD-04 | Notifications | `export` jobs categorized System | P3 | No | No | Map job types |
| PD-05 | Catalog | 15 leftover `pg-*` types | P2 | No if filter kept | Yes | Purge types |
| PD-06 | Data Quality | Flagship raw score 0 | P2 | No if scripted | No | Script or recertify |
| PD-07 | Auth | OpenAPI promises reset email | P2 | No | Yes | Fix contract text |
| PD-08 | Auth | Login error says “email” | P3 | No | No | Copy |
| PD-09 | Tests | Unit contract vs `$false` must_change | P2 | No | No | Align test |
| PD-10 | E2E | QA matrix incompatible with demo DB | P2 | No | No | Separate suites |
| PD-11 | E2E | Stage 4 spec strict on PDF labels | P3 | No | No | Use `.first()` / role |
| PD-12 | Tooling | PS 5.1 `-Depth` breaks cert script | P2 | No | No | Remove `-Depth` |
| PD-13 | Dev | Vite crashes on playwright-report watch | P3 | No | No | Ignore folder |
| PD-14 | Scheduling | Paused, zero runs, file provider | P1 | No | Yes for emailed reports | Don’t sell |
| PD-15 | Versioning | `0.1.0`, `commit_sha=null` | P2 | No | Yes | Build metadata |
| PD-16 | Security | No MFA/SSO | P2 | No | Depends on customer | Roadmap |
| PD-17 | API | Gated modules still return empty lists | P3 | No | No | 404 to match UI |
| PD-18 | Help | Tooltip claims API reference | P3 | No | No | Copy |
| PD-19 | DQ | No 1k/10k fixtures | P2 | No | Yes for scale claims | Dataset + tests |
| PD-20 | Invite tokens | Returned in development API | P2 | No | Yes if APP_ENV stays development | Never in customer env |

---

# 20. Demo blockers

# DEMO BLOCKERS

**No technical blocker prevents an internal team demo.**

Use Northstar Sales & Commercial. Do not improvise email, invites, or “117 connectors.”

# DEMO WARNINGS

- Catalog filter must stay **Available**
- Data Quality on Sales Transactions is score **0**
- Notifications are a job feed; prefs do not filter
- Scheduled deliveries are paused and would not send real mail
- Do not click Reports / AI / Automation / Billing / Marketplace
- Forgot-password does not email the user
- Version footer is not a release number
- Extra PDF rows appear in export history after this audit
- `npm run dev` can die if Playwright writes reports into the repo

---

# 21. What to demo

## SAFE TO DEMO

- Login (org admin, viewer, platform admin)
- Org / workspace / members / roles
- PostgreSQL connection + Test connection
- Dataset preview
- Pipeline studio + run of the 16-node flagship
- Semantic model published
- Dashboard viewer (KPI, bar, line, table, donut, column) + filters
- Publish state
- PDF and PNG export
- Audit log page
- Platform admin console (3 tenants)
- Tenant isolation story (viewer cannot open Crestline dashboard)
- Settings / MFA “not available” if asked honestly

## DO NOT DEMO YET

- Real email, invites, password reset as a customer feature
- Connector catalog with All statuses
- MySQL/Snowflake/S3/etc. as V1
- Notification preferences as a product
- Enabling weekly dashboard email
- Reports, AI, Automation, Billing, Marketplace, Explore, Favorites
- Pivot/scatter unless you add widgets first
- Union node unless you build it live
- 10k-row quality / performance claims
- SSO/MFA
- Production hosting / commit SHA / 0.1.0 as a shipped version

---

# 22. Final readiness scores

### Internal Team Demo Readiness: 78/100

### External Client Demo Readiness: 55/100

### Trial Readiness: 35/100

### Production Readiness: 38/100

### Resell Readiness: 28/100

---

# 23. Final verdict

### C — INTERNAL DEMO READY

Not B: email, invites, catalog leftovers, notification theater, and no hosted production story.

Not A: a paying customer cannot be operated on this SHA as-is.

---

# 24. Executive summary

1. **Can I demo VIP to my team now?** Yes, as a scripted internal demo on the Stage 4 Northstar tenant.
2. **Avoid showing:** email, invitations, catalog All, notification prefs, paused schedules, gated modules, Sales-raw quality score 0 unless you explain it.
3. **Strongest part:** governed analyst path on PostgreSQL — connection, dataset, 16-node pipeline execute, semantic publish, dashboard, PDF/PNG — plus tenant isolation.
4. **Weakest part:** anything that requires outbound email or a real notification/scheduling product; connector catalogue honesty at filter=All.
5. **Bugs that should stop the demo?** No. The Stage 4 Playwright failure is a locator after extra exports, not a dead exporter.
6. **Top 5 technical gaps:** real email transport; invitation accept UX; leftover `pg-*` types; notification prefs unused; APP_ENV/development + null commit SHA.
7. **Top 5 product decisions:** email strategy; invite vs admin-provisioned users; connector V1 scope; notifications vs activity; keep Reports/AI/Automation/Billing hidden.
8. **Before an external client demo:** purge leftover types; freeze a restore; script around DQ score 0; never say email/117 connectors; hosted HTTPS if they will click around unattended.
9. **Before a free trial:** real email or no self-service accounts; invitation or documented admin onboarding; non-development APP_ENV; backups; support path; no file-outbox.
10. **Before the first paid customer:** hosted production, monitoring, backup/restore, identity (at least MFA plan), legal/security answers, email that works, a defined V1 connector list, and an environment that is not this local compose volume.
