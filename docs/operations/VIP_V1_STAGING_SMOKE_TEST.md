# VIP V1 Staging Smoke Test

Release under test: `4e97591845a93037d6e54b0237bcb3208d1b2696`  
Expected Alembic head: `20260808_0025`

Use synthetic staging data and a securely created staging account. Never import production/customer data for this test. Record UTC time, operator, browser, API/web digests, task-definition revisions, evidence links, and IDs safe for operational records. Do not record passwords, tokens, cookies, connector credentials, or file contents.

## A. Infrastructure smoke

Run the repository script with staging URLs:

```bash
infra/aws/scripts/smoke.sh \
  staging \
  "https://app.staging.<domain>" \
  "https://api.staging.<domain>"
```

The script must verify web `/healthz`, API `/health`, API `/ready` including PostgreSQL/Redis, `/api/v1/version`, `X-Content-Type-Options`, and HTTP-to-HTTPS redirect. It requires API HSTS when invoked for `production`; staging intentionally does not claim the application's production-only HSTS behavior.

- [ ] Web `GET /healthz` returns HTTP 200 and `ok`.
- [ ] API `GET /health` returns HTTP 200 and `status=healthy`.
- [ ] API `GET /ready` returns HTTP 200, `status=ready`, database/Redis healthy.
- [ ] API `GET /api/v1/version` reports `environment=staging` and the full frozen SHA.
- [ ] Web and API task definitions reference the recorded ECR digests and matching OCI revision labels.
- [ ] TLS certificate/chain/hostname are valid; HTTP redirects to HTTPS; TLS 1.2+ only.
- [ ] Expected web/API security headers are present; no wildcard CORS/CSRF/trusted-host configuration exists.
- [ ] RDS and Redis have no public endpoint/ingress; ECS tasks have no public IP.
- [ ] Dashboard worker, pipeline worker, and scheduler are at desired running count with fresh DB heartbeats.
- [ ] Scheduler desired/running count is exactly 1; scheduler flags are false on API/scalable workers.
- [ ] EFS is mounted at `/data`; no application artifact path is container-local.
- [ ] No unexpected ERROR/CRITICAL log burst or alarm is active.

## B. Authenticated core workflow

Run in Chromium, Firefox, and WebKit unless the change record explicitly documents a smaller infrastructure-only recheck approved by Release Engineering.

### Identity and tenancy

- [ ] Login succeeds with the secure staging test account.
- [ ] Invalid login is rejected without user enumeration or sensitive error detail.
- [ ] Correct organization/workspace context is visible and switchable.
- [ ] Create or select a staging-only organization and workspace using authorized UI flows.
- [ ] Logout invalidates the session; a new login succeeds.

### Connection and import

- [ ] Create/test an approved staging connection using a non-production source and TLS credentials.
- [ ] Connector secret is not returned to the browser or visible in logs.
- [ ] Import a small synthetic CSV; malware scan and validation pass; dataset appears.
- [ ] Import a small synthetic XLSX; workbook validation passes; dataset appears.
- [ ] Preview/schema/row counts are plausible for both imports.
- [ ] Replace an API task and confirm the uploaded files remain available from shared EFS.

### Dataset and pipeline

- [ ] Open a dataset, inspect metadata/preview/quality, and verify tenant isolation context.
- [ ] Build/save/publish a minimal pipeline using synthetic data.
- [ ] Run it asynchronously; pipeline worker claims it, heartbeats remain fresh, and run completes.
- [ ] Verify output/artifact and safe status/error reporting.
- [ ] Replace the pipeline worker task and confirm completed artifact remains accessible.
- [ ] Create a staging pipeline schedule due within the test window; singleton scheduler enqueues once and the run completes once.

### Dashboard, publish, viewer, and exports

- [ ] Create/edit/save a dashboard with a configured widget using the synthetic dataset.
- [ ] Publish the dashboard and open the published viewer through the supported flow.
- [ ] Viewer renders expected data without edit controls or cross-tenant leakage.
- [ ] Request PDF export; dashboard worker completes it; signed download succeeds.
- [ ] Request PNG export; dashboard worker completes it; signed download succeeds.
- [ ] Replace the dashboard worker/API task and confirm completed PDF/PNG artifacts remain accessible while valid.

### Scheduler, email, notifications, and preferences

- [ ] Create a dashboard delivery schedule due within the test window.
- [ ] Singleton scheduler enqueues one delivery and dashboard worker processes it once.
- [ ] SMTP provider accepts the tagged staging message; delivery/bounce/complaint monitoring is visible.
- [ ] Notification appears, can be marked read, and read state survives refresh.
- [ ] Notification preferences can be changed, saved, refreshed, and restored to the intended test baseline.
- [ ] Account/session preferences, including idle-session behavior relevant to deployment, load and persist.

## C. Operational assertions

- [ ] API 5xx count and p95 latency remain within staging thresholds during the run.
- [ ] No Redis evictions; queue depth returns to baseline; no stale leases/dead letters remain unexplained.
- [ ] RDS connections stay within the pool budget; no unexpected slow-query/lock alarm.
- [ ] EFS latency/mount health is normal; files and generated artifacts are durable.
- [ ] Logs contain correlation/service context but no passwords, tokens, cookies, connection URLs/secrets, or customer payloads.
- [ ] Backup jobs and alert delivery are enabled; managed restore drill evidence is linked separately.

## D. Cleanup and result

- [ ] Remove only the synthetic staging organizations/users/connections/files/schedules created for this test through supported application operations.
- [ ] Do not run cleanup/demo commands against production.
- [ ] Preserve non-sensitive screenshots/log queries/result IDs according to evidence retention policy.

```text
Result: PASS / FAIL
Operator:
Started UTC:
Completed UTC:
Application SHA:
API digest:
Web digest:
Alembic head:
Browsers:
Infrastructure smoke evidence:
Authenticated workflow evidence:
Observed alarms/issues:
Cleanup evidence:
Approver:
```

Any incorrect SHA/head, duplicate schedule execution, lost file/artifact after task replacement, unavailable worker, email failure, tenant leakage, secret exposure, or unexplained Critical/High security result is a failed staging gate.
