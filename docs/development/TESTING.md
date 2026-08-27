# Testing

## Frontend static and unit gates

```bash
npm ci
npm run typecheck
npm run lint
npm run format:check
npm run test
npm run build
```

## Backend static and unit gates

From `apps/api` after installing `requirements.lock` and the editable package:

```bash
ruff check .
ruff format --check .
mypy src tests
pytest -m "not integration"
```

## Backend integration and migrations

Use an isolated PostgreSQL test database and Redis database, then:

```bash
RUN_INTEGRATION_TESTS=1 pytest -m integration
alembic check
alembic current
alembic heads
```

On PowerShell, set `$env:RUN_INTEGRATION_TESTS='1'` for the current process instead of the inline POSIX form.

## Browser and accessibility

The Playwright configuration builds/serves the frontend but expects a live API on port 8000, migrated database, seeded ephemeral personas, and healthy workers. Follow `.github/workflows/quality-gate.yml` or the guarded local certification script rather than embedding passwords in commands.

```bash
npx playwright install
npm run test:e2e
npm run test:a11y
```

Scan generated traces, screenshots, videos, logs, and HTML reports before retaining any evidence. Their default directories are ignored.

## Infrastructure and containers

```bash
docker compose config --quiet
docker compose build api dashboard-worker pipeline-worker
docker build -f infra/containers/web/Dockerfile \
  --build-arg VITE_APP_ENV=production \
  --build-arg VITE_API_MODE=live \
  --build-arg VITE_API_BASE_URL=https://api.example.com/api/v1 \
  --build-arg API_ORIGIN=https://api.example.com .
terraform fmt -check -recursive
terraform -chdir=infra/aws init -backend=false
terraform -chdir=infra/aws validate
```

Terraform validation does not replace a reviewed plan or live smoke test.
