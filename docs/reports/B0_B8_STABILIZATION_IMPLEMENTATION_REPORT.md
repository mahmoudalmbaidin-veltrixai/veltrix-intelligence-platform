# B0–B8 Stabilization Implementation Report

Audit date: 2026-07-28
Repository: Veltrix Intelligence Platform (VIP)
Branch: `feature/identity-org-workspace-rbac`
Starting HEAD: `45bb09f0b5a3fb0576a1aef876d129402dd874f4`
Ending HEAD: `45bb09f0b5a3fb0576a1aef876d129402dd874f4`
Certified snapshot: the current uncommitted working tree based on the ending HEAD above

## A. Executive Summary

The preceding audit verdict was `NOT READY FOR PHASE B9`, with 30 findings and five leading
blockers. This stabilization pass fixed 13 confirmed defect groups: backend formatting, backend
test typing, frontend formatting, identity integration fixtures, stale login selectors, two E2E
fixture paths, a Firefox upload defect, an Edge sidebar race, unbounded pipeline polling, missing
operational metrics, missing pipeline-worker health, unsafe Defender exit-code handling, and
vulnerable pip tooling in runtime images.

All static gates, 138 backend tests, 192 frontend tests, the production build, clean dependency
audits, fresh-database migration, and the effective 208-test browser matrix now pass. The API,
dashboard worker, pipeline worker, PostgreSQL, and Redis all report healthy. No tests were skipped
or disabled to obtain these results.

Certification remains conditional. The host's Microsoft Defender installation is disabled and
cannot perform either a clean-file or EICAR scan. The complete deterministic pipeline
reconciliation/retry/cancel/restart journey and complete dashboard widget/export/delivery journey
were not proven as single fresh scenarios. In particular, a live CSV dashboard export correctly
failed closed because the selected dashboard had no tabular data, and a newly created schedule did
not produce a delivery within the observation window. The browser matrix was fully covered in
shards with focused reruns after fixes, but was not completed twice end-to-end. These omissions
prevent a green certification.

**Certification decision:** B0–B8 may continue stabilization and internal testing, but Phase B9
must not start. Production file ingestion must remain excluded until a real scanner passes the
checklist in section H.

## B. Baseline

| Item | Recorded value |
| --- | --- |
| Branch | `feature/identity-org-workspace-rbac` |
| Starting commit | `45bb09f0b5a3fb0576a1aef876d129402dd874f4` |
| Ending commit | Same; no commit was requested or created |
| Initial worktree | Tracked tree clean; ignored prior audit report present |
| Remote | `origin` configured |
| Node / npm | Node 24.18.0 / npm 11.16.0 |
| Python | 3.14.4 |
| Docker / Compose | 29.6.1 / 5.3.0 |
| PostgreSQL / Redis | 17.5 / 8.0.3 |
| Environment | Local development/test Compose environment; secrets omitted |
| Migration head | `20260728_0014` |
| Active services | API, dashboard worker, pipeline worker, PostgreSQL, Redis |

Initial reproduced failures:

- Ruff formatting failed for migration `0013` and Platform Admin routes.
- MyPy reported 20 formula-test typing errors.
- Prettier failed in six frontend files.
- Integration tests reported 6 passed, 11 failed, and 8 errors because fixtures did not satisfy
  the username/optional-email identity contract.
- Playwright still targeted `Work email`; the aggregate run reached its 15-minute limit.
- `/metrics` returned 404.
- The pipeline worker had no Compose health state.

The dedicated `vip_test` database alone was reset. Its `public` schema was recreated and migrated
from empty to the single current head. No non-test database or user data was reset.

## C. Change Summary and Ledger

| File(s) | Reason and issue fixed | Behavior/test impact |
| --- | --- | --- |
| `apps/api/alembic/versions/20260728_0013_identity_username_optional_email.py` | Ruff formatting | No migration behavior change |
| `apps/api/src/vip_api/platform_admin/routes.py` | Ruff formatting | No route behavior change |
| `apps/api/tests/unit/test_formula_functions.py` | Add accurate row annotations | Removed 20 MyPy errors; assertions unchanged |
| Seven `apps/api/tests/integration/test_*.py` fixture files | Supply explicit unique usernames and normalized usernames | Full identity-compatible integration suite |
| `src/modules/pipelines/FormulaEditor.vue`, `formulaFunctions.ts`, `formulaFunctions.spec.ts`, `src/modules/platform/PlatformConsoleView.vue`, `platform.service.ts`, `platform.service.spec.ts` | Prettier conformance | Formatting only |
| `tests/e2e/fixtures.ts`, `auth-routes.spec.ts`, `login-navigation.spec.ts` | Replace stale `Work email` selector with accessible `Username or email` | Restored authentication E2E contract |
| `tests/e2e/b8-5-pipeline-source.spec.ts`, `dataset-upload.spec.ts` | Correct controlled CSV fixture path | Restored real upload journeys |
| `src/app/shell/AppSidebar.vue` | Base tooltip state on pinned collapse state | Removed Edge timing race |
| `src/modules/datasets/DatasetListView.vue` | Preserve selected file during async read; prioritize known text extensions over Firefox's generic Excel MIME | Cross-browser CSV upload works |
| `src/modules/pipelines/pipelines.service.ts`, `usePipelineRunner.ts` | Add abortable bounded polling, backoff, timeout, visibility pause, and cleanup | No overlapping or indefinite run polling |
| `apps/api/src/vip_api/core/metrics.py` | Add bounded, dependency-free process metrics registry | New Prometheus metric families |
| `apps/api/src/vip_api/core/config.py` | Add metrics enablement/token settings and production validation | Production metrics require a token |
| `apps/api/src/vip_api/core/middleware.py` | Instrument request, status, latency, active-request, and auth-failure metrics | Operational telemetry without tenant/user labels |
| `apps/api/src/vip_api/api/routes/operational.py` | Add protected `/metrics` and aggregate DB/Redis/worker/job/pipeline/dashboard metrics | Prometheus scrape now succeeds |
| `apps/api/src/vip_api/events/routes.py` | Instrument SSE activity, resume, reconnect, missed recovery, dropped/error paths | SSE is observable |
| `apps/api/src/vip_api/pipelines/worker.py` | Maintain pipeline worker heartbeat and clean shutdown | Worker health reflects live dependencies/heartbeat |
| `docker-compose.yml` | Apply heartbeat-aware health check to pipeline worker | Compose reports pipeline worker healthy |
| `apps/api/src/vip_api/files/scanning.py` | Disable Defender remediation and map only exit 0 to clean, 2 to infected, all others to error | Fail-closed scanner result handling |
| `apps/api/Dockerfile` | Upgrade runtime pip to the first release fixing all detected image advisories | Removes four medium and one low image findings |
| `apps/api/tests/unit/test_application.py` | Test protected Prometheus endpoint | Metrics authorization/format regression coverage |
| `apps/api/tests/unit/test_platform_jobs_files_events.py` | Test Defender clean/infected/error mappings and flag | Scanner fail-closed regression coverage |
| `docs/backend/ASYNC_JOBS_FILES_EVENTS.md`, `PIPELINE_BACKEND.md` | Document metrics, heartbeat health, and bounded polling | Operations contract updated |
| `docs/reports/B0_B8_STABILIZATION_IMPLEMENTATION_REPORT.md` | Record current evidence and residual risks | Certification deliverable |

No migration history semantics were changed, no public test assertion was weakened, and no Phase B9
feature or unrelated dependency was introduced.

## D. Quality-Gate Matrix

| Gate / command | Result | Passed | Failed | Skipped | Blocked | Notes |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `ruff check .` | Pass | 179 files | 0 | 0 | 0 | Backend tree |
| `ruff format --check .` | Pass | 179 files | 0 | 0 | 0 | Backend tree |
| `python -m mypy src tests` | Pass | 179 files | 0 | 0 | 0 | Zero errors |
| `python -m pytest -m "not integration"` | Pass | 113 | 0 | 25 deselected | 0 | 21.06 s |
| `RUN_INTEGRATION_TESTS=1 python -m pytest -m integration` | Pass | 25 | 0 | 113 deselected | 0 | 77.80 s; full-suite rerun also passed |
| `python -m pytest` | Pass | 138 | 0 | 0 | 0 | 87.44 s |
| Alembic `heads`, `current`, `check` | Pass | 3 checks | 0 | 0 | 0 | One head/current `20260728_0014`; no drift |
| Empty `vip_test` migration to head | Pass | 1 lifecycle | 0 | 0 | 0 | Dedicated test DB only |
| `npm ci` | Pass | 296 packages installed | 0 | 0 | 0 | Initial EPERM traced to local Vite process; clean rerun passed |
| `npm run typecheck` | Pass | 1 gate | 0 | 0 | 0 | TypeScript |
| `npm run lint` | Pass | 1 gate | 0 | 0 | 0 | ESLint |
| `npm run format:check` | Pass | 1 gate | 0 | 0 | 0 | Prettier |
| `npm run test` | Pass | 192 | 0 | 0 | 0 | 35 files |
| `npm run build` | Pass | 500 modules | 0 | 0 | 0 | Production bundle |
| `npm audit --audit-level=low` | Pass | 297 packages | 0 vulnerabilities | 0 | 0 | All severities clear |
| `python -m pip_audit -r requirements.lock` | Pass | Locked environment | 0 vulnerabilities | 0 | 0 | pip-audit 2.10.1 |
| Docker Compose image builds | Pass | API + 2 workers | 0 | 0 | 0 | Final source built |
| Docker Scout image scans | Pass | 3 images | 0 vulnerable packages | 0 | 0 | Final rebuilt images |
| `docker compose ps` | Pass | 5 healthy services | 0 | 0 | 0 | API, both workers, DB, Redis |
| Playwright configured matrix | Pass in project shards/focused reruns | 208 | 0 final | 0 | 0 | First aggregate attempt timed out; not repeated twice in full |
| Real Defender clean/EICAR | Blocked | 0 | 1 engine invocation | 0 | 1 | Defender disabled; CLI returned `0x80004005`, exit 2 even for a clean file |
| `actionlint` / hosted CI | Blocked | 0 | 0 | 0 | 1 | `actionlint` unavailable; no authorized hosted-CI mutation |

Integration test count remains the required 25; no test was added, removed, or reclassified.

## E. Module Certification Matrix

The repository does not contain an authoritative document mapping every feature to numbered
B0–B8 labels. This matrix uses the implemented phase areas described by the repository reports.

| Area | Frontend | Backend / DB | Worker / events | Security and evidence | Certification |
| --- | --- | --- | --- | --- | --- |
| Foundation, health, migrations | Pass | Pass; fresh DB and single head | All services healthy | Operational routes tested | Certified |
| Identity, organizations, workspaces | Pass | 25 integration tests pass | Session/event paths pass | Browser switching, CSRF/session tests | Certified |
| RBAC and governance | Pass | Pass | N/A | Browser and API negative tests | Certified within automated matrix |
| Connections and secrets | Pass | Pass | Job paths pass | Encrypted-secret tests and tenant scope | Certified |
| Files and datasets | Browser upload/preview pass | Contracts/tests pass | Scan workflow unit tested | Real AV blocked | Conditional; production ingestion excluded |
| Semantic/formula functions | Unit/UI paths pass | Formula tests pass | N/A | Tenant-scoped services | Conditional; not reconciled in one fresh business scenario |
| Pipelines | Browser publish/run pass | Persistence/worker tests pass | Healthy; recovery paths tested | Scoped runs/artifacts | Conditional; full 26-step live reconciliation incomplete |
| Dashboards, exports, delivery | UI journeys pass | Unit/API paths pass | Worker healthy | Tokens and scope tested | Conditional; fresh CSV/delivery journey incomplete |
| Jobs, audit, notifications, SSE | Pass | Tests pass | SSE + bounded fallback metrics | Tenant-scoped event streams | Certified |
| Platform administration | Pass | Routes/static gates pass | N/A | Platform role tests pass | Certified within automated matrix |

## F. Pipeline Evidence

The controlled CSV contains 15 records and the required text, integer, decimal, date, null,
duplicate, and invalid values. It includes a duplicate `B850005`, invalid date, negative quantity,
invalid decimal, null customer/category, out-of-range discount, and zero values.

A real Chrome/Edge/Firefox journey uploaded and registered this CSV, previewed `B850001`, created
and reloaded a pipeline, published it, and completed worker execution with a non-zero row counter.
The latest retained run evidence was:

| Evidence | Value |
| --- | --- |
| Run ID | `f9e1b418-77a7-474a-8ff6-f54908684457` |
| Status / attempt | `succeeded` / 1 |
| Input fixture rows | 15 |
| Worker `rows_processed` | 30 (source plus sink/node accounting) |
| Artifact ID | `67cffa9f-4a89-44ee-8dd7-c48310c351a4` |
| Artifact size | 1,270 bytes |
| SHA-256 | `d8cf9c9f8c0d4c256bd6a5d109fd233cad0a9a45093ed8a102569cd67bc336a2` |

Multiple browser runs produced the same checksum, supporting deterministic and idempotent output.
The worker/persistence suites cover retry, cancellation, expired leases, recovery, dead-letter
behavior, and tenant scope. Retained local audit data also contains four retry-queued events, four
cancel-requested events, and two lease-recovered events.

This is not a complete certification of the mandated 26-step scenario. The browser pipeline had a
source and protected-file output but no newly executed formula transformation, and expected versus
actual valid/rejected values were not independently reconciled from the stored artifact. Retry,
cancellation, and worker restart were proven by automated tests/retained evidence rather than
performed in that same fresh run. Therefore formula results, explicit valid/rejected counts,
attempt IDs for a retry, and a fresh cancellation/recovery result remain unclaimed.

## G. Dashboard Evidence

Fresh API runtime exports:

| Format | Export ID | Result | Size / MIME |
| --- | --- | --- | --- |
| PDF | `2a625536-fb36-4a0e-acc4-8a7cd1395f0e` | Completed | 2,054 bytes / `application/pdf` |
| PNG | `b5f2b3e2-37d4-4260-8eda-87b0ebf21b0d` | Completed | 19,161 bytes / `image/png` |
| JSON | `6e898583-7820-4682-bc8f-70ceefa2046f` | Completed | 342 bytes / `application/json` |
| CSV | `5211f877-5ac5-4caa-80d3-c0702db8f780` | Failed closed after 3 attempts | `DASHBOARD_CSV_NO_DATA` |

The selected published dashboard had no exportable tabular widget data, so the CSV result is the
correct fail-closed contract, not a renderer crash. It nevertheless does not meet the requirement
to prove a successful non-empty CSV export. Unit tests pass for PDF, PNG, JSON and CSV renderers,
version/filter context, signed tokens, cross-user denial, single use, email attachment/BCC,
scheduler frequency/timezone logic, retry, and duplicate prevention.

A one-time schedule was created and polled, but no fresh delivery appeared in its history during
the observation window; it was then cleaned up. Retained local data contains a successful delivery
and its audit event, but this is not treated as fresh proof. Manual expected-versus-actual widget
values, signed-URL expiry after elapsed time, every schedule cadence, and a generated development
email attachment were not all reconciled in one current scenario. Dashboard export and delivery
remain conditional.

## H. Security Evidence

### Tenant and RBAC matrix

| Persona | Read | Create/update | Publish/execute | Members/roles | Platform Admin |
| --- | --- | --- | --- | --- | --- |
| Tenant A administrator | Allow | Allow | Allow | Allow, subject to last-admin rules | Deny |
| Tenant A editor | Allow | Allow | Allow | Deny | Deny |
| Tenant A viewer | Allow | Deny | Deny | Deny | Deny |
| Tenant B administrator against Tenant A IDs | Deny/404 | Deny/404 | Deny/404 | Deny/404 | Deny |
| User with no access | Deny | Deny | Deny | Deny | Deny |
| Platform administrator | Tenant access remains scoped | Tenant access remains scoped | Tenant access remains scoped | Platform operations only | Allow |

Backend tenancy/governance tests and browser governance/tenant-isolation journeys pass. They cover
cross-tenant substitution, role restrictions, invitations, suspended/archived state, CSRF,
session revocation, and non-disclosing 403/404 behavior. A newly hand-executed substitution against
every resource type in section 12 was not performed; the result above is limited to the automated
matrix.

### Malware scanning

Microsoft Defender's CLI exists, but Windows reports:

- `AntivirusEnabled=False`
- `RealTimeProtectionEnabled=False`
- signature age `65535`
- clean README scan: `[Failed][0x80004005]`, exit code 2

The adapter now invokes Defender with `-DisableRemediation`, maps exit 0 to clean, exit 2 to
infected, and treats every other result as scanner error. Regression tests cover clean, infected,
and unavailable/error results, and the ingestion workflow remains fail closed. Because the engine
cannot produce a valid clean-file result, EICAR was not generated or submitted and real scanning
is not certified.

Production checklist:

1. Enable a repository-supported Defender or ClamAV service and update signatures.
2. Confirm the health probe and a clean-file scan.
3. Submit EICAR in an isolated test environment and verify quarantine/download denial/audit.
4. Exercise timeout/unavailable/retry and confirm fail-closed behavior.
5. Exercise MIME/extension/signature mismatch, size/corruption, signed-token expiry/replay, and
   cross-tenant denial.
6. Retain engine/version/signature and audit evidence.

Until this checklist passes, file ingestion must remain excluded from production readiness.

### Dependencies and images

- npm audit: zero vulnerabilities at low or higher.
- pip-audit: no known vulnerabilities in `requirements.lock`.
- Docker Scout: API, dashboard-worker, and pipeline-worker images were rebuilt with pip 26.1.2
  after an initial final-image scan found four medium and one low pip advisories; the completed
  rescan reported zero critical, high, medium, or low vulnerabilities.
- No credential, token, `.env` content, raw SQL, tenant ID, or user ID is exposed by metrics or
  this report.

## I. Browser and Accessibility Matrix

| Project | Functional | Axe/accessibility | Console/network | Result |
| --- | ---: | ---: | --- | --- |
| Chromium desktop | 42/42 | 18/18 | No unexplained final error | Pass |
| Microsoft Edge desktop | 42/42 | 18/18 | No unexplained final error | Pass |
| Firefox desktop | 42/42 | 18/18 | Transient route-smoke `NetworkError` passed on focused rerun | Pass |
| High-DPI Chromium | Included | 18 axe + 5 responsive = 23/23 | Clear | Pass |
| Mobile Chromium | 5/5 | Included responsive checks | Clear | Pass |

The effective configured matrix is 208/208 after fixes and focused reruns. The first monolithic run
hit the 15-minute command limit because of suite duration; projects were then sharded. It was not
run twice in full, so the requested two complete reliability passes remain an unresolved process
gate. No serious or critical axe finding remains.

## J. Observability and Worker Health

`GET /metrics` now emits Prometheus text and can require a Bearer token; production configuration
rejects an enabled endpoint without a token. Labels are bounded and do not include tenant/user IDs.
The live scrape returned HTTP 200 and included:

- HTTP request count, method/status, duration, and active requests
- authentication failures and rate-limit events
- database and Redis health (`1` for both)
- worker active/stale state (`3` active, `0` stale)
- queue ready/delayed depth and age
- job attempts, retries, failures, dead letters, cancellation, stale lease, recovery, and duration
- pipeline states, input/output/rejected rows, retry/cancel/recovery, artifact failures
- dashboard export/delivery duration, success/failure/retry/duplicate prevention, schedule lag
- SSE active connections, reconnect/resume, missed-event recovery, dropped events, and errors

The scrape reported `vip_platform_metrics_collection_error 0`. API, generic/dashboard worker,
pipeline worker, PostgreSQL, and Redis report healthy. Pipeline and dashboard health checks require
live database/Redis access and a current worker heartbeat rather than only a running process.

The frontend uses the accepted temporary strategy: abortable bounded polling at one second,
exponential error backoff capped at ten seconds, a 15-minute overall cap, a five-second hidden-tab
pause, request cancellation, and immediate visibility resume. SSE already supports authenticated
tenant/workspace scoping and cursor/resume behavior and is now instrumented. Full browser-level
disconnect/reconnect fault injection was not separately performed.

## K. Remaining Risks

| Severity / priority | Risk and reason | Recommended owner/action | Blocks B9 |
| --- | --- | --- | --- |
| Critical / P0 | No functioning real malware engine; clean and EICAR evidence absent | Security/Platform: provision and execute section H checklist; exclude production ingestion meanwhile | Yes |
| High / P1 | Complete 26-step pipeline reconciliation was not executed as one fresh deterministic scenario | Data Platform/QA: reconcile artifact values, formula, invalid rows, retry/cancel/restart/recovery | Yes |
| High / P1 | Complete dashboard widget/export/scheduled-delivery scenario is incomplete; successful CSV and fresh delivery absent | Analytics/QA: use tabular dashboard, validate all exports/tokens/schedules/email artifact | Yes |
| Medium / P2 | Complete Playwright suite was not run twice; evidence is sharded with focused reruns | QA: run two uninterrupted matrix passes in CI | Yes |
| Medium / P2 | Current implementation is uncommitted, so the ending commit does not itself contain these fixes | Repository owner: review and commit the working-tree snapshot, then rerun release gates at that SHA | Yes |
| Low / P3 | `actionlint` and hosted-CI results unavailable locally | DevEx: run workflow validation and protected hosted CI | No by itself |

These are the only unresolved risks claimed by this implementation report. They are evidence gaps
or infrastructure blockers, not hidden test failures.

## L. Scope and Integrity Confirmations

- No Phase B9 feature was implemented.
- No AI, Knowledge Base/RAG, Agents, Automation, Billing, Marketplace, or Developer Portal
  development was started.
- No unrelated broad refactor was performed.
- No test was disabled, skipped, or trivialized merely to obtain a pass.
- No production secret was exposed.
- Migrations remain single-headed.
- Generated browser artifacts, traces, logs, credentials, and `.env` files were not committed.
- `git diff --check` passes.
- The verdict applies to the current working tree based on ending HEAD
  `45bb09f0b5a3fb0576a1aef876d129402dd874f4`; because no commit was requested, it cannot truthfully
  certify that unchanged commit alone.

## Final Verdict

```text
B0–B8 CONDITIONALLY CERTIFIED — PHASE B9 BLOCKED
```
