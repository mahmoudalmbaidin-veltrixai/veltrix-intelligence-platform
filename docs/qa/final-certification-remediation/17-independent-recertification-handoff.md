# Independent Re-Certification Handoff

Run from `C:\Users\MahmoudAlmbaidin\Downloads\VIP` on branch `frontend/enterprise-ui-enhancement` without trusting these results.

## Static and unit

```powershell
Push-Location apps\api
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest -m 'not integration' -q
Pop-Location
npm run lint -- --quiet
npm run typecheck
npm run format:check
npm test -- --run
npm run build
```

## PostgreSQL reliability (run three times)

```powershell
$env:RUN_INTEGRATION_TESTS='1'
$env:APP_ENV='test'
if (-not $env:VIP_TEST_DATABASE_URL) { throw 'Set VIP_TEST_DATABASE_URL through the protected local/CI secret provider.' }
$env:DATABASE_URL=$env:VIP_TEST_DATABASE_URL
$env:REDIS_URL='redis://127.0.0.1:6379/15'
$env:DATABASE_CONNECT_TIMEOUT='2.0'
Push-Location apps\api
uv run pytest -m integration -q
Pop-Location
```

## Browser

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

## Evidence, migration, and secret scan

```powershell
Push-Location apps\api
uv run python scripts/render-dashboard-parity-evidence.py
uv run alembic current
uv run alembic check
uv run python scripts/sanitize-playwright-artifacts.py --path ..\..\test-results --path ..\..\playwright-report --report ..\..\docs\qa\final-certification-remediation\artifact-secret-scan.json
Pop-Location
```

Inspect `api-operation-coverage.json`, `widget-parity-results.json`, the four parity artifacts, and all 20 PDF pages independently. This handoff is readiness evidence, not production approval.
