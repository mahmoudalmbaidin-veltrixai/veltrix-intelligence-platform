# B5 datasets and semantic layer

Phase B5 adds tenant-scoped analytical metadata without adding ingestion, pipelines, dashboards, reports, or arbitrary SQL. Every resource is owned by one organization and workspace. Backend authorization, features, entitlements, quotas, and B4 connection-secret resolution are authoritative.

## Architecture

`vip_api.datasets` owns catalog records, immutable source identity, fields, PostgreSQL metadata discovery, predefined quality rules/results, and bounded lineage. `vip_api.semantic` owns draft/published models, attached datasets, validated joins, dimensions, measures, metrics, KPIs, glossary terms, and typed semantic queries.

PostgreSQL discovery reads only `information_schema` in a read-only transaction. Re-discovery uses a SHA-256 source key derived from connection ID, catalog, schema, object name, and type, so persistence is idempotent. Discovery never removes missing objects automatically.

Semantic queries accept keys and typed values—not SQL, table names, functions, or expressions. Identifiers are resolved from tenant-scoped metadata and quoted by the PostgreSQL compiler; values are separate asyncpg parameters. Execution uses a read-only transaction, timeout, row/offset/filter/dimension/metric/order limits, and a serialized-result byte limit. Hidden and sensitive fields are excluded. Audit records contain counts, IDs, duration, row count, and truncation only—never SQL, values, credentials, or results.

Supported end-to-end connector: PostgreSQL (`metadata_discovery` and `read_only_analytics`). Future connectors plug into the discovery registry and a connector-specific semantic compiler/executor.

## Local setup

```powershell
docker compose up -d postgres redis
docker compose run --rm api python -m alembic upgrade head
docker compose run --rm api python -m vip_api.cli seed-governance
docker compose run --rm api python -m vip_api.cli seed-connection-types
docker compose run --rm api python -m vip_api.cli seed-dataset-catalogs
docker compose run --rm api python -m vip_api.cli seed-semantic-layer
docker compose up -d --build api
pnpm install --frozen-lockfile
pnpm dev
```

Native development uses the same commands from `apps/api` with `.venv\Scripts\python`. Set `B5_DEMO_POSTGRES_PASSWORD` in the process environment before the dataset seed. Compose supplies it from the local `POSTGRES_PASSWORD`; commands and output do not print it.

## APIs

- `/api/v1/datasets`, `/datasets/{id}`, `/datasets/{id}/fields`, `/datasets/discover`
- `/api/v1/datasets/{id}/quality`, `/quality-rules`, `/lineage`
- `/api/v1/semantic-models` with validation, publication, dimensions, measures, metrics, and KPIs
- `/api/v1/glossary/domains`, `/glossary/terms`
- `POST /api/v1/semantic-query`

All routes require authenticated organization/workspace headers. Mutations also use the existing CSRF cookie/header contract.

## Quality gates

```powershell
cd apps/api
.venv\Scripts\ruff check .
.venv\Scripts\ruff format --check .
.venv\Scripts\mypy src tests
.venv\Scripts\pytest

cd ../..
pnpm lint
pnpm format:check
pnpm typecheck
pnpm test
pnpm build
pnpm test:e2e
pnpm test:a11y
```

For the live portal, set `VITE_API_MODE=live` and
`VITE_API_BASE_URL=http://localhost:8000/api/v1`. The centralized HTTP client routes the
unversioned `/auth/*` cookie-session contract to the API origin while keeping dataset, semantic,
governance, connection, and tenancy APIs under `/api/v1`. Mock adapters are selected only when
`VITE_API_MODE=mock` (used by deterministic component and presentation tests).

Intentional B5 limits: PostgreSQL is the single end-to-end connector; compilation is single-dataset until an unambiguous approved join exists; quality results are metadata-only; query results are not persisted; arbitrary calculated expressions are unsupported.
