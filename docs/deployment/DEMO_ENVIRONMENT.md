# Veltrix One demo environment variables

This inventory is for the public **DEMO / POC** deployment only. Values marked secret must be generated independently and entered in the hosting dashboard. They must never be added to Git, a frontend variable, a build argument, a command-line argument, or a deployment log.

## Render frontend/proxy

| Variable | Requirement | Sensitivity | Demo value or source |
| --- | --- | --- | --- |
| `VITE_APP_ENV` | Required | Non-secret | `demo` |
| `VITE_API_MODE` | Required | Non-secret | `live` |
| `VITE_API_BASE_URL` | Required | Non-secret | `/` (same-origin proxy) |
| `VITE_API_TIMEOUT_MS` | Optional | Non-secret | Default `20000` |
| `VITE_AUTH_CSRF_COOKIE_NAME` | Optional | Non-secret | Default `vip_csrf_token` |
| `VITE_AUTH_CSRF_HEADER_NAME` | Optional | Non-secret | Default `X-CSRF-Token` |
| `VITE_ENABLE_DEVTOOLS` | Required | Non-secret | `false` |
| `VITE_ENABLE_MOCK_LATENCY` | Required | Non-secret | `false` |
| `API_ORIGIN` | Required | Non-secret | Exact Railway API origin, with no trailing slash |

`VITE_*` values are embedded in the browser bundle and can never contain secrets. `API_ORIGIN` is also compiled into the Nginx configuration and must contain only the public Railway URL.

## Railway API/process group

### Required non-secret variables

| Variable | Demo value or source |
| --- | --- |
| `APP_ENV` | `demo` |
| `DEBUG` | `false` |
| `LOG_LEVEL` | `INFO` |
| `SERVICE_NAME` | `veltrix-one-demo-api` |
| `ENABLE_DOCS` | `false` |
| `AI_CAPABILITIES_PRODUCTION_READY` | `false` |
| `AI_DEVELOPMENT_MOCK_MODE` | `false` |
| `BUILD_COMMIT_SHA` | Immutable commit deployed from `release/demo` |
| `FRONTEND_URL` | Exact Render URL |
| `INVITATION_ACCEPT_URL` | Exact Render URL plus `/invitations/accept` |
| `CORS_ALLOWED_ORIGINS` | Exact Render origin only |
| `CORS_ALLOW_CREDENTIALS` | `true` |
| `CSRF_TRUSTED_ORIGINS` | Exact Render origin only |
| `TRUSTED_HOSTS` | Exact Railway API hostname only |
| `AUTH_COOKIE_SECURE` | `true` |
| `AUTH_COOKIE_SAMESITE` | `lax` (safe because the browser uses the same-origin Render proxy) |
| `AUTH_COOKIE_DOMAIN` | Empty; keep cookies host-only |
| `GOVERNANCE_FAIL_CLOSED` | `true` |
| `AUDIT_EVENTS_ENABLED` | `true` |
| `AUDIT_DENIED_ACCESS` | `true` |
| `METRICS_ENABLED` | `false` |
| `CONNECTION_ALLOW_PRIVATE_NETWORKS` | `false` |
| `CONNECTION_ALLOW_HTTP` | `false` |
| `CONNECTION_BLOCK_CLOUD_METADATA` | `true` |
| `FILE_STORAGE_PROVIDER` | `local` |
| `FILE_STORAGE_ROOT` | `/data/vip-files` |
| `DASHBOARD_ARTIFACT_ROOT` | `/data/vip-artifacts` |
| `DASHBOARD_EMAIL_OUTBOX_ROOT` | `/data/vip-email-outbox` |
| `PIPELINE_ARTIFACT_ROOT` | `/data/vip-pipeline-artifacts` |
| `FILE_MALWARE_SCANNER` | `noop` — documented demo limitation; trusted synthetic uploads only |
| `DASHBOARD_EMAIL_PROVIDER` | `disabled` |
| `DASHBOARD_DELIVERY_SCHEDULER_ENABLED` | `true` |
| `PIPELINE_SCHEDULER_ENABLED` | `true` |
| `JOB_WORKER_QUEUES` | `default,dashboard` |
| `JOB_WORKER_CONCURRENCY` | `2` |
| `DATABASE_POOL_SIZE` | `3` |
| `DATABASE_MAX_OVERFLOW` | `2` |
| `SKIP_PLATFORM_BOOTSTRAP` | `true` (migration/seeds run once in pre-deploy) |
| `RAILWAY_RUN_UID` | `0` (launcher fixes volume ownership, then drops all processes to `vip`) |

Railway supplies `PORT`; do not set or hardcode it.

### Required secret variables

| Variable | Source |
| --- | --- |
| `DATABASE_URL` | Constructed from Railway PostgreSQL reference variables with the required `postgresql+asyncpg://` scheme |
| `REDIS_URL` | Railway Redis `REDIS_URL` reference variable |
| `CONNECTION_ENCRYPTION_KEY` | New URL-safe base64 32-byte key |
| `DASHBOARD_DOWNLOAD_SIGNING_KEY` | New independent random value |
| `PIPELINE_DOWNLOAD_SIGNING_KEY` | New independent random value |
| `FILE_DOWNLOAD_SIGNING_KEY` | New independent random value |

Generate each secret independently. Do not reuse demo account passwords as signing or encryption keys.

### Optional variables

| Variable | Sensitivity | Demo disposition |
| --- | --- | --- |
| `METRICS_BEARER_TOKEN` | Secret | Omit while `METRICS_ENABLED=false` |
| `DASHBOARD_SMTP_HOST` | Non-secret | Omit |
| `DASHBOARD_SMTP_PORT` | Non-secret | Omit |
| `DASHBOARD_SMTP_USERNAME` | Secret | Omit |
| `DASHBOARD_SMTP_PASSWORD` | Secret | Omit |
| `CLAMAV_HOST` | Non-secret | Omit while scanner is `noop` |
| `CLAMAV_PORT` | Non-secret | Omit while scanner is `noop` |
| `AUTH_COOKIE_DOMAIN` | Non-secret | Keep empty |

### Temporary seed-only secrets

The following variables are used only during the controlled one-time demo seed and must be removed immediately afterward:

- `VIP_DEMO_USER_A_PASSWORD`
- `VIP_DEMO_USER_B_PASSWORD`
- `VIP_DEMO_USER_C_PASSWORD`
- `VIP_GOVERNANCE_ADMIN_PASSWORD`
- `VIP_GOVERNANCE_EDITOR_PASSWORD`
- `VIP_GOVERNANCE_VIEWER_PASSWORD`
- `VIP_GOVERNANCE_RESTRICTED_PASSWORD`

The platform super-admin password is entered interactively and is never stored as an application environment variable.
