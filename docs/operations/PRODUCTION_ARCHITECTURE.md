# VIP V1 Production Architecture

> Supporting architecture reference. The authoritative release invariants and deployment instructions are in `VIP_V1_INFRASTRUCTURE_HANDOFF.md`.

## Decision

VIP V1 should run on AWS in `me-south-1` (Bahrain) using ECS on Fargate, not Kubernetes. The application has five independently operated processes but does not require Kubernetes APIs, custom operators, daemon workloads, or multi-cluster scheduling. ECS provides immutable deployments, private networking, health-managed services, horizontal scaling, and task isolation with materially less operational load for the first customers.

The Bahrain region is a GCC location with three Availability Zones. It is not a Saudi data-residency location. Before onboarding, Legal/Security must record each customer's approved data location. If a contract or Saudi regulatory classification mandates in-Kingdom hosting, this stack is not an acceptable substitute; select a Saudi region/provider and rerun infrastructure validation.

## Topology

```text
Users
  -> Route 53 DNS
  -> ACM TLS 1.2/1.3 certificate
  -> AWS WAF + Shield Standard
  -> public Application Load Balancer (2 AZ)
       -> app.<domain> -> VIP web ECS/Fargate (2 private tasks)
       -> api.<domain> -> VIP API ECS/Fargate (2 private tasks + ClamAV sidecar)
                            -> RDS PostgreSQL 17.10 Multi-AZ (private data subnets)
                            -> ElastiCache Redis 7.1 Multi-AZ/TLS (private data subnets)
                            -> encrypted EFS access point (private data subnets)
                            -> transactional SMTP over TLS (SES in an approved SMTP-capable region)
       private ECS services:
         -> generic/dashboard worker (scalable)
         -> pipeline worker (scalable)
         -> scheduler (exact desired count 1)
         -> one-off migration task (CD only)

CloudWatch Logs/Metrics/Alarms <- ALB, WAF, ECS, API/workers, RDS, Redis
AWS Backup -> encrypted primary vault -> encrypted cross-region vault
S3 -> ALB logs and encrypted recovery artifacts/config exports
Secrets Manager + KMS -> runtime and SMTP secrets
ECR -> immutable API/web images and vulnerability scan results
```

## Why EFS rather than S3 for certified V1 application artifacts

The certified application implements a path-safe local provider for uploaded files and filesystem providers for pipeline/dashboard artifacts. No S3 adapter is registered. Changing that behavior would invalidate the certified application SHA. The production task definitions therefore mount one encrypted EFS access point at `/data`; the existing tenant-scoped object keys and atomic file operations remain unchanged, while the storage becomes multi-AZ, persistent across task replacement, private, encrypted, and covered by AWS Backup.

S3 is used for load-balancer logs, recovery exports, immutable versions, and lifecycle-managed off-instance copies. A native S3 artifact provider is a post-certification application change and requires a new release candidate. EFS is an intentional V1 compatibility decision, not container-local storage.

## Current infrastructure audit

| Component | Current state at certified SHA | Production ready? | Gap / production disposition |
| --- | --- | --- | --- |
| Backend Dockerfile | Pinned Python 3.12 Alpine digest, locked runtime requirements, non-root UID 100, entrypoint, no dev server outside development | Partial | Entrypoint ran migrations in every API replica; production sets `SKIP_PLATFORM_BOOTSTRAP=true` and uses one CD migration task. CI adds OCI labels and immutable ECR digest. |
| Frontend Dockerfile/runtime | No container; Vite dev/preview and Netlify static config only | No | Added multi-stage Node build and non-root Nginx runtime with SPA routing, health check, compression, CSP, and security headers. |
| Docker Compose | PostgreSQL, Redis, ClamAV, API, generic/dashboard worker, pipeline worker; local ports and named volumes | Development/UAT only | Retained for local use. It is not the production orchestrator. No frontend or standalone scheduler service. |
| Environment examples | Root and API examples contain local URLs and development defaults | No | Production values are explicit ECS environment entries; secret values come from Secrets Manager. Production validation already rejects key unsafe defaults. |
| FastAPI command | Uvicorn on port 8000; reload only when `APP_ENV=development` | Yes with production settings | Fargate runs the same certified command; ALB drains for 60 seconds. |
| Frontend build | `vue-tsc --noEmit` then Vite build; production/live configuration fails closed | Yes when built correctly | API URL is environment-specific and baked into an immutable web image. |
| PostgreSQL | PostgreSQL 17 local container, public host port, local volume | No | RDS PostgreSQL 17.10, private subnets, forced TLS, KMS encryption, Multi-AZ, auto-growth, PITR, enhanced monitoring. Production starts from a new empty database. |
| Migrations | Alembic entrypoint upgrade; HEAD `20260808_0025` | Partial | One Fargate migration task, CD concurrency, pre-deploy snapshot, head verification, fail-before-service-update. |
| Redis | Redis 8 local container, AOF, no auth/TLS, public host port | No | Private ElastiCache Redis 7.1, TLS, AUTH, KMS, Multi-AZ, snapshots, `noeviction`, alarms. |
| Generic/dashboard worker | Separate process, durable DB lease/retry/dead-letter, Redis queue acceleration, DB heartbeat | Partial | Dedicated ECS service; scheduler ticks disabled so workers can scale safely. |
| Pipeline worker | Separate process, DB `SKIP LOCKED` claim, leases, recovery, heartbeat | Partial | Dedicated ECS service with independent CPU/memory and EFS access. |
| Scheduler | Both schedulers run inside every generic worker; DB `FOR UPDATE SKIP LOCKED` prevents duplicate slot claims | Safe but not operationally isolated | Dedicated singleton ECS scheduler using queue `scheduler`; scheduling disabled everywhere else. Deployment permits stop-before-start, while DB locking remains defense in depth. |
| Uploaded files | Path-safe local provider, size/extension/MIME/signature/XLSX checks, ClamAV option, signed downloads | Partial | Encrypted EFS mounted at the same paths; ClamAV sidecar on API. Native object adapter remains a future recertification item. |
| Pipeline/dashboard artifacts | Local atomic filesystem providers and signed download tokens | No on ephemeral disk | Encrypted shared EFS plus lifecycle and backups. |
| SMTP | File outbox by default; real SMTP implementation exists and production requires it | Partial | ECS requires SMTP host and Secrets Manager username/password. SES domain, DKIM, MAIL FROM SPF, DMARC, and encrypted bounce/complaint/delivery notifications are IaC. SES has no SMTP sending endpoint in Bahrain/UAE, so the default is Frankfurt (`eu-central-1`). Cross-region email-content approval, production access, SNS subscription confirmation, and live delivery/event tests remain gates. |
| Health | `/health` is dependency-free liveness; `/ready` checks PostgreSQL and Redis concurrently with bounded timeouts | Yes | ECS uses `/health`; ALB uses `/ready`, preventing dependency failure from creating restart loops. Worker heartbeats back container health. |
| Logging | JSON logs with timestamp, level, service, environment, correlation/request and tenant context; key-based redaction | Yes | CloudWatch log groups are encrypted with retention; ALB/VPC logs are centralized. Exception text still requires operational review for value-based secret leakage. |
| Metrics | Prometheus endpoint with HTTP/dependency/queue/worker/export/pipeline metrics; bearer token required in production | Partial | Infrastructure metrics/alarms are implemented. Managed scraping of the protected application metrics endpoint is not yet deployed and is P2. |
| CI | Ruff, format, mypy, backend unit/integration, Alembic check, ESLint, Prettier, typecheck, frontend tests/build, browser tests, npm/pip audit, API image scan | Mostly | Added repository secret/dependency/IaC scan and Terraform format/validate. GitHub runs remain to be observed on the infrastructure commit. |
| CD | None | No | Added exact-certified-tree verification, immutable image build/scan/push, migration-first deployment, health wait, smoke, manifest, and environment concurrency. AWS/GitHub environment setup remains. |
| Reverse proxy/TLS/WAF | None in repository | No | ALB/ACM/WAF/Route 53 implemented in Terraform. |
| Secrets | Typed `SecretStr`; encrypted connector credentials use AES-256-GCM; local Compose has explicit dev-only fallbacks | Partial | KMS-backed Secrets Manager injection, encrypted state requirement, key versioning and rotation runbook. Never use Compose defaults in production. |
| Backup/restore | No deployed production backup configuration | No | RDS PITR and AWS Backup plans/vaults are IaC. The local PostgreSQL restore drill passed; a real managed staging RDS/EFS restore remains mandatory. |

## Environments

| Component | Development | Staging / UAT | Production |
| --- | --- | --- | --- |
| Domain | `localhost:3009`, `localhost:8000` | `app.staging.<domain>`, `api.staging.<domain>` | `app.<domain>`, `api.<domain>` |
| Compute | Docker Compose/native | Separate ECS cluster/services | Separate ECS cluster/services |
| Database | Local `vip` / isolated `vip_test` | New staging RDS | New empty production RDS; never copied from QA |
| Redis | Local DB 0/test DB 15 | Dedicated staging ElastiCache | Dedicated production Multi-AZ ElastiCache |
| Storage | Local named volumes | Dedicated staging EFS/S3 | Dedicated production EFS/S3 |
| Secrets | Uncommitted local `.env` | Staging Secrets Manager/KMS | Production Secrets Manager/KMS and separate access roles |
| SMTP | File provider | SES sandbox/test recipients or staging provider | SES/transactional provider with production access |
| Data | Developer/fixtures | Synthetic QA data only | Customer data and intentional baseline seed only |
| Deployment approval | None | Automated after CI | GitHub protected environment approval required |

No database, Redis endpoint, KMS key, secret, EFS access point, S3 bucket, SMTP credential, domain, user, or generated artifact is shared between staging and production.

## DNS, TLS, cookies, CORS, and redirects

- Route 53 `A` alias records map the app and API names to the ALB. The stack is IPv4; add dual-stack only after IPv6 security testing.
- ACM uses DNS validation and automated renewal. CloudWatch/EventBridge certificate-expiry alerting should be enabled in the account baseline.
- Port 80 performs a permanent redirect to HTTPS. Unknown Host values get 404. The API also enforces an explicit trusted host.
- ALB policy `ELBSecurityPolicy-TLS13-1-2-2021-06` permits TLS 1.2 and 1.3.
- API production settings use `Secure`, `HttpOnly` for session cookies, `SameSite=Lax`, and domain `.<root-domain>`. The CSRF token cookie remains intentionally readable for double-submit protection.
- CORS and CSRF trust only the exact HTTPS frontend origin. Credentialed wildcard origins are forbidden by application validation.
- HSTS is emitted by the API only in production. The web tier should add HSTS only after both hostnames and all intended subdomains are permanently HTTPS; the ALB/API already establish the production policy.

## Ingress limits and timeouts

| Endpoint class | WAF limit per source IP | Application limit | Reason |
| --- | ---: | ---: | --- |
| Login `/auth/login` | 100 / 5 min | 10 / min | WAF absorbs volumetric attacks; per-process-independent Redis limit and account lockout provide identity protection. |
| Password reset `/auth/password-reset/*` | 50 / 5 min | 5 / min per IP+identifier | Reduces enumeration and mail abuse. |
| File uploads `/api/v1/files` POST | 300 / 5 min | 30 / min per tenant/user; 100 MiB each | Supports enterprise batches while bounding abuse. |
| Semantic queries | General 3,000 / 5 min; add tenant plan limits after measurements | Query rows, bytes, complexity, and 30-second timeout bounded | IP-only limits can harm NATed enterprise offices; tenant-aware controls belong in the app. |
| Dashboard export/create | General 3,000 / 5 min | Async job limits, 3 attempts, 50 MiB artifact default | Exports are asynchronous; avoid short proxy timeouts. |
| SSE/event subscriptions | General limit | 30 / min | Heartbeats keep the 120-second ALB idle timer open. |
| Public viewer (if later enabled) | Add 600 / 5 min and bot control before launch | Not currently introduced | Must be reviewed as a new public attack surface. |

ALB idle timeout is 120 seconds. Long pipelines and exports are asynchronous and not tied to an HTTP request. Uploads must complete inside this timeout or use a newly certified direct-upload mechanism.

## Data services

### PostgreSQL

- Engine: RDS PostgreSQL 17.10, matching the local major version.
- Initial recommended class: `db.t4g.medium`, 100 GiB gp3, auto-growth to 500 GiB, Multi-AZ in production.
- Application pooling: 5 persistent + 5 overflow connections per task. Alert at 100 connections and introduce RDS Proxy or resize before API scale creates pressure.
- TLS is forced by the RDS parameter group and `ssl=require` is in the runtime URL. At-rest encryption uses a customer-managed rotating KMS key.
- Automated backups/PITR: 35 days production. Daily AWS Backup copy to a second region; monthly recovery points retained for one year.
- Maintenance: Friday 22:00-23:00 UTC; backup window 00:30-01:30 UTC. Coordinate customer-facing maintenance in Asia/Riyadh time.

### Redis

VIP uses Redis for queue wakeups/ready lists, event/SSE streams, rate limits, caches, and one-time download token consumption. Durable job truth, leases, and schedules live in PostgreSQL. Redis loss can delay/recreate queue acceleration and lose ephemeral event history, but must not lose the authoritative jobs.

- ElastiCache Redis 7.1, TLS (`rediss://`), AUTH, KMS at rest, private security group.
- Two nodes/Multi-AZ in production; daily snapshots retained 14 days.
- `noeviction` protects queue, event, and security keys from silent eviction. Alert at 75% memory and scale before saturation.

## Services and scaling

| Service | Minimum | Recommended initial production | Scale trigger / constraint |
| --- | --- | --- | --- |
| Web | 1 x 0.25 vCPU / 0.5 GiB | 2 tasks across AZs | CPU >60%, ALB request volume, or p95 latency. |
| API + ClamAV | 1 task, 2 vCPU / 4 GiB | 2 tasks | CPU >60%, memory >75%, p95 >2s; watch DB connections. |
| PostgreSQL | Single-AZ `db.t4g.medium`, 50 GiB staging | Multi-AZ `db.t4g.medium`, 100 GiB | CPU >70%, free memory pressure, connections >70%, storage forecast. Scale vertically first; replicas later for read-heavy workloads. |
| Redis | One `cache.t4g.small` staging node | Two-node `cache.t4g.small` replication group | Memory >75%, CPU >70%, any eviction. |
| Dashboard worker | 0.5 vCPU / 1 GiB | 1 vCPU / 2 GiB, one task | Queue age/depth, export duration, CPU/memory. Safe to replicate; DB leases prevent duplicate execution. |
| Pipeline worker | 1 vCPU / 2 GiB | 2 vCPU / 4 GiB, one task | Queued-run age, execution duration, CPU/memory. Safe to replicate; database `SKIP LOCKED` leases apply. |
| Scheduler | 0.25 vCPU / 0.5 GiB | 0.5 vCPU / 1 GiB, exactly one task | Do not scale horizontally. Database row locking is defense in depth. |
| EFS | Elastic | Elastic throughput | Throughput/IO latency and storage cost. Move to native S3 only in a new certified application release. |

Workload measurements are not available; these are safe starting assumptions for low tens of concurrent enterprise users and modest asynchronous workload, not capacity guarantees.

## Backup and recovery targets

- Recommended V1 RPO: 15 minutes for PostgreSQL; 24 hours for filesystem artifacts/config exports; Redis RPO is best-effort because PostgreSQL is authoritative.
- Recommended V1 RTO: 4 hours for database or bad-deployment recovery; 8 hours for regional data-plane recovery; 24 hours if a complete region rebuild is required.
- Database loss: restore PITR into a new RDS instance, inject a new secret version, run readiness and tenant-scoped smoke tests, then switch services.
- Region outage: apply the versioned Terraform stack in the approved DR region, restore the cross-region recovery point, promote immutable image digests copied to the DR registry, update DNS after approval.
- Redis loss: restore snapshot or create a fresh encrypted replication group, update secret, restart workers/API, reconcile durable queued jobs from PostgreSQL.
- Worker crash: ECS restarts; expired leases are recovered by workers.
- Object/filesystem issue: stop mutations, restore EFS recovery point to a new filesystem, mount via a new access point, validate keys/metadata, and redeploy.
- Bad deployment: ECS circuit breaker or explicit prior task-definition rollback. Never automatically run Alembic downgrade.

## Remaining architecture constraints

- AWS Bahrain is GCC-hosted, not Saudi-resident. Customer approval is mandatory.
- The native artifact provider is filesystem-only. EFS is production-durable but not object-native.
- Managed scraping/error aggregation for application metrics is not provisioned; CloudWatch infrastructure and structured-log alarms are present.
- Terraform state contains sensitive derived values required by Redis and runtime secret construction. The backend must be KMS-encrypted, versioned, locked, access-logged, and restricted to the deployment role and break-glass operators.
