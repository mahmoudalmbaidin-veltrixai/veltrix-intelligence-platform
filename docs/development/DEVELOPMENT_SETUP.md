# Development setup

## Frontend

Use Node.js 22 and the committed npm lock file:

```bash
npm ci
npm run dev
```

Frontend source is under `src/`. Raw HTTP belongs in `src/shared/lib/apiClient.ts`; feature services use the shared live/mock service pattern. Production/live claims require `VITE_API_MODE=live`.

## Backend

Use Python 3.12 and the locked requirements:

```bash
cd apps/api
python -m venv .venv
# Activate the virtual environment.
python -m pip install -r requirements.lock
python -m pip install --no-deps -e .
cp .env.example .env
```

Start PostgreSQL, Redis, and ClamAV through Compose, then run migrations/API/workers as separate processes. Keep schema changes in Alembic and include tests for tenant and authorization boundaries.

## Source-of-truth files

- npm: `package.json` and `package-lock.json`;
- Python: `apps/api/pyproject.toml`, `requirements.lock`, and `requirements.runtime.lock`;
- database: SQLAlchemy models plus `apps/api/alembic/`;
- configuration: Pydantic `Settings`, `.env.example`, and Compose/Terraform injection;
- CI: `.github/workflows/quality-gate.yml`.

Generated outputs, local `.env` files, virtual environments, caches, uploaded files, exports, credentials, database dumps, and test reports are not source.
