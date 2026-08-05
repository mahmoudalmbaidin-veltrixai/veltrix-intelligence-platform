# Independent Certification Handoff

## Candidate identity

- Repository: `C:\Users\MahmoudAlmbaidin\Downloads\VIP`
- Branch: `frontend/enterprise-ui-enhancement`
- Freeze base: `b6c85b313c29e161f5b1c23555e00f54b2352454`
- Product/test gate SHA: `1e286a20eb535633a3eb341a2e0d3e38693fa5ac`
- Final release SHA: the commit containing this file; run `git rev-parse HEAD`. The
  release-manager response records the exact immutable value.
- Push status: not pushed
- Pull request: not created

## Environment prerequisites

- Docker Desktop; Node.js 24; pnpm 11; Python 3.14; Playwright Chromium, Firefox,
  and WebKit binaries.
- Required Compose services: API, PostgreSQL, Redis, MySQL, ClamAV, pipeline worker,
  and dashboard worker.
- Backend dependencies installed from the committed lockfiles and frontend dependencies
  installed from the committed package lock.
- `VIP_TEST_DATABASE_URL` supplied by a protected local/CI provider; do not write its
  value to source or reports.
- First isolated QA environment: run
  `apps\api\scripts\full-platform-qa-seed.ps1`. Existing exact QA estate: run
  `apps\api\scripts\resume-full-platform-qa-seed.ps1`. Both create process-safe,
  DPAPI-backed ephemeral browser credentials below ignored `artifacts/`.

## Static, unit, build, integration, and migration

```powershell
Push-Location apps\api
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
uv run pytest -m 'not integration' -q
$env:RUN_INTEGRATION_TESTS='1'
$env:APP_ENV='test'
if (-not $env:VIP_TEST_DATABASE_URL) { throw 'Set VIP_TEST_DATABASE_URL using the protected provider.' }
$env:DATABASE_URL=$env:VIP_TEST_DATABASE_URL
$env:REDIS_URL='redis://127.0.0.1:6379/15'
$env:DATABASE_CONNECT_TIMEOUT='2.0'
1..3 | ForEach-Object { uv run pytest -m integration -q; if ($LASTEXITCODE) { exit $LASTEXITCODE } }
uv run alembic current
uv run alembic heads
uv run alembic check
Pop-Location
npm run lint -- --quiet
npm run typecheck
npm run format:check
npm test -- --run
npm run build
```

## Independent browser certification

```powershell
.\tests\e2e\run-local-certification.ps1 --project=firefox-desktop dashboard-save-reliability.spec.ts --repeat-each=20
.\tests\e2e\run-local-certification.ps1 --project=firefox-desktop dashboard-save-reliability.spec.ts --repeat-each=20
.\tests\e2e\run-local-certification.ps1 --project=chrome-desktop
.\tests\e2e\run-local-certification.ps1 --project=firefox-desktop
.\tests\e2e\run-local-certification.ps1 --project=webkit-desktop
.\tests\e2e\run-local-certification.ps1 --project=chrome-high-dpi
.\tests\e2e\run-local-certification.ps1 --project=chromium-mobile
.\tests\e2e\run-local-certification.ps1 --project=chrome-desktop b8-5-pipeline-source.spec.ts --repeat-each=10
```

## Contract and parity regeneration

```powershell
Push-Location apps\api
uv run python scripts/build_api_operation_coverage.py ..\..\docs\qa\final-certification-remediation\api-operation-coverage.json
uv run python scripts/render-dashboard-parity-evidence.py
Pop-Location
```

Verify `operation_count=classified_count=247`, all 20 widget rows, the four artifact
hashes, and every rendered PDF page independently. Each Playwright run invokes the
credential sanitizer in global teardown. Before uploading any retained artifact, run
the sanitizer again using the protected process-scoped QA password variables.

## Evidence paths

- Parity: `docs/qa/final-certification-remediation/evidence/dashboard-parity/`
- Widget matrix: `docs/qa/final-certification-remediation/widget-parity-results.json`
- API coverage: `docs/qa/final-certification-remediation/api-operation-coverage.json`
- Artifact scan: `docs/qa/release-freeze/artifact-secret-scan.json`
- Repository scan: `docs/qa/release-freeze/repository-secret-scan.json`
- Classification and exclusions: `docs/qa/release-freeze/file-classification.json` and
  `docs/qa/release-freeze/excluded-artifacts.json`

Known intentional limitations: XLSX upload and archived-user lifecycle remain
intentionally unsupported and unadvertised; incomplete AI surfaces are development
mock-only and fail closed in production live mode. This handoff is readiness evidence,
not production approval.
