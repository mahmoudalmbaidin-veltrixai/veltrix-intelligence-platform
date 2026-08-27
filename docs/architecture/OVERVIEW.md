# Architecture overview

VIP is a Vue single-page application backed by a FastAPI service and asynchronous Python workers. PostgreSQL is authoritative for users, tenancy, governance, data catalogs, authored assets, schedules, jobs, audit records, and application state. Redis supports caching, queues, event streams, rate limits, and coordination. Generated files and uploads use a filesystem storage provider rooted at configurable paths.

```text
User browser
  -> TLS / reverse proxy
    -> static Vue application
    -> FastAPI API
       -> PostgreSQL
       -> Redis
       -> persistent filesystem
       -> malware scanner
       -> SMTP provider (when activated)

Redis/PostgreSQL
  -> generic job worker
     -> dataset quality, dashboard export, file lifecycle, schedule ticks
  -> pipeline worker
     -> pipeline execution and artifacts
```

## Frontend

`src/` contains Vue 3, TypeScript, Vue Router, Pinia, Zod contracts, shared UI components, and feature modules. `src/shared/lib/apiClient.ts` centralizes HTTP, cookie, CSRF, tenant-header, and event-stream behavior. `VITE_API_MODE=live` selects the API-backed adapters. Production builds reject mock mode.

## API

`apps/api/src/vip_api/` contains FastAPI route composition, Pydantic settings, authentication, tenant resolution, governance, connections, datasets, semantic querying, dashboards, pipelines, jobs, files, events, and administration. Settings come from environment variables. Production validation rejects insecure cookies, wildcard hosts/origins, missing signing/encryption keys, disabled malware scanning, and non-SMTP delivery.

## Data and migrations

SQLAlchemy models and Alembic migrations live under `apps/api`. Migrations are linear and must run once before a release is promoted. Tenant-owned resources carry organization/workspace scope and API repositories apply that scope to reads and writes.

## Workers and schedules

The generic worker consumes Redis/PostgreSQL-backed jobs and runs recurring dashboard-delivery and pipeline-schedule ticks. The pipeline worker leases and executes pipeline runs separately. Production may isolate schedule ticks in a singleton generic-worker task by disabling tick settings on ordinary workers.

## Storage

V1 includes a registered local-filesystem provider. The same provider works with a shared mounted filesystem such as EFS. S3/Azure/GCS/MinIO application-storage adapters are extension points, not shipped V1 providers. Connector support for S3 is unrelated to application artifact storage.

For detailed domain diagrams and route inventories, see `docs/backend/` and `docs/architecture/system-workflow/`.
