# Pipeline Backend (Phase B7)

## Scope and architecture

B7 provides tenant-scoped pipeline drafts, authoritative validation, immutable published versions, durable asynchronous runs, protected artifacts, and live Pipeline Studio integration. It does not add schedules, arbitrary code, arbitrary URLs, arbitrary filesystem paths, or a general-purpose B8 job framework.

The REST API persists a run and a minimal outbox event in one PostgreSQL transaction before returning `202`. `vip-pipeline-worker` claims work with `FOR UPDATE SKIP LOCKED` and a lease. PostgreSQL remains authoritative for status, attempts, node state, logs, results, cancellation, retry, and audit linkage. The worker can be replaced by B8 infrastructure without changing the REST contracts or immutable version records.

```mermaid
sequenceDiagram
    participant UI as Pipeline Studio
    participant API as FastAPI
    participant DB as PostgreSQL
    participant W as Pipeline Worker
    participant V as B4 Secret Provider
    participant S as Artifact Storage
    UI->>API: POST /pipelines/{id}/runs
    API->>DB: Insert run + outbox (one transaction)
    API-->>UI: 202 queued
    W->>DB: Claim with SKIP LOCKED + lease
    W->>DB: Re-authorize user and tenant
    W->>V: Resolve scoped connection secret
    W->>DB: Read immutable published snapshot
    W->>S: Write tenant/run-bound artifact
    W->>DB: Persist node states, result, logs, audit
    UI->>API: Poll run detail
    API-->>UI: Status, progress, nodes, safe logs
```

## Authoring, validation, and publishing

Draft nodes and edges are separate tenant-owned rows. Aggregate saves require `expected_version`; stale writes return `409 VERSION_CONFLICT`. Validation is server-authoritative and checks node allowlisting, configuration keys, dataset scope, input counts, references, cycles, formulas, and outputs. Drafts may remain incomplete, but unsupported node types or configuration fields are never persisted.

Publishing is rejected until strict validation succeeds. Each publish creates an immutable JSON snapshot with a canonical SHA-256 digest and monotonically increasing version. Runs always reference a published version ID, never mutable draft rows. Restore copies a historical snapshot into a new draft state and increments the row version; it does not mutate history.

Approved node families are B5 dataset sources, deterministic preparation/combine/aggregate/formula transforms, writable B5 dataset outputs, and protected CSV/JSON artifacts. Raw SQL, Python, JavaScript, shell, custom REST, upload paths, inline credentials, and dynamic imports are not executable node contracts.

## Formula language

The formula module uses its own bounded tokenizer, recursive-descent parser, AST, and evaluator. Supported values are literals, `[field]` references, arithmetic/comparison operators, and the allowlisted functions `abs`, `ceil`, `coalesce`, `concat`, `floor`, `lower`, `round`, and `upper`. It enforces source length, token count, nesting, and argument limits. It never calls `eval`, `exec`, a shell, SQL, JavaScript, or dynamic imports.

## Run state and retry semantics

```mermaid
stateDiagram-v2
    [*] --> queued
    queued --> running: worker claim
    queued --> cancelled: cancel before claim
    running --> succeeded
    running --> failed
    running --> cancelled: cooperative request
    failed --> retrying: authorized retry
    retrying --> running: new attempt
    failed --> [*]: retry limit
    succeeded --> [*]
    cancelled --> [*]
```

Attempts are append-only. Retry preserves prior attempts and requeues the same logical run with a
new attempt number, subject to the configured cap; current-attempt progress, row totals, node
states, and result summaries are reset before execution. Cancellation is immediate for queued work
and cooperative between bounded node operations for running work, including a final cancellation
check before success is committed.

The worker renews its lease from an independent database session while a node is running. Expired
leases are reclaimable, and row locking prevents two healthy workers from claiming the same run
concurrently. Recovery finalizes the abandoned attempt and node states with
`PIPELINE_LEASE_EXPIRED`, records a recovery audit/log event, discards abandoned-attempt artifacts,
resets attempt-scoped counters, and starts one replacement attempt. Each completed node commits its
safe node log and progress checkpoint so API clients can observe execution while the run is active.

## Connections, datasets, lineage, and artifacts

Dataset and connection identifiers are resolved again inside the active organization/workspace. Source identifiers come only from B5 catalog records and are quoted by the server; values are parameterized. Credentials are obtained only from the B4 `SecretProvider` and are never placed in versions, queue payloads, logs, results, artifacts, or API responses. Network destination policy is rechecked by the worker.

Dataset outputs require an existing tenant dataset explicitly marked writable. Writes use generated identifiers and parameterized values. Successful writes update dataset metadata/version and create B5 lineage edges carrying pipeline, published-version, and run references.

Large CSV/JSON results use a provider boundary and tenant/workspace/run-bound storage keys. Failed,
cancelled, and lease-abandoned attempts remove artifacts created by that attempt before the terminal
state is committed. API responses never expose storage paths. Downloads require authentication,
current RBAC/feature/entitlement access, artifact scope, retention validity, and a short-lived HMAC
token bound to the user, organization, workspace, and artifact. Successful token consumption is
recorded in Redis with a tenant-qualified digest until expiry, making artifact download links
single-use and replay resistant.

## API summary

- `GET/POST /api/v1/pipelines`
- `GET/PUT/DELETE /api/v1/pipelines/{pipeline_id}`
- `POST /api/v1/pipelines/{pipeline_id}/validate`
- `POST /api/v1/pipelines/{pipeline_id}/publish`
- `GET /api/v1/pipelines/{pipeline_id}/versions`
- `POST /api/v1/pipelines/{pipeline_id}/versions/{version_id}/restore`
- `POST/GET /api/v1/pipelines/{pipeline_id}/runs`
- `GET /api/v1/pipelines/{pipeline_id}/runs/{run_id}`
- `POST .../cancel` and `POST .../retry`
- `GET .../artifacts` and `POST .../{artifact_id}/download-url`
- `GET /api/v1/pipeline-artifacts/download?token=...`

All endpoints require authentication, organization/workspace context, RBAC, `pipeline_studio` feature and entitlement gates, applicable quotas, CSRF on mutations, tenant-qualified queries, correlation IDs, and audit events.

## Operations and troubleshooting

```powershell
docker compose up -d postgres redis api dashboard-worker pipeline-worker
docker compose logs -f pipeline-worker
docker compose exec api alembic upgrade head
docker compose exec api python -m vip_api.cli seed-governance
```

Important settings include `PIPELINE_RUN_MAX_ROWS`, `PIPELINE_RUN_TIMEOUT_SECONDS`, `PIPELINE_RUN_MAX_ATTEMPTS`, `PIPELINE_WORKER_POLL_SECONDS`, `PIPELINE_WORKER_LEASE_SECONDS`, `PIPELINE_RUN_MAX_RESULT_BYTES`, `PIPELINE_ARTIFACT_RETENTION_HOURS`, and `PIPELINE_DOWNLOAD_SIGNING_KEY`. Production must provide a strong signing key. Scale workers horizontally; claims are database-coordinated. Monitor queue age, expired leases, failure codes, attempt counts, run duration, and artifact volume.

If work remains queued, verify worker health, database reachability, migration head, and governance synchronization. If a source fails, test its B4 connection and B5 dataset status; secrets and raw driver errors are intentionally absent from client responses. If downloads fail, verify retention and request a new link rather than reusing an expired token.

## Development and validation

```powershell
cd apps/api
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy src tests
$env:RUN_INTEGRATION_TESTS="1"
$env:DATABASE_URL="postgresql+asyncpg://vip:vip_local_dev_only@localhost:5432/vip_test"
.\.venv\Scripts\python.exe -m pytest
cd ../..
pnpm typecheck
pnpm lint
pnpm test
pnpm build
docker compose config --quiet
docker compose build api pipeline-worker
```

Migration naming follows `YYYYMMDD_NNNN_description.py`. Validate `alembic downgrade 1883cb49e703`, `alembic upgrade head`, and `alembic check` against a disposable test database. Never downgrade a production database without a tested backup and change approval.
