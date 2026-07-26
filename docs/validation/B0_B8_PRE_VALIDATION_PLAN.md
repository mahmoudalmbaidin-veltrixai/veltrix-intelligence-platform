# VIP Backend B0–B8 Pre-Validation Plan

## 1. Executive objective

This is the final enterprise quality, security, operability, and regression gate for the implemented
VIP backend phases B0 through B8 before Phase B9 begins. The gate will inspect the repository and
running system, execute the established local CI-equivalent suite, exercise critical workflows
manually, fix legitimate B0–B8 defects with regression coverage, and issue an evidence-based B9
go/no-go verdict. It will not add B9 functionality or replace established architecture.

## 2. Repository assessment

| Item | Baseline |
| --- | --- |
| Repository | `C:\Users\MahmoudAlmbaidin\Downloads\VIP` |
| Branch | `main` |
| Commit | `33a8356da18b5d74831f2a79b727a73779900f50` |
| Remotes | None configured; hosted GitHub Actions cannot presently be triggered or inspected |
| Working tree | Extensively dirty with pre-existing modified, deleted, and untracked frontend/backend files |
| Preservation rule | Do not discard, reset, overwrite, or reformat unrelated user changes |
| Recent history | B0–B7/backend integration and frontend QA/remediation commits through `33a8356` |
| Backend | FastAPI package in `apps/api`, Python `>=3.12,<3.15` |
| Frontend | Vue 3/Vite at repository root; npm scripts are authoritative |
| CI | `.github/workflows/quality-gate.yml` with frontend, browser, backend, integration, and container jobs |
| Migration topology | One linear head: `20260725_0008`; B0 base through B8 |
| Test inventory | 61 test/spec files and approximately 251 statically discovered test declarations |

The current dirty state materially limits any claim of a clean release commit. All validation will
run against the exact current workspace state, and the final report will distinguish pre-existing
changes from gate-specific changes.

## 3. Environment status

| Component | Current state / planned use |
| --- | --- |
| Host | Windows, PowerShell, Asia/Riyadh |
| Git | 2.55.0 |
| Docker / Compose | Docker 29.6.1; Compose 5.3.0 |
| Host Python | 3.14.4; container/CI contract remains Python 3.12-compatible |
| Node / npm | Node 24.18.0; npm 11.16.0 |
| Package manager | `package-lock.json` and `npm ci` are CI-authoritative; a pnpm lock also exists and will be reviewed for drift |
| PostgreSQL | `postgres:17.5-alpine`, healthy, host port 5432 |
| Redis | `redis:8.0.3-alpine`, healthy, persistent AOF, host port 6379 |
| API | Healthy at `http://localhost:8000`; `/health`, `/ready`, and version all return 200 |
| Generic worker | `dashboard-worker`, generic B8 job worker, healthy |
| Pipeline worker | Separate B7 execution worker, running |
| Storage | Local provider and named Docker volume in development |
| Malware scanner | Development `noop`; production configuration is expected to reject it |
| Email | File/outbox provider in Docker development |
| Dashboard/pipeline artifacts | Tenant-qualified local named volumes |
| Frontend | Dependencies installed; build/E2E server will use established Playwright configuration |
| OpenAPI | Development-enabled; generated schema will be scanned for duplicate IDs and sensitive fields |
| Personas | Tenant A/B/C and governance admin/editor/viewer/restricted fixtures; passwords supplied only by environment |

## 4. Phase-by-phase scope and test matrix

| Phase | Components, APIs, entities, workers, UI | Permissions and security boundaries | Automated and manual tests | Failure scenarios | Exit criteria |
| --- | --- | --- | --- | --- | --- |
| B0 | FastAPI lifecycle, configuration, PostgreSQL, Redis, Alembic, health/readiness/version, logging, middleware, Docker, CI | Fail-closed production settings, redaction, safe correlation IDs/errors, non-root runtime | Ruff/format/MyPy/pytest; Compose/build/start; HTTP health, readiness, version, malformed request, 404; dependency-outage tests | PostgreSQL/Redis unavailable, invalid correlation ID, invalid production config, startup/shutdown | Single migration head; clean startup; dependency-aware readiness; safe logs/errors; all quality gates pass |
| B1 | Users, sessions, reset-token foundation; login/me/refresh/logout; frontend auth store | Cookie flags, CSRF, token hashing/rotation/revocation, lockout/rate limits, safe identity response | Auth unit/integration/E2E tests; login/logout/bootstrap/refresh; cookie inspection; role/session attack cases | Wrong/unknown/disabled/locked user, fixation, replay, stale refresh, expired/revoked session, CSRF bypass | Authentication and revocation work; no raw secret persistence/logging; 401/403 semantics correct |
| B2 | Organizations, workspaces, memberships, invitations, tenant context, tenant frontend store | Organization/workspace membership; tenant-qualified repositories, foreign-key and cache boundaries | Tenancy integration and E2E isolation matrix; switching and cache reset; CRUD/invitation flows | Cross-tenant UUID guesses, foreign child IDs, duplicate/malformed tenant headers, stale context | Every scoped access is tenant/workspace checked and non-disclosing; context/audit correct |
| B3 | Roles, permissions, mappings, flags, entitlements, quotas, authorization dependencies, audit, governance UI | Backend-authoritative permission/feature/entitlement/quota enforcement | Policy/unit/integration/E2E role matrix; route-policy review; audit checks | Viewer/editor bypass, disabled feature, missing entitlement, quota reached/released, direct API bypass | All declared routes governed; admin/editor/viewer/restricted behavior matches policy; critical decisions audited |
| B4 | Connection catalog/CRUD/test/rotation/health; encrypted credential versions; connection UI | Write-only secrets, AES-GCM integrity, provider boundary, SSRF/TLS/redirect policy, tenant scope | Security/unit/integration/E2E connection tests; response/OpenAPI/log/DB inspection | Wrong key, tampered ciphertext, failed rotation, private/loopback/metadata/unsafe scheme, foreign secret | No plaintext disclosure; SSRF fails closed; production requires encryption; tenant scope and audits pass |
| B5 | Datasets, fields, discovery, quality, lineage, semantic models/metrics/KPIs/glossary/query; dataset/semantic UI | Read-only bounded queries, foreign reference rejection, sanitized provider errors | Contract/unit/database integration and frontend tests; safe query and validation workflows | Invalid metric/filter/grouping, foreign connection/model, excessive rows/columns/bytes, timeout, driver error | Contracts validate; queries are read-only/bounded/scoped; lineage reflects actual success only |
| B6/6.5 | Dashboards/pages/widgets/layout/filter/version/share/snapshot; exports/delivery/cache; dashboard UI | Immutable publish, optimistic concurrency, share membership/levels, signed one-use downloads, tenant-qualified cache | Dashboard unit/integration/E2E; editor/publish/view/share/export/download/schedule; generic-job linkage | Stale save, draft leak, privilege escalation, expired/reused/guessed token, cache collision, job cancellation/retry | Persistence/publish/share/query/export work; downloads secure; B8 generic jobs used; no legacy duplicate queue |
| B7 | Pipelines/nodes/edges/canvas/versions/runs/logs/results/artifacts; pipeline worker/UI | Safe formula AST, immutable run version, secrets worker-only, tenant scope, leases/terminal-state protection | Pipeline unit/integration/E2E; graph validation/publish/run/retry/cancel/recovery/artifact | Cycle/missing node/invalid edge, arbitrary code/SQL/shell/path, duplicate claim, lease expiry, false lineage | Graph and formula safety pass; durable asynchronous execution and recovery; protected results; correct lineage |
| B8 | Generic jobs/attempts/events/dead letters; files/versions/scans/downloads; SSE/metrics; generic worker | Idempotency tenant scope, bounded payload/result, leases, file/path/MIME/signature checks, scanner fail-closed, one-use bound tokens, authenticated scoped events | Platform unit/integration/manual API tests; worker interruption; file/download/SSE flows; metrics | Retry storm, timeout, cancellation race, worker/Redis restart, traversal/disguise/oversize, scanner outage, stale event ID | Durable jobs and recovery; safe files/scans/downloads; authenticated resumable SSE; no duplicate side effects |

## 5. Cross-phase workflow matrix

| Flow | Planned evidence | Expected result |
| --- | --- | --- |
| Login → governed workspace | HTTP/cookies, tenant context, permissions, flags, entitlements, quotas, audit/correlation | Correct persona context with no stale tenant authorization |
| Connection → dataset → semantic query | Encrypted DB row, connection test, dataset/schema/model/query response and audit | Credentials remain undisclosed; query is bounded and read-only |
| Dataset → dashboard → export | Draft/published versions, widget response, snapshot, job/attempt/events, PDF/PNG/JSON/CSV artifacts, download reuse attempt | Published-only output, observable generic job, single-use scoped download |
| Dataset → pipeline → output/lineage | Graph validation, immutable digest, run/node/log state, output artifact/dataset/lineage | Worker-only secret use, durable execution, lineage only on success |
| Controlled generic-job failure | Attempts, safe error, retry/backoff, dead letter, retry/discard audit | Bounded retries and authorized recovery |
| Worker interruption | Heartbeat, lease timestamps, worker stop/start, final attempts/side effects | Expired work reclaimed without duplicate terminal side effect |
| Tenant isolation attack | HTTP statuses for every B2–B8 resource family and SSE | All foreign access fails safely without existence disclosure |
| Role matrix | Admin/workspace admin/editor/viewer/restricted/anonymous expected-vs-actual table | Backend matches declared policy regardless of UI controls |

## 6. Security test matrix and risk priorities

| Priority | Area | Planned checks |
| --- | --- | --- |
| Critical | Authentication | Hash strength, cookie/CSRF/session rotation/replay/revocation/lockout, production fail-closed |
| Critical | Tenant/workspace isolation | Repository filters, composite constraints, foreign references, UUID guessing, cache/jobs/events/download tokens |
| Critical | Authorization/governance | Route coverage, direct API bypass, role/feature/entitlement/quota enforcement, denied audits |
| Critical | Secrets and SSRF | Encryption/nonces/tamper/wrong-key, no response/log/audit/schema leakage, scheme/IP/redirect/TLS policy |
| Critical | Jobs/retries/recovery | Atomic claim, leases, idempotency, bounded retry/dead letter, cancellation, terminal state |
| Critical | Files/malware/downloads | Streaming bounds, path/MIME/extension/signature, scanner production policy, infected/pending denial, one use and scope |
| Critical | Pipelines/exports/migrations/audit | AST and immutable versions, generic export jobs, migration round-trip/drift, lifecycle audit integrity |
| High | SSE and cache | Authentication, scoped filtering/resume/cleanup; fully qualified cache keys/invalidation |
| High | Injection/arbitrary execution | Raw SQL, formulas, HTML/JS/shell/subprocess, unsafe deserialize, path traversal |
| High | Logging/OpenAPI | Recursive redaction, safe public errors, operation ID uniqueness, response schema disclosure |
| Medium | Payload/query bounds | Pagination, row/column/byte/time limits, upload/name bounds, queue backlog |
| Medium | Frontend state/accessibility | Logout/switch cache clearing, protected routes, conflict/error states, keyboard/axe checks |
| Low | Cosmetic/operational recommendations | Non-blocking UX polish, dashboards/alerts, future provider recommendations |

## 7. Role and tenant matrix

The test fixture will use Alpha and Beta organizations, multiple workspaces, tenant users A/B/C,
and governance admin/editor/viewer/restricted personas. For representative read, create, update,
publish/run, share/manage, and delete/cancel operations, expected outcomes are:

| Persona | Own tenant/workspace | Foreign tenant/workspace | Privileged mutations |
| --- | --- | --- | --- |
| Organization admin | Allowed subject to feature/entitlement/quota | Denied/non-disclosing | Organization and workspace management allowed |
| Workspace admin | Allowed in assigned workspace | Denied/non-disclosing | Workspace management allowed; organization-only operations denied |
| Editor | Read/create/update/run where policy grants | Denied/non-disclosing | Manage/share/admin and unauthorized publish denied |
| Viewer | Read/view/interact where granted | Denied/non-disclosing | Mutations denied |
| Restricted user | Minimal declared reads only | Denied/non-disclosing | Mutations and restricted modules denied |
| Unauthenticated | Public health/version only | N/A | Protected routes return 401 |

## 8. Performance and resilience plan

Reasonable local, non-destructive concurrency will cover API reads, job submissions, worker claims,
exports, pipeline runs, bounded uploads/query results, and multiple SSE subscribers. Controlled
dependency/provider failures will cover Redis, PostgreSQL, worker, local storage, scanner, and email
errors. Evidence will include latency observations, response/error contracts, pool/queue metrics,
worker heartbeats/leases, attempts, and recovery outcomes. No destructive stress testing will be
performed and no production system is in scope.

## 9. Exact planned commands

Repository and environment:

```powershell
git status --short --branch
git branch --show-current
git remote -v
git log --oneline -10
git diff --stat
git diff --cached --stat
docker compose config --quiet
docker compose ps
docker compose images
```

Backend and database:

```powershell
docker compose exec -T api ruff check .
docker compose exec -T api ruff format --check .
docker compose exec -T api mypy src tests
docker compose exec -T api pytest -m "not integration"
$env:RUN_INTEGRATION_TESTS="1"; $env:DATABASE_URL="postgresql+asyncpg://.../vip_test"; $env:REDIS_URL="redis://localhost:6379/15"; pytest -m integration
docker compose exec -T api python scripts/backend_quality.py
docker compose exec -T api alembic heads
docker compose exec -T api alembic current
docker compose exec -T api alembic check
docker compose exec -T api alembic downgrade 20260722_0007
docker compose exec -T api alembic upgrade head
```

The destructive migration round trip will run only against the dedicated `vip_test` database via
the integration test harness, never against shared/production data. Seed commands will be run twice
against test data with passwords passed only through environment variables.

Frontend:

```powershell
npm ci
npm run typecheck
npm run lint
npm run format:check
npm run test
npm run build
npm run test:e2e
npm run test:a11y
npm audit --audit-level=low
```

Containers and CI:

```powershell
docker compose build api dashboard-worker pipeline-worker
docker compose up -d
docker compose ps
actionlint .github/workflows/*.yml
```

Static review uses `rg` over source, migrations, tests, scripts, workflow, and configuration for all
required markers (`TODO`, `FIXME`, `HACK`, `XXX`, `pass`, `NotImplemented`, `mock`, `localhost`,
Windows paths, dynamic execution/subprocess/deserialization/TLS bypass, and sensitive-field terms).
Matches will be manually classified rather than automatically treated as defects.

## 10. Manual verification checklist

- Login, bootstrap, refresh, logout, invalid credentials, stale/revoked session, and CSRF rejection.
- Organization/workspace switching, protected navigation, cache clearing, and all-persona access.
- Connection catalog/create/detail/update/test/credential replacement with secret absence checks.
- Dataset catalog/detail/schema/quality/lineage and bounded semantic query.
- Dashboard editor save/reload/conflict, publish/view/share/snapshot, export progress/cancel/retry,
  schedules/email preview, signed download expiry/reuse/scope.
- Pipeline editor save/reload/validation/publish, run progress/logs/results/retry/cancel, artifact.
- Generic jobs, attempts, safe errors, dead letter, heartbeat/metrics, worker interruption/recovery.
- File upload/replace/version/restore/delete and malicious filename/MIME/signature/size cases.
- Scanner pending/clean/failure/unavailable policy and download denial when not clean.
- Authenticated SSE filtering, event IDs, reconnect, `Last-Event-ID`, invalid/stale IDs, tenant isolation.
- Browser console/network errors, responsive layouts, keyboard navigation, loading/empty/error/denied/conflict states.

## 11. Expected evidence

The final report will capture every executed command and result, test counts and durations where
reported, HTTP status/contracts/headers, migration revisions, database constraints/state, audit
rows, redacted logs, job attempts/leases/heartbeats/errors, queue/worker metrics, artifacts and
download-token behavior, file scan records, SSE event IDs/resume behavior, and Playwright
screenshots/traces where useful. Unexecuted or environment-blocked checks will be `NOT TESTED`, never
`PASS`.

## 12. Known risks

- The worktree contains extensive pre-existing uncommitted work, so release cleanliness cannot be
  established without owner disposition.
- No Git remote is configured, so remote GitHub Actions is unavailable unless repository authority
  changes.
- Development uses a no-op malware scanner; real ClamAV/Defender integration depends on local
  availability, while production fail-closed configuration remains mandatory.
- Host Python is 3.14 while CI targets 3.12; Docker/locked dependencies provide the primary
  reproducible environment.
- Both npm and pnpm lockfiles exist; CI uses npm, and lockfile consistency requires review.
- Controlled outage/restart checks may briefly interrupt only the local Docker development stack.

## 13. Go/no-go criteria

Approval requires all critical B0–B8 workflows and quality gates to pass, with no unresolved
Critical or High defect; secure authentication and authoritative authorization; complete tenant and
workspace isolation; encrypted undisclosed credentials; safe migrations; durable/recoverable jobs;
working dashboard export and pipeline execution; safe files/scanning/downloads; authenticated
resumable SSE; healthy builds/services; current documentation; and no duplicate common
infrastructure. Any unverified critical criterion or failed required quality gate results in
`NOT READY FOR PHASE B9`. Environment-dependent checks may support
`READY FOR PHASE B9 WITH NON-BLOCKING RECOMMENDATIONS` only when the underlying fail-closed behavior
and all critical local substitutes are proven.
