# Independent Re-Certification Handoff

Branch: `frontend/enterprise-ui-enhancement`

Starting candidate: `3f78daa9a29d879d9ca2413e1da14fd57da2bc75`

The exact final committed SHA is emitted by the release task after the documentation
commit. Reviewers must use that SHA, not the starting candidate. No push or pull request
was created.

## Prerequisites

- Docker services: PostgreSQL, Redis, API, dashboard worker, pipeline worker, MySQL,
  and ClamAV healthy.
- `VIP_TEST_DATABASE_URL` must point to the protected local integration database.
- Process-scoped browser fixture credentials must be provisioned by the committed
  certification bootstrap; do not place values in the repository.
- Integration settings: `RUN_INTEGRATION_TESTS=1`, `APP_ENV=test`,
  `REDIS_URL=redis://127.0.0.1:6379/15`, `DATABASE_CONNECT_TIMEOUT=2.0`.

## Exact focused commands

```powershell
Push-Location apps\api
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
uv run pytest -m 'not integration' -q
$env:RUN_INTEGRATION_TESTS='1'
$env:APP_ENV='test'
$env:DATABASE_URL=$env:VIP_TEST_DATABASE_URL
$env:REDIS_URL='redis://127.0.0.1:6379/15'
$env:DATABASE_CONNECT_TIMEOUT='2.0'
$env:VIP_WIDGET_LIFECYCLE_EVIDENCE_PATH='..\..\tmp\multiformat-lifecycle-evidence.json'
$env:VIP_API_OPERATION_EVIDENCE_PATH='..\..\tmp\api-operation-security-coverage.json'
uv run pytest -m integration -q
uv run python scripts/build_api_operation_coverage.py ..\..\tmp\coverage-regenerated.json --execution-report ..\..\tmp\api-operation-security-coverage.json
uv run alembic current
uv run alembic heads
uv run alembic check
Pop-Location

npm run lint -- --quiet
npm run typecheck
npm run format:check
npm test -- --run
npm run build

.\tests\e2e\run-local-certification.ps1 --project=firefox-desktop dashboard-save-reliability.spec.ts --repeat-each=20
.\tests\e2e\run-local-certification.ps1 --project=chrome-high-dpi
.\tests\e2e\run-local-certification.ps1 --project=chrome-desktop b8-5-pipeline-source.spec.ts --repeat-each=10
```

Run integration three consecutive times and Firefox dashboard twice for independent
certification. Evidence paths are:

- `multiformat-lifecycle-evidence.json` and `artifacts/all-20-widgets-lifecycle.*`
- `api-operation-security-coverage.json`
- `high-dpi-results.json`, `test-results.json`, and `artifact-secret-scan.json`

Known limitations remain unchanged: this handoff prepares an independent audit and does
not issue production certification.
