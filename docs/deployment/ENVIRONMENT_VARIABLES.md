# Environment variables

`.env.example` is the exhaustive root template. `apps/api/.env.example` is the native API subset. This document explains ownership and production requirements; it does not repeat every tuning default.

| Group | Key variables | Production treatment |
| --- | --- | --- |
| Application | `APP_ENV`, `APP_VERSION`, `BUILD_COMMIT_SHA`, `BUILD_TIMESTAMP`, `LOG_LEVEL` | Set immutable release identity; use `production`; disable debug/docs unless approved |
| Database | `DATABASE_URL`, pool/connect settings | Secret manager; PostgreSQL async URL; TLS/private endpoint |
| Redis | `REDIS_URL`, socket timeout | Secret manager; TLS/auth/private endpoint |
| Authentication | `AUTH_*`, `PASSWORD_*`, `CSRF_TRUSTED_ORIGINS` | Secure cookies, explicit domain/origins, reviewed TTL/rate limits |
| Tenancy/governance | `TENANCY_*`, authorization caches, audit/retention | Keep fail-closed and audit enabled |
| Connection secrets | `CONNECTION_ENCRYPTION_KEY`, version and SSRF controls | Unique managed key; private networks/HTTP off unless explicitly approved |
| Dashboard/export | `DASHBOARD_*` | Unique signing key, durable artifact root, scheduler policy |
| Pipeline | `PIPELINE_*` | Unique signing key, durable artifact root, worker/scheduler policy |
| Jobs/events | `JOB_*`, `EVENTS_*` | Consistent across API/workers; tune against workload |
| Storage | `FILE_*`, ClamAV/Defender settings | Shared encrypted filesystem and fail-closed scanner |
| Email | `DASHBOARD_EMAIL_*` | SMTP host/credentials and verified sender; do not use file mode |
| Monitoring | `METRICS_ENABLED`, `METRICS_BEARER_TOKEN` | Protect metrics with a managed token and private/controlled access |
| Frontend | `VITE_*` | Public build-time values only; never secrets |
| Network | `FRONTEND_URL`, `CORS_ALLOWED_ORIGINS`, `TRUSTED_HOSTS` | Exact HTTPS hosts, no wildcards |

## Required secrets

At minimum, a production environment supplies secret values for `DATABASE_URL`, `REDIS_URL`, `CONNECTION_ENCRYPTION_KEY`, `DASHBOARD_DOWNLOAD_SIGNING_KEY`, `PIPELINE_DOWNLOAD_SIGNING_KEY`, `FILE_DOWNLOAD_SIGNING_KEY`, and `METRICS_BEARER_TOKEN` when metrics are enabled. SMTP credentials are required when the provider requires authentication.

Use different keys per environment. Rotation must account for encrypted connector records and outstanding signed download URLs. Never place secrets in Terraform variables committed to Git, Docker build arguments, `VITE_*`, GitHub workflow output, logs, screenshots, or demo registers.

## Development defaults

Localhost addresses, unauthenticated Redis, replaceable database passwords, file email, non-secure cookies, and enabled API docs are development-only. The Pydantic settings validator rejects several of these choices when `APP_ENV=production`, but infrastructure review remains required.
