# B0–B8 Final Certification Report

Certification date: 2026-07-28
Repository: Veltrix Intelligence Platform (VIP)
Branch: `feature/identity-org-workspace-rbac`
Certification commit: the commit containing this report (recorded by immutable SHA in the release
response and Git history)

## 1. Executive Summary

The B0–B8 implementation is functionally complete for the repository-defined scope. The three
previously missing production proofs now pass: real fail-closed malware scanning, a deterministic
pipeline reconciliation with failure/cancellation/recovery, and a dashboard
query/export/scheduled-delivery reconciliation. The complete 208-test Playwright matrix passed
twice without retries. Backend, frontend, migration, dependency, workflow, secret, container, and
service-health gates pass.

This certifies the B0–B8 foundation and permits Phase B9 definition. It does not claim that a local
Compose deployment is a public production deployment; the environment-specific live controls in
the production-readiness report remain deployment prerequisites.

## 2. Previous Conditional Status

The prior report was `B0–B8 CONDITIONALLY CERTIFIED — PHASE B9 BLOCKED`. Its blockers were:

1. no operational antivirus engine and therefore no real clean/EICAR proof;
2. no single reconciled pipeline scenario with rejected-row evidence and resilience proof;
3. no single reconciled dashboard scenario with all exports and scheduled delivery;
4. no two uninterrupted full browser passes.

All four evidence gaps are closed below.

## 3. Final Committed SHA

Git cannot embed a commit's own content-derived SHA inside that same commit. The authoritative
final SHA is therefore the immutable SHA of the commit containing this report, printed in the
certification response and visible with `git rev-parse HEAD`. All post-commit gates are executed
against that exact checkout.

## 4. Environment

| Component | Certified value |
| --- | --- |
| Host | Windows, Docker Desktop, local isolated certification environment |
| Python | 3.14.4 |
| Node / npm | 24.18.0 / 11.16.0 |
| PostgreSQL | 17.10, populated DB preserved |
| Redis | 8.0.6 |
| ClamAV | 1.5.3; signatures current on 2026-07-28 |
| API | `0.1.0`, development configuration |
| Alembic | one linear head, `20260728_0015` |
| Browsers | Chromium/Chrome, Edge, Firefox, high-DPI/a11y Chromium, mobile Chromium |

Passwords, signing keys, cookies, and tokens are intentionally omitted.

## 5. Completed Blockers

| Defect group | Closure |
| --- | --- |
| Operational malware scan absent | Added ClamAV service/adapter, persisted evidence, fail-closed errors, real clean/EICAR/outage tests |
| Pipeline reconciliation absent | Added row-validation node, rejected-row artifact and reasons, deterministic reconciliation |
| Pipeline recovery evidence absent | Proved retry exhaustion, cancellation, hard worker loss, lease recovery and one final artifact |
| Dashboard mapped filter incorrect | Published-dashboard mapped runtime filters now resolve and reconcile |
| Dashboard delivery terminal retry defect | Terminal attempts now reach the correct final state; retry/cancel/deduplication pass |
| Browser authentication races | Login fixture waits on the real response and URL; client state reset is deterministic |
| Organization menu inaccessible at scale | Tenant menu is viewport-bounded and scrollable |
| Local integration DB mismatch | Test fixture uses a dedicated overridable `*_test` URL matching Compose |
| Runtime image patch lag | PostgreSQL 17.10 and Redis 8.0.6 are digest pinned; vulnerable upstream privilege helper is replaced at runtime |
| Cross-realm Blob contract assertion | Frontend download tests now verify the standard Blob brand, MIME type, and byte size across Node/jsdom realms |
| Hosted browser worker topology incomplete | CI now starts and heartbeat-checks the generic/dashboard and pipeline workers before live Playwright journeys |

Together with the 13 groups in the stabilization report, 23 defect groups were closed. No test was
disabled, skipped, reclassified, or weakened. Retries remain zero. The longest worker-backed
browser journey has an explicit hosted-runtime budget while retaining every operation-level
assertion and timeout.

## 6. Full Quality-Gate Matrix

| Gate | Result |
| --- | --- |
| Ruff lint | Pass |
| Ruff format | Pass, 201 files |
| MyPy | Pass, 179 source/test files |
| Backend unit | Pass, 119 |
| Backend integration | Pass, 25 |
| Backend full suite | Pass, 144 |
| Alembic populated current/head/check | Pass, `20260728_0015`, one head, no drift |
| Empty-database zero-to-head | Pass |
| Frontend install | Pass, 296 packages |
| TypeScript | Pass |
| ESLint / Prettier | Pass / pass |
| Frontend unit | Pass, 192 tests in 35 files |
| Production build | Pass, 500 modules |
| npm audit | Pass, zero known vulnerabilities |
| pip-audit | Pass, zero known vulnerabilities |
| Action workflow syntax / actionlint | Pass |
| Gitleaks | Pass, no leaks |
| Docker Compose build/config/start | Pass |
| Application image critical/high scan | Pass, zero |

## 7. Browser and Accessibility Results

Two uninterrupted `npm run test:e2e` matrix executions passed:

| Pass | Tests | Failures | Retries | Duration |
| --- | ---: | ---: | ---: | ---: |
| 1 | 208 | 0 | 0 | 21.8 minutes |
| 2 | 208 | 0 | 0 | 16.6 minutes |

The matrix covers desktop Chrome, desktop Edge, desktop Firefox, high-DPI Chromium with axe
checks, and mobile Chromium. No critical or serious accessibility violation remained. Focused
Firefox and Edge organization/authentication reruns also passed 60/60 each.

## 8. Antivirus Evidence

| Scenario | Result |
| --- | --- |
| Engine | ClamAV 1.5.3, TCP service, current signatures |
| Clean upload | File `70899734-bc79-4325-944e-6278239a4606` became ready and downloaded once |
| Replay | Rejected with 404 |
| EICAR | Upload rejected with 422; infected audit emitted |
| Infected persistence | No file, version, or content object retained |
| Scanner stopped | Upload failed closed with 503 |
| Recovery | Scanner restart restored clean ingestion |
| Malformed/unreachable/timeout | All fail closed |
| Focused regression | 18 tests passed |

Scan engine, version, signature date, result, signature name, timestamps, and summary are persisted
as upload evidence. Production mode cannot bypass scanner errors.

## 9. Pipeline Reconciliation Evidence

The controlled input had 15 rows. Validation accepted 9 and rejected 6 with explicit reason
records. Deduplication retained 8 rows; the business filter retained 6.

| ID / measurement | Evidence |
| --- | --- |
| Dataset | `18c6aaca-2aa4-4dbe-8b2a-24735eef59e8` |
| Pipeline | `57e5af74-d288-49a9-a2eb-b21464601150` |
| Run | `28e48a12-6d82-4c51-bea4-ce3874e4b679` |
| Output artifact | `3d908521-c812-4588-a37e-74b3a2d28d01` |
| Rejected artifact | `aaf2528d-c5e3-4ed1-8d49-50aa234b9036` |
| Output checksum | `c93c60ec21ceae2479df786eef0ff3fd0dc8c4640fd20a14627bfccebe08e9dc` |
| Valid net values | B850001=2160; B850002=2090; B850003=2400; B850004=4080; B850005=1710; B850006=2200 |

A controlled permanent failure exhausted two attempts and produced no artifact. A 240-node run
was cancelled and produced no artifact. A hard-killed worker left an expired lease; the restarted
worker recovered attempt 2, succeeded, emitted one artifact and one recovery audit. Eleven focused
pipeline tests passed.

## 10. Dashboard, Export, and Delivery Evidence

The published dashboard reconciled a KPI of 14,640 and region totals Dammam 2,400, Jeddah 3,800,
Riyadh 8,440. A published runtime filter for Riyadh reconciled to 8,440.

| Format | Export ID | Bytes | Result |
| --- | --- | ---: | --- |
| PDF | `668dcdf7-fae1-4d41-8971-4cc5e8becbd3` | 3,399 | Pass |
| PNG | `e0dea2a6-df4d-4a16-b4b0-53015a1f11cc` | 34,432 | Pass |
| JSON | `e93701f0-f6dc-4cb2-9b6b-39d0b611d37e` | 1,622 | Pass |
| CSV | `6180ff43-ee45-4a3f-978a-542fb28dc2f8` | 253 | Pass |

Signed download replay was rejected with 403. One-time, daily, weekly, and monthly schedules were
created and validated; a daily schedule produced a sent delivery through the development-file
provider. Retry, terminal failure, cancellation, duplicate prevention, and cross-tenant denial
passed. Eleven focused dashboard/delivery tests passed.

## 11. Tenant and RBAC Evidence

API integration and browser suites prove organization/workspace isolation, tenant-ID substitution
denial, Admin/Editor/Viewer/Restricted behavior, invitation lifecycle, last-owner safeguards,
suspension/archive effects, session revocation, CSRF, platform-admin separation, and non-disclosing
403/404 results. No cross-tenant artifact, file, dataset, pipeline, dashboard, export, delivery,
job, or audit access succeeded.

## 12. Metrics and Health Evidence

`/health`, `/ready`, and `/api/v1/version` return 200 in the healthy state. Prometheus metrics are
token protected and include request, status, latency, auth failure, SSE, dependency, worker
heartbeat, job, pipeline, and dashboard aggregates without tenant/user/secret labels. API,
dashboard worker, pipeline worker, PostgreSQL, Redis, and ClamAV are healthy. Stopping Redis makes
`/ready` return 503 while `/health` remains 200; restarting Redis and workers restores readiness
and heartbeat health.

## 13. CI Evidence

The workflow passes `actionlint`. Local CI-equivalent backend, frontend, browser, migration,
dependency, image, and service gates pass. The hosted browser job provisions the API plus the
generic/dashboard and pipeline workers, then verifies worker heartbeats before Playwright.
The immutable hosted run ID and result for the commit containing this report are recorded in the
final response after push.

## 14. Production-Readiness Assessment

The codebase and B0–B8 containers are ready for controlled UAT and pilot packaging. A public live
deployment still requires managed PostgreSQL/Redis/object storage, external secrets/KMS, TLS and
DNS, production email, ingress/WAF/rate limits, backup/restore drills, monitoring/alert routing,
capacity tests, data retention, incident response, and rollout/rollback automation. Local Compose
success is not evidence that those environment controls exist.

## 15. Remaining Risks

- Docker Scout retains deleted base-layer package evidence for upstream `gosu`; runtime inspection
  proves `/usr/local/bin/gosu` resolves to native `su-exec`, and the derivative introduces zero
  critical/high findings. The upstream base should be repinned when its SBOM is rebuilt.
- Development-file email is delivery-path proof, not proof of a production SMTP provider.
- Load, soak, disaster-recovery, and external penetration tests are deployment-program work.
- AI, Automation, Reports, Marketplace, Billing, and some informational screens remain mock,
  static, frontend-only, or partial as identified in the capability matrix; none was promoted by
  this certification.

## 16. Final Verdict

**B0–B8 CERTIFIED — READY TO DEFINE AND START PHASE B9**

No Phase B9, AI, or Automation implementation was added in this closure.
