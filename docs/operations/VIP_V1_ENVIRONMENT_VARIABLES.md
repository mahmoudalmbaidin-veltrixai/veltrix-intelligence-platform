# VIP V1 Environment Variable Inventory

Authoritative release: `4e97591845a93037d6e54b0237bcb3208d1b2696`  
Source of truth: `apps/api/src/vip_api/core/config.py`, `apps/api/scripts/docker-entrypoint.sh`, `src/shared/config/env.ts`, and `infra/containers/web/Dockerfile`.

This inventory covers every setting accepted by the deployed API package plus the web build inputs and API-image process controls. Defaults below are code defaults, not blanket production recommendations. Variables not overridden in the AWS task definitions use these defaults. Comma-separated values are parsed as lists. Every Python process constructs the full `Settings` object and must receive all production-required values even when the Service column names only the functional consumer.

Service labels: **All API** = API, dashboard worker, pipeline worker, scheduler, and migration task; **Web build** = Vite build stage only. No `VITE_*` value may contain a secret because it is compiled into public JavaScript.

## Core, dependencies, origins, and telemetry

| Variable | Service | Required? | Secret? | Example / description |
| --- | --- | ---: | ---: | --- |
| `APP_NAME` | All API | No | No | Default `VIP API`; response metadata. |
| `APP_ENV` | All API | Yes | No | `staging` or `production`; activates fail-closed production validation. |
| `APP_VERSION` | All API | Yes for release | No | `1.0.0`; human-readable version. |
| `DEBUG` | All API | Yes | No | Must be `false` in production. |
| `LOG_LEVEL` | All API | No | No | Default `INFO`; CRITICAL/ERROR/WARNING/INFO/DEBUG. |
| `SERVICE_NAME` | Each API process | Yes | No | `vip-api`, `vip-dashboard-worker`, `vip-pipeline-worker`, `vip-scheduler`, or `vip-migration`. |
| `ENABLE_DOCS` | API | Yes | No | `false` for staging/production. |
| `API_V1_PREFIX` | API | No | No | Default `/api/v1`; do not change for V1 because the web build targets it. |
| `AI_CAPABILITIES_PRODUCTION_READY` | All API | No | No | Default/production `false`; do not enable without a certified readiness decision. |
| `AI_DEVELOPMENT_MOCK_MODE` | All API | No | No | Must be `false` in production. |
| `DATABASE_URL` | All API | Yes | **Yes** | `postgresql+asyncpg://<user>:<password>@<private-host>:5432/vip?ssl=require`. Inject as one secret. |
| `DATABASE_POOL_SIZE` | All API | No | No | Code default `10`; current AWS value `5` per process. |
| `DATABASE_MAX_OVERFLOW` | All API | No | No | Code default `20`; current AWS value `5`. |
| `DATABASE_POOL_TIMEOUT` | All API | No | No | Default/current AWS `30` seconds. |
| `DATABASE_CONNECT_TIMEOUT` | All API | No | No | Default/current AWS `5` seconds. |
| `DATABASE_ECHO` | All API | No | No | Default `false`; keep false to avoid SQL/data leakage. |
| `REDIS_URL` | All API | Yes | **Yes** | `rediss://:<auth>@<private-host>:6379/0`; inject as one secret. |
| `REDIS_SOCKET_TIMEOUT` | All API | No | No | Default/current AWS `5` seconds. |
| `CORS_ALLOWED_ORIGINS` | API | Yes | No | Exact frontend HTTPS origin, e.g. `https://app.<domain>`; no wildcard in production. |
| `CORS_ALLOW_CREDENTIALS` | API | Yes | No | `true` for cookie-based browser auth. |
| `TRUSTED_HOSTS` | API | Yes | No | Exact API host, e.g. `api.<domain>`; no wildcard in production. |
| `BUILD_COMMIT_SHA` | All API | Yes for release | No | Full `4e97591845a93037d6e54b0237bcb3208d1b2696`; returned by version endpoint. |
| `BUILD_TIMESTAMP` | All API | Yes for release | No | UTC RFC3339 build timestamp. |
| `METRICS_ENABLED` | API | No | No | Default/current AWS `true`. |
| `METRICS_BEARER_TOKEN` | API | Required when metrics enabled in production | **Yes** | Random high-entropy bearer token; inject from secret store. |

## Authentication, cookies, tenancy, invitations, and governance

| Variable | Service | Required? | Secret? | Example / description |
| --- | --- | ---: | ---: | --- |
| `AUTH_ACCESS_SESSION_TTL_MINUTES` | API | No | No | Default `15`. |
| `AUTH_REFRESH_SESSION_TTL_DAYS` | API | No | No | Default `14`; absolute session lifetime. |
| `AUTH_SESSION_IDLE_TTL_MINUTES` | API | No | No | Default `30`; sliding idle timeout. |
| `AUTH_SESSION_IDLE_WARNING_MINUTES` | Web/API contract | No | No | API default `5`; client warning threshold contract. |
| `AUTH_MAX_ACTIVE_SESSIONS_PER_USER` | API | No | No | Default `10`; range 1–100. |
| `AUTH_COOKIE_SECURE` | API | Yes | No | Must be `true` in production. |
| `AUTH_COOKIE_SAMESITE` | API | Yes | No | Current value `lax`; `none` requires secure cookies. |
| `AUTH_COOKIE_DOMAIN` | API | Yes for sibling hosts | No | Parent cookie scope, e.g. `.<domain>`; staging must use its approved parent. |
| `AUTH_ACCESS_COOKIE_NAME` | API/Web contract | No | No | Default `vip_access_session`; changing is an application contract change. |
| `AUTH_REFRESH_COOKIE_NAME` | API/Web contract | No | No | Default `vip_refresh_session`. |
| `AUTH_CSRF_COOKIE_NAME` | API/Web contract | No | No | Default `vip_csrf_token`; must match `VITE_AUTH_CSRF_COOKIE_NAME`. |
| `AUTH_CSRF_HEADER_NAME` | API/Web contract | No | No | Default `X-CSRF-Token`; must match `VITE_AUTH_CSRF_HEADER_NAME`. |
| `AUTH_MAX_FAILED_LOGIN_ATTEMPTS` | API | No | No | Default `5`. |
| `AUTH_LOCKOUT_MINUTES` | API | No | No | Default `15`. |
| `AUTH_LOGIN_RATE_LIMIT_PER_MINUTE` | API | No | No | Default/current AWS `10`. |
| `PASSWORD_MIN_LENGTH` | API | No | No | Default `12`. |
| `PASSWORD_MAX_LENGTH` | API | No | No | Default `256`. |
| `PASSWORD_RESET_TOKEN_TTL_MINUTES` | API | No | No | Default `30`. |
| `PASSWORD_RESET_RATE_LIMIT_PER_MINUTE` | API | No | No | Default/current AWS `5`. |
| `FRONTEND_URL` | API | Yes | No | Exact frontend origin, e.g. `https://app.<domain>`. |
| `CSRF_TRUSTED_ORIGINS` | API | Yes | No | Exact frontend HTTPS origin(s); wildcard forbidden. |
| `TENANCY_ORGANIZATION_HEADER` | API/Web contract | No | No | Default `X-Organization-ID`; must remain an `X-` header. |
| `TENANCY_WORKSPACE_HEADER` | API/Web contract | No | No | Default `X-Workspace-ID`; must remain an `X-` header. |
| `TENANCY_REQUIRE_WORKSPACE_BY_DEFAULT` | API | No | No | Default `false`. |
| `TENANCY_DEFAULT_WORKSPACE_NAME` | API | No | No | Default `Default`. |
| `TENANCY_AUDIT_ENABLED` | API | No | No | Default `true`. |
| `TENANCY_CACHE_PREFIX` | API | No | No | Default `vip`; isolate environments if Redis were ever shared (sharing is not allowed). |
| `INVITATION_TOKEN_TTL_HOURS` | API | No | No | Default `72`. |
| `INVITATION_TOKEN_BYTES` | API | No | No | Default `32`; entropy bytes. |
| `INVITATION_ACCEPT_URL` | API | Yes | No | `https://app.<domain>/invitations/accept`. |
| `AUTHORIZATION_CACHE_ENABLED` | API | No | No | Default `false`. |
| `AUTHORIZATION_CACHE_TTL_SECONDS` | API | No | No | Default `60`. |
| `FEATURE_FLAGS_CACHE_TTL_SECONDS` | API | No | No | Default `60`. |
| `ENTITLEMENTS_CACHE_TTL_SECONDS` | API | No | No | Default `60`. |
| `QUOTA_CACHE_TTL_SECONDS` | API | No | No | Default `30`. |
| `AUDIT_EVENTS_ENABLED` | All API | Yes | No | Must be `true` in production. |
| `AUDIT_DENIED_ACCESS` | All API | Yes | No | Must be `true` in production. |
| `AUDIT_RETENTION_DAYS` | All API | No | No | Default/current AWS `365`; allowed 30–3650. |
| `GOVERNANCE_FAIL_CLOSED` | All API | Yes | No | Must be `true` in production. |

## Connections, discovery, semantic queries, and dashboards

| Variable | Service | Required? | Secret? | Example / description |
| --- | --- | ---: | ---: | --- |
| `CONNECTION_SECRET_PROVIDER` | API/workers | Yes | No | Only supported value `database_encrypted`. |
| `CONNECTION_ENCRYPTION_KEY` | API/workers | Yes in production | **Yes** | URL-safe base64 encoding of exactly 32 random bytes; stable for existing ciphertext. |
| `CONNECTION_ENCRYPTION_KEY_VERSION` | API/workers | Yes | No | Current AWS value `prod-v1`; metadata label, not the key. |
| `CONNECTION_TEST_TIMEOUT_SECONDS` | API | No | No | Default `15`. |
| `CONNECTION_TEST_MAX_REDIRECTS` | API | No | No | Default `2`. |
| `CONNECTION_TEST_RATE_LIMIT_PER_MINUTE` | API | No | No | Default `10`. |
| `CONNECTION_ALLOW_PRIVATE_NETWORKS` | API/workers | No | No | Default/current AWS `false`; enable only with an approved connector network design. |
| `CONNECTION_ALLOW_HTTP` | API/workers | No | No | Default/current AWS `false`. |
| `CONNECTION_BLOCK_CLOUD_METADATA` | API/workers | Yes | No | Default/current AWS `true`; SSRF defense. |
| `CONNECTION_MAX_CONFIGURATION_BYTES` | API | No | No | Default `32768`. |
| `CONNECTION_MAX_SECRET_BYTES` | API | No | No | Default `16384`. |
| `METADATA_DISCOVERY_TIMEOUT_SECONDS` | API/workers | No | No | Default `30`. |
| `METADATA_DISCOVERY_MAX_OBJECTS` | API/workers | No | No | Default `500`. |
| `METADATA_DISCOVERY_MAX_FIELDS_PER_OBJECT` | API/workers | No | No | Default `500`. |
| `LINEAGE_MAX_DEPTH` | API | No | No | Default `5`. |
| `LINEAGE_MAX_NODES` | API | No | No | Default `250`. |
| `SEMANTIC_QUERY_DEFAULT_LIMIT` | API | No | No | Default `100`. |
| `SEMANTIC_QUERY_MAX_LIMIT` | API | No | No | Default `1000`. |
| `SEMANTIC_QUERY_MAX_OFFSET` | API | No | No | Default `10000`. |
| `SEMANTIC_QUERY_MAX_DIMENSIONS` | API | No | No | Default `10`. |
| `SEMANTIC_QUERY_MAX_METRICS` | API | No | No | Default `20`. |
| `SEMANTIC_QUERY_MAX_FILTERS` | API | No | No | Default `25`. |
| `SEMANTIC_QUERY_MAX_ORDER_FIELDS` | API | No | No | Default `10`. |
| `SEMANTIC_QUERY_MAX_IN_VALUES` | API | No | No | Default `500`. |
| `SEMANTIC_QUERY_TIMEOUT_SECONDS` | API | No | No | Default `30`. |
| `SEMANTIC_QUERY_MAX_RESULT_BYTES` | API | No | No | Default `5242880` (5 MiB). |
| `DASHBOARD_MAX_PAGES` | API | No | No | Default `50`. |
| `DASHBOARD_MAX_WIDGETS` | API | No | No | Default `250`. |
| `DASHBOARD_MAX_WIDGETS_PER_PAGE` | API | No | No | Default `100`. |
| `DASHBOARD_MAX_FILTERS` | API | No | No | Default `50`. |
| `DASHBOARD_MAX_EDITOR_PAYLOAD_BYTES` | API | No | No | Default `2097152` (2 MiB). |
| `DASHBOARD_MAX_VERSION_SNAPSHOT_BYTES` | API | No | No | Default `5242880` (5 MiB). |
| `DASHBOARD_QUERY_MAX_CONCURRENT_WIDGETS` | API | No | No | Default `8`. |
| `DASHBOARD_QUERY_TIMEOUT_SECONDS` | API | No | No | Default `30`. |
| `DASHBOARD_QUERY_CACHE_ENABLED` | API | No | No | Default `false`. |
| `DASHBOARD_QUERY_CACHE_TTL_SECONDS` | API | No | No | Default `60`. |
| `DASHBOARD_QUERY_MAX_RESULT_BYTES` | API | No | No | Default `5242880` (5 MiB). |
| `DASHBOARD_SNAPSHOT_MAX_BYTES` | API/worker | No | No | Default `20971520` (20 MiB). |
| `DASHBOARD_SNAPSHOT_RETENTION_DAYS` | API/worker | No | No | Default `30`. |

## Dashboard export, scheduler, email, pipeline, and jobs

| Variable | Service | Required? | Secret? | Example / description |
| --- | --- | ---: | ---: | --- |
| `DASHBOARD_EXPORT_MAX_ATTEMPTS` | Dashboard worker | No | No | Default `3`. |
| `DASHBOARD_EXPORT_MAX_ARTIFACT_BYTES` | Dashboard worker/API | No | No | Default `52428800` (50 MiB). |
| `DASHBOARD_EXPORT_RETENTION_HOURS` | Dashboard worker/API | No | No | Default `24`. |
| `DASHBOARD_EXPORT_WORKER_POLL_SECONDS` | Dashboard worker | No | No | Default `1.0`. |
| `DASHBOARD_EXPORT_LEASE_SECONDS` | Dashboard worker | No | No | Default `120`. |
| `DASHBOARD_DELIVERY_SCHEDULER_ENABLED` | API/dashboard/pipeline/scheduler | Yes | No | `false` everywhere except singleton scheduler, where `true`. |
| `DASHBOARD_DELIVERY_SCHEDULER_POLL_SECONDS` | Scheduler | No | No | Default `15.0`. |
| `DASHBOARD_DELIVERY_SCHEDULER_BATCH` | Scheduler | No | No | Default `25`. |
| `PIPELINE_SCHEDULER_ENABLED` | API/dashboard/pipeline/scheduler | Yes | No | `false` everywhere except singleton scheduler, where `true`. |
| `PIPELINE_SCHEDULER_POLL_SECONDS` | Scheduler | No | No | Default `15.0`. |
| `PIPELINE_SCHEDULER_BATCH` | Scheduler | No | No | Default `25`. |
| `DASHBOARD_ARTIFACT_ROOT` | API/dashboard worker | Yes | No | `/data/vip-artifacts` on shared EFS. |
| `DASHBOARD_DOWNLOAD_TOKEN_TTL_SECONDS` | API/dashboard worker | No | No | Default `300`. |
| `DASHBOARD_DOWNLOAD_SIGNING_KEY` | API/dashboard worker | Yes in production | **Yes** | Independent high-entropy signing key. |
| `DASHBOARD_EMAIL_PROVIDER` | API/dashboard worker | Yes | No | Must be `smtp` in production; `disabled`/`file` are non-production. |
| `DASHBOARD_EMAIL_OUTBOX_ROOT` | Dashboard worker | No | No | Default `/data/vip-email-outbox`; file provider only. |
| `DASHBOARD_EMAIL_FROM` | API/dashboard worker | Yes for SMTP | No | Verified address such as `no-reply@mail.<domain>`. |
| `DASHBOARD_SMTP_HOST` | API/dashboard worker | Yes for SMTP | No | Approved SMTP hostname. |
| `DASHBOARD_SMTP_PORT` | API/dashboard worker | No | No | Default/current AWS `587`. |
| `DASHBOARD_SMTP_USERNAME` | API/dashboard worker | Provider-dependent | **Yes** | Secret-store value; must be paired with password. |
| `DASHBOARD_SMTP_PASSWORD` | API/dashboard worker | Provider-dependent | **Yes** | Secret-store value; must be paired with username. |
| `DASHBOARD_SMTP_STARTTLS` | API/dashboard worker | Yes | No | Current AWS `true`. |
| `DASHBOARD_SMTP_USE_TLS` | API/dashboard worker | Yes | No | Current AWS `false`; cannot be true together with STARTTLS. |
| `DASHBOARD_SMTP_TIMEOUT_SECONDS` | API/dashboard worker | No | No | Default `30`. |
| `PIPELINE_MAX_NODES` | API | No | No | Default `250`. |
| `PIPELINE_MAX_EDGES` | API | No | No | Default `1000`. |
| `PIPELINE_RUN_MAX_ATTEMPTS` | Pipeline worker/API | No | No | Default `3`. |
| `PIPELINE_RUN_MAX_ROWS` | Pipeline worker/API | No | No | Default `100000`. |
| `PIPELINE_RUN_MAX_RESULT_BYTES` | Pipeline worker/API | No | No | Default `52428800` (50 MiB). |
| `PIPELINE_RUN_TIMEOUT_SECONDS` | Pipeline worker | No | No | Default `900`. |
| `PIPELINE_WORKER_POLL_SECONDS` | Pipeline worker | No | No | Default `1.0`. |
| `PIPELINE_WORKER_LEASE_SECONDS` | Pipeline worker | No | No | Default `120`. |
| `PIPELINE_ARTIFACT_ROOT` | API/pipeline worker | Yes | No | `/data/vip-pipeline-artifacts` on shared EFS. |
| `PIPELINE_ARTIFACT_RETENTION_HOURS` | Pipeline worker/API | No | No | Default `24`. |
| `PIPELINE_DOWNLOAD_TOKEN_TTL_SECONDS` | API/pipeline worker | No | No | Default `300`. |
| `PIPELINE_DOWNLOAD_SIGNING_KEY` | API/pipeline worker | Yes in production | **Yes** | Independent high-entropy signing key. |
| `JOB_QUEUE_PREFIX` | API/workers/scheduler | No | No | Default `vip:jobs`. |
| `JOB_DEFAULT_QUEUE` | API/workers | No | No | Default `default`. |
| `JOB_WORKER_QUEUES` | Dashboard worker/scheduler | Yes per process | No | Dashboard `default,dashboard`; scheduler `scheduler`. |
| `JOB_WORKER_CONCURRENCY` | Dashboard worker/scheduler | Yes per process | No | Dashboard current `4`; scheduler exactly `1`. |
| `JOB_WORKER_POLL_SECONDS` | Dashboard worker/scheduler | No | No | Default `1.0`. |
| `JOB_LEASE_SECONDS` | API/workers/scheduler | No | No | Default `120`. |
| `JOB_HEARTBEAT_SECONDS` | Workers/scheduler | No | No | Default `15`; health becomes stale after max(3x, 30 sec). |
| `JOB_DEFAULT_TIMEOUT_SECONDS` | Dashboard worker | No | No | Default `900`. |
| `JOB_MAX_PAYLOAD_BYTES` | API/dashboard worker | No | No | Default `1048576` (1 MiB). |
| `JOB_MAX_RESULT_BYTES` | API/dashboard worker | No | No | Default `10485760` (10 MiB). |
| `JOB_EVENT_STREAM_MAXLEN` | API/workers | No | No | Default `10000`. |
| `JOB_EVENT_HEARTBEAT_SECONDS` | API | No | No | Default `15`. |
| `EVENTS_SUBSCRIPTION_RATE_LIMIT_PER_MINUTE` | API | No | No | Default `30`. |

## Upload/file storage and malware scanning

| Variable | Service | Required? | Secret? | Example / description |
| --- | --- | ---: | ---: | --- |
| `FILE_STORAGE_PROVIDER` | API/dashboard worker | Yes | No | Frozen V1 value `local`, backed by mounted EFS; no certified S3 provider. |
| `FILE_STORAGE_ROOT` | API/dashboard worker | Yes | No | `/data/vip-files` on shared EFS. |
| `FILE_MAX_UPLOAD_BYTES` | API | No | No | Default/current AWS `104857600` (100 MiB). |
| `FILE_ALLOWED_MIME_TYPES` | API | No | No | CSV/JSON/PDF/XLSX/PNG/JPEG/plain-text default list in code; override only by approved policy. |
| `FILE_ALLOWED_EXTENSIONS` | API | No | No | `.csv,.json,.pdf,.png,.jpg,.jpeg,.txt,.xlsx` by default. |
| `FILE_DOWNLOAD_TOKEN_TTL_SECONDS` | API | No | No | Default `300`. |
| `FILE_DOWNLOAD_SIGNING_KEY` | API/dashboard worker | Yes in production | **Yes** | Independent high-entropy signing key. |
| `FILE_STREAM_CHUNK_BYTES` | API | No | No | Default `1048576` (1 MiB). |
| `FILE_RETENTION_DAYS` | API/operations | No | No | Default `365`; coordinate with backup/retention policy. |
| `FILE_MALWARE_SCANNER` | API | Yes in production | No | Must not be `noop`; current AWS `clamav`. |
| `CLAMAV_HOST` | API | Yes for ClamAV | No | Current sidecar value `127.0.0.1`. |
| `CLAMAV_PORT` | API | No | No | Default/current AWS `3310`. |
| `FILE_SCAN_TIMEOUT_SECONDS` | API | No | No | Default `30`. |
| `DEFENDER_COMMAND` | API | No unless Defender selected | No | Default `MpCmdRun.exe`; not used by Linux/ClamAV deployment. |
| `FILE_UPLOAD_RATE_LIMIT_PER_MINUTE` | API | No | No | Default `30`. |
| `FILE_DOWNLOAD_RATE_LIMIT_PER_MINUTE` | API | No | No | Default `120`. |

## API image process control

| Variable | Service | Required? | Secret? | Example / description |
| --- | --- | ---: | ---: | --- |
| `SKIP_PLATFORM_BOOTSTRAP` | API/workers/scheduler/migration | Yes | No | Set `true` on every ECS task. This prevents the image entrypoint from automatically running migrations/seeds; the migration task supplies the explicit release command. |
| `PYTHONPATH` | API image | Image-defined | No | Image sets `/app/src`; do not override. |
| `PYTHONDONTWRITEBYTECODE` | API image | Image-defined | No | Image sets `1`. |
| `PYTHONUNBUFFERED` | API image | Image-defined | No | Image sets `1` for container logs. |

## Web build-time configuration

These are immutable once the SPA is built. Rebuild the web image separately for staging and production. They are not runtime container environment values.

| Variable | Service | Required? | Secret? | Example / description |
| --- | --- | ---: | ---: | --- |
| `VITE_APP_ENV` | Web build | Yes | No | `staging` or `production`. |
| `VITE_API_MODE` | Web build | Yes | No | Must be `live` for staging/production. |
| `VITE_API_BASE_URL` | Web build | Yes | No | Absolute `https://api.<host>/api/v1`. |
| `VITE_API_TIMEOUT_MS` | Web build | No | No | Default `20000`. |
| `VITE_ENABLE_DEVTOOLS` | Web build | Yes | No | `false` for staging/production. |
| `VITE_ENABLE_MOCK_LATENCY` | Web build | Yes | No | `false` for staging/production. |
| `VITE_ALLOW_MOCK_FALLBACK` | Web build | No; forbidden outside local dev | No | Leave unset/false; staging/production fail closed even if set. |
| `VITE_AUTH_CSRF_COOKIE_NAME` | Web build | No | No | Default `vip_csrf_token`; must match API cookie name. |
| `VITE_AUTH_CSRF_HEADER_NAME` | Web build | No | No | Default `X-CSRF-Token`; must match API header name. |
| `API_ORIGIN` | Web Docker build | Yes | No | Absolute API origin without `/api/v1`; inserted into Nginx CSP `connect-src`. |

## Production minimum explicit set

The current AWS task definition explicitly supplies release identity, origins/cookies, security controls, DB/Redis tuning, shared-storage paths, malware scanner, SMTP settings, and scheduler isolation; secrets are injected separately. All other values inherit the code defaults above. Review inherited defaults during every environment change—do not copy local `.env`, Compose fallbacks, B5 demo variables, `VIP_E2E_*`, `VIP_DEMO_*`, `VIP_GOVERNANCE_*`, or test database values into staging/production.
