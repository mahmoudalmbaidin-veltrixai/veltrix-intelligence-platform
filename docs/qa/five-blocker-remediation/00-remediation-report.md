# VIP Final Five Blocker Remediation

## Scope and baseline

- Branch: `frontend/enterprise-ui-enhancement`
- Frozen candidate baseline: `f6eac93989bdb6028b8bc4b1af9b159b15cb7424`
- Scope: only the five independently verified certification blockers.
- No migration, database reset, authorization weakening, timeout increase, test skip,
  mock replacement, push, or pull request was used.

## Blocker results

### 1. Honest operation-level API coverage

The generator now separates classification, exact test mapping, execution, and
result. It rejects missing operation records, missing claimed probes, unsupported
dimensions, malformed evidence, and failed execution reports. The combined
anonymous/authenticated integration sweep executed in one pytest process and
produced:

- 192 paths
- 247 operations
- 247 classified
- 247 exact-test mapped
- 247 executed
- 247 generic contract/security probe results passed
- 42 authenticated success responses with response-schema validation
- 143 observed forbidden responses
- 205 cross-tenant isolation observations

The map does not claim authenticated success or schema validation for operations
that returned a safe domain error because the sweep did not create a happy-path
resource for that operation. Domain test files are navigation aids only and are
not counted as executed dimensions. Exact executable `file::test` identifiers are
recorded for every claimed dimension.

Evidence: `api-operation-coverage.json`.

### 2. Real dashboard export lifecycle

The new integration test uses the real dashboard services to create, save,
reload, and publish a 20-widget immutable version. It binds a scheduled delivery
to that exact version, dispatches through the real scheduler, executes the real
generic job worker and dashboard export handler, reads the stored artifact, checks
the database job/file/export records, parses the generated email, and compares
the attachment bytes to the stored artifact. All 20 widget definitions are
preserved. The final artifact and attachment SHA-256 values are identical.

The data-backed widgets in this delivery fixture are intentionally hidden so the
worker lifecycle test does not substitute a fake connector for a real query.
Their complete definitions still traverse persistence, publication, worker
execution, artifact storage, scheduling, and email delivery. Visible rendering
for every widget type is exercised separately by the all-widget renderer fixture.

Evidence: `widget-lifecycle-evidence.json`.

### 3. PDF/PNG visual parity

PDF and PNG renderers now visibly render configured Cartesian X/Y axis titles
and legends. Legend position is honored for top, bottom, left, and right layouts;
pie and donut charts display category legends without inappropriate Cartesian
axis titles. Renderer behavioral tests assert PDF draw text and PNG pixel changes.
All 20 PDF pages and representative full-resolution PNG chart sections were
visually inspected after regeneration.

Artifact hashes:

- PDF: `568b9b6a5e7b61043050ac5ef8fc7b4aad85f0697b0c7cac9f8c1f9eff9ac298`
- PNG: `c51bcf5284e5b4801598bd7338724fe4a3ac7fe11ab3853cc5155ca421bef041`
- CSV: `bd5dfdc601b985e6dbbf0555d5527e3f2c07bb05203edd31d8c4b119b5344c92`
- JSON: `5b31ad42e50ba9ed61e9fb3c124508536616a1b0c93838b92455cc7511acdcff`

### 4. AI production API fail-closed behavior

All AI catalog routes now require permission, feature flag, entitlement, and an
implementation-backed readiness condition. Production live mode returns a
consistent non-200 response for all four flag/entitlement combinations. Even an
operator-set readiness flag cannot expose the current empty placeholder until
the implementation constant is changed alongside a real implementation.
Explicit development/test mock mode remains available and production validation
rejects that mode.

The existing frontend production gates continue to hide AI routes, direct URLs,
navigation, command palette/search entries, quick actions, mock documents, and
placeholder uploads in live mode.

### 5. Dynamic authentication artifact sanitation

The sanitizer now scans and redacts exact known values and structural sensitive
names in plain files and every entry in Playwright trace ZIPs. Coverage includes
Authorization, Cookie, Set-Cookie, access/refresh/session cookies, CSRF tokens,
storage state, local/session storage, HTML/JSON/context/log files, and URL
parameters. A test issues dynamic cookie canaries not present in the environment
and proves they are removed from files and a trace archive.

CI sanitizes before upload and refuses to upload browser evidence if sanitation
fails. Retained local evidence scans clean; raw sensitive evidence is not
uploaded.

## Regression totals

- Backend Ruff: pass
- Backend format check: pass
- MyPy `src tests`: zero errors across 222 source files
- Backend unit: 255 passed
- Backend integration: 66/66, 66/66, 66/66 in three independent runs with the
  two-second DB timeout
- Frontend lint/typecheck/format/build: pass
- Frontend unit: 303/303 across 49 files
- Firefox dashboard reliability: 20/20 and 20/20, zero retries
- Chromium full: 66/66
- Firefox full: 66/66
- WebKit full: 66/66
- High-DPI: 23/23
- Mobile: 5/5
- Governed pipeline: 10/10
- AI direct API matrix: pass
- Dynamic artifact sanitizer unit: 2/2
- Alembic current/heads/check: `20260803_0019`, one head, clean

All browser runs were first-attempt passes and each retained-artifact scan ended
with zero findings.

## First-failure history

- An early authenticated operation sweep exceeded its outer shell allowance.
  Root cause: raw SSE URLs were used in restricted and cross-tenant persona loops.
  All persona loops now use the invalid-cursor product condition; the combined
  sweep then passed in 57.03 seconds.
- The first AI matrix implementation passed a string environment value rather
  than the enum to the logger. The test failed, was corrected to use
  `AppEnvironment`, then passed.
- The first real lifecycle run reached all product assertions but failed exact-ID
  teardown due to dataset/connection FK ordering. Cleanup now deletes dependent
  test records in FK-safe order; the rerun passed.
- The first standalone coverage generation omitted required database/Redis
  configuration and failed before generation. The configured rerun passed.
- One targeted AI invocation omitted `RUN_INTEGRATION_TESTS=1` and skipped. It was
  not counted; the exact command was rerun with integration enabled and passed.

## Security conclusion

No RBAC, ACL, authorization, tenant-isolation, CSRF, TLS, validation, or timeout
control was weakened. No production mock mode was enabled. No secret, raw trace,
database dump, environment file, or migration is included in this remediation.
