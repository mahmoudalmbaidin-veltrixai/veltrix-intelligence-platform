# Veltrix One public demo deployment

> Classification: **DEMO / POC ENVIRONMENT**. This design is not production, high availability, disaster recovery, guaranteed backup, compliance certification, penetration testing, or an enterprise SLA.

## 1. Architecture

The originally preferred Render Static Site → Railway API split is not compatible with the certified cookie authentication design. The browser must read the non-HttpOnly CSRF cookie and echo it in a header, but JavaScript on `onrender.com` cannot read a host-only cookie issued by `up.railway.app`. Render static rewrites are not a general authenticated reverse proxy for POST, upload, download, and SSE traffic.

The compatible demo topology is:

```text
Internet / HTTPS
       |
       v
Render free Web Service (existing Nginx frontend image)
  - serves Vue SPA
  - same-origin proxy for /auth, /api, /health, /ready
       |
       v HTTPS
Railway public API service
  - FastAPI process
  - generic/dashboard job worker and scheduler tick
  - pipeline worker
  - one shared local filesystem/volume
       |                    |
       v                    v
Railway PostgreSQL      Railway Redis
```

Railway does not support sharing one volume between multiple services. Co-locating the three existing Python entry points in a single **demo-only process group** preserves asynchronous pipelines, exports, files, and scheduler behavior without changing their business logic. A separate scheduler service is not required because both schedule ticks already run in the generic worker.

## 2. Service disposition

| Runtime | Disposition | Reason |
| --- | --- | --- |
| Render Nginx frontend/proxy | REQUIRED | SPA, HTTPS URL, same-origin cookie/CSRF contract |
| FastAPI | REQUIRED | Application API and authentication |
| Generic/dashboard worker | REQUIRED | Jobs, quality work, exports, deliveries, scheduler ticks |
| Pipeline worker | REQUIRED | Published pipeline execution |
| Separate scheduler | DISABLED FOR DEMO | Scheduler ticks are already inside the generic worker |
| PostgreSQL | REQUIRED | System of record and tenant-scoped data |
| Redis | REQUIRED | Job queues, rate limiting, events, cache/coordination |
| ClamAV | DISABLED FOR DEMO | Not needed at startup; only trusted synthetic uploads are allowed |
| SMTP | DISABLED FOR DEMO | Email delivery is not required for the demonstration |

## 3. Git and immutable release

- Source branch: `feat/vip-productization-p2`
- Source/previous known-good SHA: `8f4ccf7805fc0db9ffb6c4c5d311417237ff2`
- Deployment branch: `release/demo`
- Deployment SHA: the exact commit selected by Render/Railway and copied into `BUILD_COMMIT_SHA`

Never deploy an uncommitted worktree. Record the resulting commit with `git rev-parse HEAD` and compare `/api/v1/version` after deployment.

## 4. Repository deployment process

1. Run the complete quality gate and repository secret scan.
2. Commit only the reviewed demo deployment changes on `release/demo`.
3. Push the immutable commit and confirm both hosts build that exact SHA.
4. Create Railway PostgreSQL and Redis before the API service.
5. Deploy the Railway API/process group and verify `/ready`.
6. Perform the controlled seed through an interactive Railway shell.
7. Deploy the Render Nginx frontend/proxy with the Railway public origin.
8. Run the post-deployment checklist in section 15.

## 5. Environment variables

Use [DEMO_ENVIRONMENT.md](DEMO_ENVIRONMENT.md). It is authoritative for required/optional and secret/non-secret classification. Do not import a local `.env` containing credentials into either provider.

## 6. Railway setup

### Project and data services

1. Sign in to Railway and click **New Project** → **Empty Project**. Rename it `veltrix-one-demo`.
2. Open the environment menu. Railway initially labels the environment `production`; rename it to `demo` so the platform environment also reflects the PoC classification.
3. Click **+ New** → **Database** → **PostgreSQL**. Rename the service `Postgres`.
4. Click **+ New** → **Database** → **Redis**. Rename the service `Redis`.
5. Keep both datastores private. Do not generate public database or Redis domains.

### API/process-group service

1. Click **+ New** → **GitHub Repo** and select `mahmoudalmbaidin-veltrixai/veltrix-intelligence-platform`.
2. Rename the service `veltrix-one-api`.
3. In **Settings → Source**, select branch `release/demo` and set **Root Directory** to `/apps/api`.
4. In **Settings → Build**, select the repository `Dockerfile` (`/apps/api/Dockerfile`). Do not use native/Railpack detection.
5. In **Settings → Deploy**, set **Pre-deploy Command** to:

   ```text
   alembic upgrade head && python -m vip_api.cli seed-governance && python -m vip_api.cli seed-connection-types
   ```

6. Set **Custom Start Command** to:

   ```text
   /app/scripts/demo-process-group.sh
   ```

7. Set **Healthcheck Path** to `/ready`, timeout `300` seconds, restart policy `ON_FAILURE`, one replica, and no deployment overlap. More than one replica would duplicate the worker processes and local filesystem.
8. Under **Volumes**, click **Add Volume** and mount it at `/data`. The free/trial volume limit may be only 0.5 GB; keep demo artifacts small.
9. Under **Networking → Public Networking**, click **Generate Domain**. Record the exact hostname as `RAILWAY_API_HOST` and origin as `https://RAILWAY_API_HOST`.
10. Under **Variables**, add every required backend variable from `DEMO_ENVIRONMENT.md`. Use references rather than copied credentials:

    ```text
    DATABASE_URL=postgresql+asyncpg://${{Postgres.PGUSER}}:${{Postgres.PGPASSWORD}}@${{Postgres.PGHOST}}:${{Postgres.PGPORT}}/${{Postgres.PGDATABASE}}
    REDIS_URL=${{Redis.REDIS_URL}}
    ```

11. Generate independent values for the four secret key variables. Railway can generate values with its variable generator; never paste them into source or chat.
12. Set `TRUSTED_HOSTS` to `RAILWAY_API_HOST` without `https://`, and set `BUILD_COMMIT_SHA` to the immutable release SHA.
13. Deploy the staged changes. Confirm `GET https://RAILWAY_API_HOST/ready` returns `200` and both dependency statuses are `healthy`.

Do **not** enable Railway Serverless for this service. The required workers poll PostgreSQL/Redis and are not sleep-compatible; enabling it would not reliably reduce cost and can interrupt queued work.

## 7. Render setup

The compatible service type is **Web Service**, not Static Site, because same-origin authenticated proxying is required.

### Blueprint path

1. Sign in to Render and click **New** → **Blueprint**.
2. Connect `mahmoudalmbaidin-veltrixai/veltrix-intelligence-platform`.
3. Select branch `release/demo`; Render reads `/render.yaml`.
4. When prompted for `API_ORIGIN`, enter `https://RAILWAY_API_HOST` with no trailing slash. It is public configuration, not a secret.
5. Confirm the service is named `veltrix-one-demo`, runtime **Docker**, plan **Free**, Dockerfile `infra/containers/web/Dockerfile`, context repository root, and health path `/healthz`.
6. Click **Apply**. Record the generated `https://...onrender.com` URL.
7. Return to Railway and set `FRONTEND_URL`, `CORS_ALLOWED_ORIGINS`, and `CSRF_TRUSTED_ORIGINS` to that exact Render origin. Set `INVITATION_ACCEPT_URL` to the same origin plus `/invitations/accept`, then redeploy the API once.
8. In Render, ensure `API_ORIGIN` still matches the final Railway URL and trigger **Manual Deploy → Deploy latest commit** if it changed.

The Nginx image serves Vue history routes through `/index.html`; direct `/login`, `/dashboard`, `/workspaces`, `/pipelines`, `/datasets`, and `/admin` loads therefore use SPA fallback. Only `/auth/*`, `/api/*`, `/health`, and `/ready` are proxied. `/metrics`, `/docs`, `/redoc`, and `/openapi.json` are intentionally not proxied by the public frontend.

## 8. Database migrations

- Command: `alembic upgrade head`
- Timing: Railway pre-deploy, after image build and before the new service starts
- Owner: the single API/process-group service
- Failure behavior: a non-zero exit prevents the new deployment from becoming active

The start process sets `SKIP_PLATFORM_BOOTSTRAP=true`, so migrations do not race during API or worker startup. Do not add the pre-deploy command to PostgreSQL, Redis, or any second service.

## 9. Synthetic seed data

Do not copy a development database. After migrations and readiness pass, open an interactive shell to the running API container (Railway CLI `railway ssh`) and create the platform operator:

```text
python -m vip_api.cli create-user --username demo-platform-admin --email <owner-email> --display-name "Demo Platform Administrator"
python -m vip_api.cli grant-platform-admin --email <owner-email>
```

The first command prompts for a password without echoing it. Use a unique password from the team password manager.

In the same interactive shell, enter unique temporary passwords without echo, export them, run the idempotent seeds, then unset them:

```sh
read -s VIP_DEMO_USER_A_PASSWORD; export VIP_DEMO_USER_A_PASSWORD
read -s VIP_DEMO_USER_B_PASSWORD; export VIP_DEMO_USER_B_PASSWORD
read -s VIP_DEMO_USER_C_PASSWORD; export VIP_DEMO_USER_C_PASSWORD
read -s VIP_GOVERNANCE_ADMIN_PASSWORD; export VIP_GOVERNANCE_ADMIN_PASSWORD
read -s VIP_GOVERNANCE_EDITOR_PASSWORD; export VIP_GOVERNANCE_EDITOR_PASSWORD
read -s VIP_GOVERNANCE_VIEWER_PASSWORD; export VIP_GOVERNANCE_VIEWER_PASSWORD
read -s VIP_GOVERNANCE_RESTRICTED_PASSWORD; export VIP_GOVERNANCE_RESTRICTED_PASSWORD
python -m vip_api.cli seed-multitenancy-demo
python -m vip_api.cli configure-governance-demo
python -m vip_api.cli seed-dataset-catalogs
python -m vip_api.cli seed-semantic-layer
python -m vip_api.cli seed-dashboard-governance
python -m vip_api.cli seed-dashboard-demo
unset VIP_DEMO_USER_A_PASSWORD VIP_DEMO_USER_B_PASSWORD VIP_DEMO_USER_C_PASSWORD
unset VIP_GOVERNANCE_ADMIN_PASSWORD VIP_GOVERNANCE_EDITOR_PASSWORD
unset VIP_GOVERNANCE_VIEWER_PASSWORD VIP_GOVERNANCE_RESTRICTED_PASSWORD
```

This creates synthetic tenant owners/workspace admins, an editor/analyst, viewers, and restricted governance personas. Do not publish the credentials. Store them only in the team password manager and distribute them separately to authorized demonstrators.

## 10. Demo accounts procedure

- Platform/super admin: created interactively once; never auto-created and never assigned a default password.
- Organization/workspace admins: seeded from temporary secret input.
- Standard analyst/editor and viewers: seeded from temporary secret input.
- Credentials: password manager only; never Git, README, screenshots, browser artifacts, or provider logs.
- Rotation: run the platform password-reset operation through an authenticated platform-admin session or re-run the exact demo seed with newly entered temporary values, then remove those values.

## 11. Health and public endpoint policy

- Render liveness: `/healthz` → plain `ok` from Nginx.
- API liveness: `/health` → service name/version only.
- API readiness: `/ready` → PostgreSQL and Redis status only.
- API docs/OpenAPI: disabled (`ENABLE_DOCS=false`).
- Metrics: disabled (`METRICS_ENABLED=false`).
- Admin APIs: remain authenticated and RBAC-protected; no separate debug admin endpoint is enabled.

## 12. Rollback

```text
Current deployment SHA: BUILD_COMMIT_SHA recorded for the active release/demo deployment
Previous deployment SHA: 8f4ccf7805fc0db9ffb6c4c5d311417237ff2
```

1. Identify the previous known-good immutable commit; never roll back by rewriting branch history.
2. In Railway, choose the prior deployment while it remains in retention, or redeploy the previous commit from Git. Confirm migrations are backward-compatible before any application rollback; do not run `alembic downgrade` automatically.
3. In Render, use **Manual Deploy → Deploy a specific commit** and select the same previous SHA.
4. Confirm `/api/v1/version`, `/ready`, login, tenant selection, and one read-only dashboard.
5. If a forward migration is incompatible with the old application, restore the clean demo database from an operator-created backup or rebuild and reseed it. Do not improvise manual schema edits.

Railway Free/Trial removed-image retention is short, so the Git SHA is the durable rollback reference.

## 13. Known limitations

- Render Free Web Services sleep after idle time; the first frontend request can take about one minute.
- Railway Free includes only a small monthly credit; the always-running workers and datastores may exceed it. The one-time trial credit expires.
- Railway Free deployment is subject to regional peak-hour restrictions and limited image retention.
- The single Railway process group is not HA and must remain one replica.
- The Railway volume is small on Free/Trial and is not a backup guarantee.
- Local file storage is persistent only while the Railway volume exists; no cross-region replication exists.
- Malware scanning is disabled. Only trusted staff with demo credentials may upload synthetic files.
- SMTP is disabled. Password reset, invitations, notifications, and scheduled email reports do not send email.
- Redis capacity is limited and Redis loss can discard transient queue/cache/event state.
- No guaranteed database backups, DR, SLA, penetration test, SOC 2, or ISO 27001 claim is made.
- Free/trial resources can restart, suspend, or become unavailable when credits/limits expire.

## 14. Troubleshooting

- `422`/startup validation: check the exact variable names and public-demo security values in `DEMO_ENVIRONMENT.md`.
- Database scheme error: Railway's native URL uses `postgresql://`; construct `DATABASE_URL` with `postgresql+asyncpg://` as shown above.
- `/ready` is `503`: inspect Railway service logs, then verify both reference variables and datastore service health.
- Render `502`: verify `API_ORIGIN`, the Railway public domain, and Railway `/health` directly.
- Login succeeds but mutation returns `CSRF_VALIDATION_FAILED`: ensure the browser calls the Render origin (not Railway directly), cookie domain is empty, `SameSite=lax`, and `CSRF_TRUSTED_ORIGINS` exactly matches Render.
- SPA refresh returns an error: verify Nginx is the Render Web Service image and `/healthz` works; do not configure a catch-all proxy.
- Upload returns `413`: confirm the deployed Nginx template includes `client_max_body_size 100m`; also respect application upload limits and the small demo volume.
- Jobs remain queued: inspect all three process log prefixes and query worker heartbeats; redeploy the process group if either worker exited.
- Artifact download is missing: confirm the `/data` volume is mounted and all artifact roots remain under it.

## 15. Post-deployment validation

Record PASS/FAIL and sanitized evidence for every item:

1. Frontend `GET /` and direct SPA paths `/login`, `/dashboard`, `/workspaces`, `/pipelines`, `/datasets`, `/admin`.
2. Backend `/health`, `/ready`, and `/api/v1/version`; compare the reported commit/environment.
3. Public checks for `/debug`, `/docs`, `/redoc`, `/openapi.json`, `/metrics`, and `/internal` on the Railway origin. Expected: `404` except protected/disabled behavior explicitly approved.
4. Login, `/auth/me`, idle/session persistence, invalid password, refresh, logout, and post-logout protected-page rejection.
5. Browser cookie attributes: `Secure`, `HttpOnly` on access/refresh, host-only domain, `SameSite=Lax`; CSRF cookie readable only on the Render origin.
6. CORS preflight from the exact Render origin passes; an unrelated origin does not receive an allow-origin header.
7. Platform admin, organization admin, workspace admin, editor/analyst, viewer, and restricted-user negative authorization cases.
8. Cross-organization and cross-workspace ID substitution fails closed.
9. Workspace list/open/switch, connections, datasets, pipelines, dashboards, exports, notifications, and admin pages.
10. One safe synthetic connection, one safe pipeline execution, and PDF/PNG/CSV export plus protected download.
11. Chromium smoke certification; run Firefox/WebKit suites when the public environment and credentials are available.
12. Lightweight timings for first frontend load, warm frontend load, health, login, dashboard, dataset, and pipeline list. Do not load test.

Never store passwords, cookies, JWT/session tokens, signed download URLs, or secret variable values in validation evidence.

## 16. Expected cost

- Render frontend/proxy: Free Web Service, subject to free-hour, bandwidth, build-minute, sleep, and ephemeral-runtime limits.
- Railway: Free plan currently provides `$1` monthly usage credit; the new-account trial provides a one-time `$5` credit for up to 30 days. Railway bills actual RAM, CPU, egress, and volume usage. The required always-running API/workers/PostgreSQL/Redis topology may exceed `$1/month`; do not promise a permanent `$0` deployment.
- Railway Hobby: `$5/month` minimum if Free credit is insufficient; that subscription amount counts toward usage.

Set a Railway hard usage limit before sharing the URL. Actual cost must be read from the Railway Usage page after a representative demo because application/database memory usage is workload-dependent.
