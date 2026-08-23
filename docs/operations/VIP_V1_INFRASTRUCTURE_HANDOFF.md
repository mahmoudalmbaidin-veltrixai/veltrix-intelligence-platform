# VIP V1 Infrastructure Handoff

Status: authoritative staging and production deployment handoff  
Application owner: VIP application team  
Execution owner: infrastructure/DevOps team

## Release invariant

```text
FINAL VIP V1 APPLICATION SHA
4e97591845a93037d6e54b0237bcb3208d1b2696

Branch
feat/post-core-p1-p2-connectors-scheduling-versions

Alembic HEAD
20260808_0025

Freeze status
A — VIP V1 APPLICATION FROZEN AND READY FOR INFRASTRUCTURE HANDOFF
APPLICATION FREEZE APPROVED

Certified application status
P0 = 0
P1 = 0
Agreed P2 remediation = complete
Chromium 59/59; Firefox 59/59; WebKit 59/59
```

Deploy the commit, never a moving branch or `latest` tag. Build both images from the exact Git tree at this SHA, record OCI revision labels, push them, resolve registry digests, and deploy only `repository@sha256:...` references. Infrastructure commits and state are separate from the frozen application. No application source modification is permitted during deployment.

Any genuine application P0/P1 that needs source code stops the deployment and creates a new release candidate, SHA, certification run, and handoff revision.

## Authoritative document set

- `VIP_V1_INFRASTRUCTURE_HANDOFF.md` — architecture, service contract, operational requirements, and freeze policy.
- `VIP_V1_DEPLOYMENT_CHECKLIST.md` — ordered deployment and acceptance gates.
- `VIP_V1_ENVIRONMENT_VARIABLES.md` — complete application configuration inventory.
- `VIP_V1_SECRETS_INVENTORY.md` — secret ownership, injection, and rotation.
- `VIP_V1_STAGING_SMOKE_TEST.md` — infrastructure and authenticated product smoke procedure.
- `VIP_V1_ROLLBACK_RUNBOOK.md` — application, schema, data, and storage recovery.

Supporting detail remains in `PRODUCTION_ARCHITECTURE.md` and `PRODUCTION_RUNBOOK.md`. If they conflict with this set, this set wins.

## Repository handoff audit

No AWS provisioning was executed during this handoff. Local Docker Compose configuration parsed successfully. Terraform 1.13.2 `fmt -check`, `validate`, and the mocked `production_plan` test passed in a container (1 test, 0 failures; mocked providers made no AWS calls); Bash syntax checking passed for all three deployment scripts. Protected CI execution, a real account-backed reviewed plan, and staging apply/rehearsal remain mandatory.

| Classification | Files | Disposition |
| --- | --- | --- |
| READY FOR HANDOFF | `apps/api/Dockerfile`, `apps/api/scripts/docker-entrypoint.sh`, `apps/api/scripts/worker-health.py`, `infra/containers/web/Dockerfile`, `infra/containers/web/nginx.conf.template` | Frozen build/runtime contracts. Do not edit. |
| READY FOR HANDOFF | The six `VIP_V1_*` documents in this directory | Authoritative handoff package. |
| READY FOR HANDOFF | `docs/operations/PRODUCTION_ARCHITECTURE.md`, `docs/operations/PRODUCTION_RUNBOOK.md` | Supporting references with final release invariants aligned. |
| READY FOR HANDOFF | `infra/aws/.terraform.lock.hcl`, `infra/aws/tests/production_plan.tftest.hcl` | Provider lock and mocked production controls test; test passed locally. Commit on the separate infrastructure branch. |
| DRAFT | `infra/aws/versions.tf`, `locals.tf`, `network.tf`, `security.tf`, `registry.tf`, `database.tf`, `redis.tf`, `storage.tf`, `secrets.tf`, `ecs.tf`, `load_balancer.tf`, `waf.tf`, `email.tf`, `monitoring.tf`, `backup.tf`, `outputs.tf` | AWS implementation is formatted/valid and mocked plan test passes, but remains uncommitted/unprovisioned. Infra team must run CI security scan, a real reviewed account plan, and staging apply before acceptance. Release pin and Alembic head are aligned. |
| DRAFT | `infra/aws/scripts/deploy.sh`, `rollback.sh`, `smoke.sh`; `.github/workflows/quality-gate.yml`; `.github/workflows/deploy-certified-release.yml` | Bash syntax/Compose checks pass and release pins are aligned, but commands require protected CI execution and staging rehearsal. |
| REQUIRES INFRA TEAM CONFIGURATION | `infra/aws/backend.hcl.example`, `infra/aws/terraform.tfvars.example` | Supply approved account/regions, encrypted remote state, domain/hosted zone, alert mailbox, SMTP secret ARN, image digests, and environment-specific values. Never commit generated `.tfvars` containing sensitive data. |
| REQUIRES INFRA TEAM CONFIGURATION | GitHub `staging`/`production` environments and OIDC roles | Configure protected approvals plus `AWS_DEPLOY_ROLE_ARN`, `APP_HOSTNAME`, `API_HOSTNAME`, `API_ECR_REPOSITORY`, `WEB_ECR_REPOSITORY`, `ECS_CLUSTER`, `PRIVATE_SUBNET_IDS`, `ECS_SECURITY_GROUP_ID`, and `RDS_IDENTIFIER`. |
| DEVELOPMENT ONLY | `docker-compose.yml`, `.env.example`, `apps/api/.env.example`, `infra/postgres/Dockerfile` | Local/QA reference. Public ports, local passwords, QA seeds, file email, and named volumes are not production patterns. |
| OBSOLETE / GENERATED | `infra/aws/.terraform/` | Local provider cache only; do not review, distribute, or commit it as handoff content. Recreate with `terraform init`. |
| OBSOLETE FOR DEPLOYMENT | `docs/operations/DEPLOYMENT_CHECKLIST.md`, `PRODUCTION_READINESS_REPORT.md`, `LOCAL_RESTORE_DRILL.md` | Historical audit/evidence only. Do not use as release authority or as proof of a managed restore. |

## Intended AWS architecture

The current IaC target is AWS ECS on Fargate in `me-south-1` (Bahrain), not Kubernetes. Bahrain is GCC hosting, not Saudi data residency; Legal/Security and the customer must approve the location before provisioning. If KSA residency is required, stop and select an approved in-country target, then revalidate the infrastructure without changing application code.

```text
Users
  -> Route 53 public DNS
  -> ACM public certificate / HTTPS
  -> AWS WAF + Shield Standard
  -> public Application Load Balancer
       app.<domain> -> private VIP Web ECS tasks (Nginx static SPA)
       api.<domain> -> private VIP API ECS tasks + ClamAV sidecar
                         -> private RDS PostgreSQL 17.10
                         -> private ElastiCache Redis 7.1 over TLS
                         -> encrypted EFS mounted at /data
       browser SPA calls https://api.<domain>/api/v1

  private ECS services using the API image:
       dashboard/export worker
       pipeline worker
       singleton scheduler
       one-off migration/bootstrap task

  SMTP provider <- API/dashboard worker as required
  Secrets Manager + KMS -> task secret injection
  CloudWatch/Route 53/SNS -> logs, metrics, uptime, alarms
  AWS Backup -> RDS + EFS, encrypted primary and cross-region vaults
  ECR -> immutable API and web image digests
```

The web container does not proxy API requests. `VITE_API_BASE_URL` is baked into the SPA and the browser calls the API hostname directly. This makes DNS, CORS, CSRF, cookie-domain, and certificate configuration a single coordinated release input.

## Service matrix

| Service | Purpose | Command / entrypoint | Required dependencies | Scale model |
| --- | --- | --- | --- | --- |
| Web | Serves the built Vue SPA and security headers | Nginx image entrypoint: `nginx -g 'daemon off;'`, port 8080 | ALB; browser access to API hostname | 2 initial tasks; horizontal by request/CPU/latency |
| API | Authentication, tenancy, datasets, pipelines, dashboards, files, administration | `/app/scripts/docker-entrypoint.sh` -> `uvicorn vip_api.main:app --host 0.0.0.0 --port 8000 --no-access-log`; set `SKIP_PLATFORM_BOOTSTRAP=true` | PostgreSQL, Redis, shared storage, ClamAV, SMTP for email flows | 2 initial tasks; horizontal, bounded by DB pool |
| Pipeline Worker | Claims and executes pipeline runs | `python -m vip_api.pipelines.worker` | PostgreSQL, Redis, `/data/vip-pipeline-artifacts`, connector egress | Independently horizontal; DB leases/`SKIP LOCKED` protect claims |
| Dashboard/Export Worker | Generic jobs, dashboard rendering/export, delivery/email | `python -m vip_api.jobs.worker` with `JOB_WORKER_QUEUES=default,dashboard` | PostgreSQL, Redis, `/data/vip-artifacts`, `/data/vip-files`, SMTP | Independently horizontal; start at 1, scale by queue age/depth |
| Scheduler | Enqueues recurring pipeline and dashboard delivery work | `python -m vip_api.jobs.worker` with queue `scheduler`, concurrency `1`, both scheduler flags `true` | PostgreSQL, Redis | **Exactly one logical replica**; ECS desired count 1, stop-before-start |
| PostgreSQL | Durable system of record, jobs, leases, schedules, audit | AWS RDS PostgreSQL 17.10 | Private data subnets, TLS, backups | Multi-AZ production; vertical first; pool budget required |
| Redis | Queue acceleration, caches, rate limits, events, token consumption | ElastiCache Redis 7.1 managed service | Private TLS endpoint and AUTH | 2-node Multi-AZ production; `noeviction` |
| File Storage | Uploads and generated artifacts using frozen filesystem providers | Encrypted EFS access point mounted at `/data` | NFS 2049 only from ECS SG, KMS, backups | Shared/durable; elastic throughput |
| Email | SMTP delivery of dashboard notifications/exports and auth email | External SMTP endpoint, STARTTLS on 587 by current IaC | Verified sender/domain, credentials, egress, event monitoring | Provider-managed; quotas and bounces monitored |
| Migration | One release-scoped schema/baseline task | `alembic upgrade head`, verify `20260808_0025`, then `seed-governance` and `seed-connection-types` | PostgreSQL and runtime settings | One-off; never a replicated service |

API, workers, scheduler, and migration use the same immutable API image. Scheduler flags must be false on API and scalable workers and true only on the singleton scheduler.

## Build matrix

Check out the exact SHA in detached state or verify `git rev-parse HEAD` before building. Convenience tags are not deployment identities.

| Artifact | Image name/tag | Dockerfile | Context | Required build inputs | Runtime command/health |
| --- | --- | --- | --- | --- | --- |
| API | `vip-api:4e97591845a9` | `apps/api/Dockerfile` | `apps/api` | No Docker build args. Add OCI labels `org.opencontainers.image.revision=4e975...`, `created=<UTC>`, `version=1.0.0`. `BUILD_COMMIT_SHA` is an ECS runtime environment variable, not a Docker ARG. | Default API entrypoint; `GET http://127.0.0.1:8000/health` |
| Web | `vip-web:4e97591845a9` | `infra/containers/web/Dockerfile` | repository root | `VITE_APP_ENV=staging|production`, `VITE_API_BASE_URL=https://api.<host>/api/v1`, `VITE_API_MODE=live`, `VITE_ENABLE_DEVTOOLS=false`, `VITE_ENABLE_MOCK_LATENCY=false`, and required `API_ORIGIN=https://api.<host>`; add the same OCI revision labels. | Nginx on 8080; `GET /healthz` returns `ok` |

Reference build commands:

```bash
git checkout --detach 4e97591845a93037d6e54b0237bcb3208d1b2696
test "$(git rev-parse HEAD)" = "4e97591845a93037d6e54b0237bcb3208d1b2696"

docker build --pull \
  --label org.opencontainers.image.revision=4e97591845a93037d6e54b0237bcb3208d1b2696 \
  --tag vip-api:4e97591845a9 apps/api

docker build --pull --file infra/containers/web/Dockerfile \
  --build-arg VITE_APP_ENV=staging \
  --build-arg VITE_API_MODE=live \
  --build-arg VITE_API_BASE_URL=https://api.staging.<domain>/api/v1 \
  --build-arg VITE_ENABLE_DEVTOOLS=false \
  --build-arg VITE_ENABLE_MOCK_LATENCY=false \
  --build-arg API_ORIGIN=https://api.staging.<domain> \
  --label org.opencontainers.image.revision=4e97591845a93037d6e54b0237bcb3208d1b2696 \
  --tag vip-web:4e97591845a9 .
```

Scan both final images for Critical/High vulnerabilities before push. Push, resolve ECR digests, and use only those digests in Terraform/ECS. Production requires its own web build because the API URL is compiled into the SPA.

## DNS, TLS, cookies, CORS, and CSRF

No company domain is assumed. Required placeholders are:

| Environment | Web | API |
| --- | --- | --- |
| Staging | `app.staging.<domain>` | `api.staging.<domain>` |
| Production | `app.<domain>` | `api.<domain>` |

Use sibling names under the same registrable root. Configure `AUTH_COOKIE_DOMAIN=.<domain>` for production (and the appropriate staging parent), exact HTTPS `CORS_ALLOWED_ORIGINS` and `CSRF_TRUSTED_ORIGINS`, `FRONTEND_URL`, and `INVITATION_ACCEPT_URL`. Use `AUTH_COOKIE_SECURE=true`, `AUTH_COOKIE_SAMESITE=lax`, and credentialed CORS. Session cookies are HttpOnly; the CSRF cookie is readable by the SPA for double-submit protection. Do not use wildcard CORS, CSRF origins, or trusted hosts.

ACM must cover both hostnames. Enforce HTTPS only, HTTP-to-HTTPS 301, TLS 1.2+, valid public certificates, and secure cookies. The current ALB policy permits TLS 1.2/1.3. The API emits HSTS in production. Enable HSTS on the web/edge only after every affected hostname/subdomain is permanently HTTPS.

## Network and traffic matrix

Only the ALB and DNS endpoints are public. ECS tasks have no public IP. RDS, Redis, EFS, workers, scheduler, migration, and secrets endpoints remain private/restricted. Default-deny security groups and least-privilege egress apply.

| Source | Destination | Port/protocol | Purpose |
| --- | --- | --- | --- |
| Internet | ALB | 443/TCP; 80 only for redirect | Web/API ingress |
| ALB SG | Web ECS SG | 8080/TCP | SPA |
| ALB SG | API ECS SG | 8000/TCP | API and health |
| API/workers/scheduler/migration SG | RDS SG | 5432/TCP TLS | Application database |
| API/workers/scheduler/migration SG | Redis SG | 6379/TCP TLS | Queues/cache/rate limits/events |
| API/dashboard/pipeline SG | EFS SG | 2049/TCP TLS/IAM | Shared files/artifacts |
| API task | ClamAV sidecar | 3310/TCP on task loopback | Malware scan |
| API/dashboard worker | SMTP provider | 587/TCP STARTTLS | Transactional email |
| ECS execution role/tasks | ECR, Logs, Secrets Manager, KMS, required AWS APIs | HTTPS/443 via NAT or VPC endpoints | Images, logs, secret injection |
| API/workers | Approved customer connector endpoints | Connector-specific, policy-controlled | Data connections; private destinations remain disabled by default |

Do not expose PostgreSQL, Redis, EFS, worker, scheduler, migration, metrics, or container administration endpoints publicly. `/metrics` requires a bearer token and approved private/admin access.

## PostgreSQL and migration contract

- RDS PostgreSQL 17.10 is the current target; application support requires PostgreSQL reached through `postgresql+asyncpg://`.
- Create a new, empty `vip` database for production. Never copy QA/UAT databases, test users, or test data into production.
- Place RDS in private data subnets, force SSL, set `ssl=require` in `DATABASE_URL`, enable KMS encryption, Multi-AZ for production, Performance Insights, enhanced monitoring, deletion protection, and storage auto-growth.
- Current per-process IaC pool is 5 plus 5 overflow. Budget total possible connections across every API/worker/scheduler/migration task before scaling. Add RDS Proxy or resize only through an infrastructure review.
- Production RDS PITR retention is 35 days in current IaC; take a pre-deploy checkpoint and use AWS Backup.

Authoritative migration order:

```text
confirm clean target / capture backup checkpoint
-> run exactly one migration task in private application subnets
-> alembic upgrade head
-> alembic current
-> require 20260808_0025
-> python -m vip_api.cli seed-governance
-> python -m vip_api.cli seed-connection-types
-> require task exit 0
-> deploy application services/traffic
```

All ECS services must set `SKIP_PLATFORM_BOOTSTRAP=true`; otherwise the API image entrypoint runs migrations. Never let every API replica migrate independently. Baseline governance definitions and connection types are deterministic system initialization, not customer/demo content.

## Redis contract and recovery

Redis is used for job ready/delayed queues, queue wakeups, event/SSE streams, authorization/feature/entitlement/quota caches when enabled, rate limits, and one-time signed-download token consumption. Durable jobs, leases, schedules, audit records, and business data remain in PostgreSQL.

Use private ElastiCache Redis 7.1 with `rediss://`, AUTH, encryption at rest/in transit, Multi-AZ production replication, snapshots, and `noeviction`. Redis loss can remove ephemeral streams/caches and delay work; restore or replace Redis, redeploy all consumers, then reconcile PostgreSQL-backed queued jobs. Never treat Redis as the system of record.

## Durable file and artifact storage

The frozen V1 has filesystem providers; it has no certified S3 application adapter. Mount one encrypted shared EFS access point at `/data` for every consumer that needs it:

| Content | Application path | Consumers |
| --- | --- | --- |
| CSV/XLSX and other supported uploads | `/data/vip-files` | API, dashboard worker |
| Pipeline output/artifacts | `/data/vip-pipeline-artifacts` | API, pipeline worker |
| PDF/PNG/dashboard export artifacts | `/data/vip-artifacts` | API, dashboard worker |
| File-provider email outbox | `/data/vip-email-outbox` | Non-production only; production uses SMTP |

Container-local storage would lose data on replacement and cannot be shared across replicas. EFS must be durable, encrypted, private, IAM/access-point restricted, mounted with consistent UID/GID, monitored for capacity/latency, and backed up. S3 remains suitable for ALB logs and recovery copies, not as a substitute for the frozen application filesystem paths.

## Workers and scheduler

- Scale dashboard/export and pipeline workers independently using queue age/depth, processing duration, CPU, memory, failure, retry, and stale-lease metrics.
- Workers publish database heartbeats. Container health uses `/app/scripts/worker-health.py`; a heartbeat older than three configured heartbeat periods is stale.
- Retries and leases are application-managed. Do not manually clear job/lease rows. Use supported UI/API retry/cancel operations.
- Run **one logical scheduler**. Its command is the generic worker with `JOB_WORKER_QUEUES=scheduler`, `JOB_WORKER_CONCURRENCY=1`, `DASHBOARD_DELIVERY_SCHEDULER_ENABLED=true`, and `PIPELINE_SCHEDULER_ENABLED=true`.
- Set both scheduler flags false on API, dashboard workers, and pipeline workers. Configure ECS desired count 1 with minimum healthy 0 and maximum 100 so deployment is stop-before-start. Database row locking is defense in depth, not authorization to scale the scheduler.

## Email

Application requirement: in production `DASHBOARD_EMAIL_PROVIDER` must be `smtp`; a sender address, SMTP host, and coherent TLS mode are required. Username and password are either both set or both absent. Current IaC uses STARTTLS on port 587 and injects credentials from Secrets Manager.

Provider decision: the provider and region remain infrastructure decisions. Current AWS IaC proposes SES SMTP in `eu-central-1` because Bahrain/UAE do not provide the needed SES SMTP sending endpoint. Before use, approve cross-region email content, move SES out of sandbox, verify the sender domain, DKIM, MAIL FROM/SPF and DMARC, confirm bounce/complaint/delivery notifications, confirm quotas, and complete a live delivery test. Another approved transactional SMTP provider may be used without source change if it satisfies the same interface.

## First Super Admin bootstrap

Run this only after migrations and baseline seeds, from an isolated one-off task using the production API image, production runtime secret, private networking, and no public listener:

```text
python -m vip_api.cli create-user --email <admin-email> --display-name <admin-name> --password-stdin
python -m vip_api.cli grant-platform-admin --email <admin-email>
```

Generate a unique bootstrap password in the approved password manager. The CLI reads one line from stdin; never put the password in argv, Terraform, workflow output, logs, ticket, or chat. Because non-interactive Fargate does not expose stdin, use an approved short-lived bootstrap secret and a reviewed wrapper that pipes the secret directly without echoing it. Delete/disable that bootstrap secret immediately after success. The admin must log in, change the password immediately, then revoke all other sessions. There is no hardcoded/default password.

The platform-admin flag gates the cross-tenant console. The Super Admin can create/activate/suspend organizations and workspaces; create/activate/suspend/manage users; assign/remove organization and workspace memberships/roles; inspect access summaries; reset passwords; revoke sessions; and perform platform administration. Actions are audited.

## Production seed rules

The migration task may run only the deterministic `seed-governance` and `seed-connection-types` commands. Do not run demo seed commands in production.

Production must not contain Dataiku QA, Floweus QA, Joalpha QA, test datasets, QA users, known test passwords, Playwright fixtures, local demo warehouses, or browser-test personas. `seed-multitenancy-demo`, `configure-governance-demo`, `seed-dataset-catalogs`, `seed-semantic-layer`, and `seed-dashboard-demo` are non-production fixtures and/or guarded as such. Staging may recreate explicitly approved synthetic fixtures with unique secrets; production begins clean except for deterministic system definitions and the one-time Super Admin.

## Health, readiness, and version

| Service | Health method | Expected |
| --- | --- | --- |
| Web | `GET /healthz` on port 8080/public HTTPS | HTTP 200 body `ok` |
| API liveness | `GET /health` | HTTP 200, `status=healthy`; does not touch dependencies |
| API readiness | `GET /ready` | HTTP 200, `status=ready`, database and Redis `healthy` |
| API version | `GET /api/v1/version` | `environment` is target and `commit_sha` equals the full frozen SHA |
| Dashboard worker | `python /app/scripts/worker-health.py` | Exit 0 with fresh DB heartbeat |
| Pipeline worker | `python /app/scripts/worker-health.py` | Exit 0 with fresh DB heartbeat |
| Scheduler | `python /app/scripts/worker-health.py` | Exit 0 with fresh scheduler worker heartbeat |
| Migration | ECS one-off task | Exit 0 and log/current output contains `20260808_0025` |
| PostgreSQL | Managed RDS state plus private SQL probe | Available; TLS query succeeds |
| Redis | Managed replication-group state plus private `PING` | Available; TLS/auth `PONG` |
| File storage | Mount and application upload/export smoke | EFS mount available and artifacts survive task replacement |
| Email | Tagged test delivery plus provider event | Accepted/delivered; bounce/complaint path visible |

Deployment acceptance must prove API runtime revision `4e97591845a93037d6e54b0237bcb3208d1b2696`. Also retain API/web ECR digest mappings and OCI revision labels in the deployment manifest. An ambiguous revision is a failed deployment.

## Logging

Send stdout/stderr to separate encrypted, retained log groups for web, API, dashboard worker, pipeline worker, scheduler, migration, and ClamAV. Web access logs are JSON. Application logs include timestamp, level, service/environment, request/correlation ID, and safe tenant/workspace context. Migration logs must record command phase, Alembic head, and exit status. Worker/scheduler logs must make start, heartbeat, claim, retry, failure, and clean shutdown observable. ALB/WAF/RDS/Redis/CloudTrail logs follow account standards.

Never log passwords, password hashes, connector secrets, database/Redis/SMTP URLs or credentials, bearer/session/CSRF/download tokens, cookies, authorization headers, bootstrap secret content, raw customer file contents, or decrypted configuration. Validate redaction and restrict log access/retention.

## Monitoring and alerting minimum

Before acceptance, monitor and alert on:

- external web/API availability, ALB unhealthy targets, 5xx rate, request count, and API p95 latency;
- ECS desired/running tasks, restart loops, CPU and memory for every service;
- RDS availability/Multi-AZ, CPU, memory, connections, locks/slow queries, free storage, backup age, and pending maintenance;
- Redis availability/failover, memory, CPU, connections, replication lag, snapshot age, and any eviction;
- dashboard/pipeline queue depth and oldest age, active/stale worker heartbeats, stale leases, retries, dead letters, failures, and duration;
- singleton scheduler running count and late scheduled jobs;
- dashboard export/delivery/PDF/PNG failures and pipeline failures;
- EFS availability, storage/throughput/latency, backup success, and mount errors;
- SMTP delivery, bounces, complaints, quotas, and sender/domain health;
- WAF block spikes, certificate expiry, secret rotation failures, backup/restore job failures.

The protected `/metrics` endpoint exposes aggregate application metrics and requires `METRICS_BEARER_TOKEN`. It must not be publicly reachable without an approved control.

## Backup and restore acceptance

Required protection is RDS automated backup/PITR, encrypted AWS Backup for RDS and EFS, cross-region copies where approved, and a documented recovery ownership/escalation chain. Current targets are RPO 15 minutes for PostgreSQL, 24 hours for file artifacts, and RTO 4 hours for DB/bad-release recovery (8–24 hours for regional recovery). These are objectives until measured.

Production is not accepted until an actual managed staging restore drill has:

1. restored an RDS recovery point into a new private instance;
2. restored EFS to a new filesystem/access point;
3. started isolated tasks against the restored copies;
4. verified Alembic `20260808_0025`, non-sensitive entity counts, representative file/artifact consistency, and smoke workflows;
5. recorded recovery point, timestamps, achieved RPO/RTO, operators, results, cleanup, and issues.

The historical local restore file is not this proof.

## Security release checklist

- TLS 1.2+, HTTPS redirect, valid ACM certificate, HSTS rollout, secure/HttpOnly session cookies.
- WAF managed rules plus rate limits for login, reset, upload, and general traffic; Shield Standard.
- Private RDS, Redis, EFS, ECS tasks, workers, scheduler, migration, and metrics access.
- Secrets Manager/KMS or equivalent; no secrets in Git, images, build args, frontend, Terraform variables/state outputs, logs, or tickets.
- Exact CORS/CSRF/trusted-host values and coherent SameSite/cookie domain.
- Web/API security headers and CSP retained.
- API and web final runtime image scans: Critical 0, High 0 or formally accepted risk.
- Repository secret scan, Python/npm dependency scan, IaC scan, Terraform validate/test, and least-privilege review pass.
- Image signing/provenance and ECR tag immutability where account controls support them.

## Non-blocking V1.1 backlog — do not delay infrastructure

- Dataset Certified-only filter is page-local.
- Catalog page/search is not URL-backed.
- Back from dataset detail returns to page 1.
- One dashboard filter per dimension.
- Incomplete widget draft is not persistent until configured.
- Timezone per-option offsets removed.
- Build-stage Node warnings are absent from the final runtime image.

These items are **NON-BLOCKING** and must **NOT DELAY INFRASTRUCTURE**. Do not fix them in the frozen V1 deployment.

## APPLICATION FREEZE POLICY

1. Do not modify application source during infrastructure implementation.
2. Configuration-only deployment work keeps the application SHA unchanged. Infrastructure and operations commits remain separate.
3. If an actual application P0/P1 is discovered: stop deployment; create a dedicated fix; create a new application SHA; rerun the relevant full certification; and update every release pin and handoff document.
4. Do not deploy a branch, `latest`, a mutable tag, a locally modified tree, or an image whose digest/revision provenance is unknown.
5. Do not change database schema outside the certified Alembic chain, commands/entrypoints, API/frontend behavior, dependency locks, Dockerfiles, storage provider, cookie/CORS contract, scheduler topology, or baseline seeds as an infrastructure workaround.

## Infrastructure team first action

Create a clean infrastructure branch/commit separate from the frozen application, set up encrypted/locked Terraform remote state and approved staging AWS/GitHub environment values, then run the full validation pipeline and produce a reviewed **staging** Terraform plan pinned to `4e97591845a93037d6e54b0237bcb3208d1b2696`. Do not apply production and do not alter application files.
