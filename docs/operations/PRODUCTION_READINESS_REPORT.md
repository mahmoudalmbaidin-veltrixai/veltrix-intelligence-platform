# VIP Production Infrastructure Architecture & Deployment Readiness

> Historical pre-freeze audit evidence only. It is not deployment authority. Use `VIP_V1_INFRASTRUCTURE_HANDOFF.md` for the frozen V1 release.

Report date: 2026-08-16  
Target: first paying VIP V1 customers  
Target data-plane region: AWS Middle East (Bahrain), `me-south-1`

## A. Infrastructure Verdict

**B — INFRASTRUCTURE IMPLEMENTED, BLOCKERS REMAIN**

The production architecture, Terraform, packaging, CI/CD, security controls, monitoring, backup policy, and operating procedures are implemented and locally/static validated. Nothing has been deployed to AWS. Open High dependency findings, missing account-level deployment evidence, managed restore/staging smoke evidence, and governance approvals prevent production use.

## B. Executive Summary

```text
Application status: A — APPLICATION READY FOR PRODUCTION INFRASTRUCTURE at the certified SHA, but new dependency advisories now require a recertified dependency update.
Infrastructure status: Implemented in code; Terraform and local runtime validation PASS; AWS deployment/testing NOT EXECUTED.
Can onboard paying customer now: NO
```

Kubernetes remains intentionally rejected. ECS/Fargate is the smaller, production-credible operating model for five processes with no Kubernetes-specific dependency. The implementation uses two Availability Zones in Bahrain; AWS documents three AZs in the region. RDS PostgreSQL 17.10 is an available supported minor version. SES is the only concrete regional incompatibility found: Bahrain and UAE do not expose SES SMTP sending endpoints, so the code uses Frankfurt (`eu-central-1`) and explicitly gates cross-region email processing approval. Sources: [AWS Regions and Availability Zones](https://docs.aws.amazon.com/global-infrastructure/latest/regions/aws-availability-zones.html), [RDS PostgreSQL versions](https://docs.aws.amazon.com/AmazonRDS/latest/PostgreSQLReleaseNotes/postgresql-versions.html), [ECS regional endpoints](https://docs.aws.amazon.com/general/latest/gr/ecs-service.html), [SES endpoints](https://docs.aws.amazon.com/general/latest/gr/ses.html), and [AWS Backup feature availability](https://docs.aws.amazon.com/aws-backup/latest/devguide/backup-feature-availability.html).

## C. Revision Traceability

```text
Certified application SHA: 869e7c092bd887c636cad4a35ec1fb622de8f181
Infrastructure HEAD: UNCOMMITTED WORKTREE based on 869e7c092bd887c636cad4a35ec1fb622de8f181
Alembic HEAD: 20260808_0024
Application source unchanged: YES
Branch: feat/post-core-p1-p2-connectors-scheduling-versions
```

The infrastructure work has not been committed, so no separate infrastructure SHA exists. The application-tree diff against the certified SHA is empty. Updating `cryptography`, `nanoid`, or `js-yaml` is now mandatory before release and would change the certified dependency set; the application SHA must therefore be invalidated and recertified for that remediation.

### Repository and change audit

```text
Current HEAD: 869e7c092bd887c636cad4a35ec1fb622de8f181
Current branch: feat/post-core-p1-p2-connectors-scheduling-versions
Tracked diff: 3 modified files, 34 insertions, 4 deletions before untracked files
Product-source diff from certified SHA: empty
```

`git status --short` at final hygiene:

```text
 M .github/workflows/quality-gate.yml
 M .gitignore
 M apps/api/.dockerignore
?? .dockerignore
?? .github/workflows/deploy-certified-release.yml
?? docs/operations/
?? infra/aws/
?? infra/containers/
```

`git diff --name-status` contains the three modified files shown above. The complete untracked-file set is classified in the table below. `git diff --check` passed.

| File(s) | Category | Application behavior changed? | Keep? |
| --- | --- | --- | --- |
| `.github/workflows/quality-gate.yml` | CI/CD | No; adds blocking repository/IaC validation | YES |
| `.github/workflows/deploy-certified-release.yml` | CI/CD | No; packages/promotes the certified trees | YES |
| `.gitignore` | Infrastructure | No | YES |
| `.dockerignore` | Container packaging | No | YES |
| `apps/api/.dockerignore` | Container packaging | No application behavior; narrows build context | YES |
| `infra/containers/web/Dockerfile` | Container packaging | No source behavior; production build/runtime | YES |
| `infra/containers/web/nginx.conf.template` | Container packaging | No application-source behavior; edge runtime policy | YES |
| `infra/aws/.terraform.lock.hcl`, `versions.tf`, `variables.tf`, `locals.tf`, `outputs.tf` | Infrastructure | No | YES |
| `infra/aws/network.tf`, `security.tf`, `load_balancer.tf`, `waf.tf` | Infrastructure | No | YES |
| `infra/aws/database.tf`, `redis.tf`, `storage.tf`, `backup.tf` | Infrastructure | No | YES |
| `infra/aws/registry.tf`, `secrets.tf`, `email.tf`, `ecs.tf`, `monitoring.tf` | Infrastructure | No | YES |
| `infra/aws/backend.hcl.example`, `terraform.tfvars.example` | Infrastructure | No; placeholders only | YES |
| `infra/aws/tests/production_plan.tftest.hcl` | Infrastructure | No; credential-free mocked plan assertions | YES |
| `infra/aws/scripts/deploy.sh`, `rollback.sh`, `smoke.sh` | CI/CD | No; release orchestration only | YES |
| `docs/operations/PRODUCTION_ARCHITECTURE.md` | Documentation | No | YES |
| `docs/operations/PRODUCTION_RUNBOOK.md` | Operations | No | YES |
| `docs/operations/DEPLOYMENT_CHECKLIST.md` | Operations | No | YES |
| `docs/operations/LOCAL_RESTORE_DRILL.md` | Operations | No | YES |
| `docs/operations/PRODUCTION_READINESS_REPORT.md` | Documentation | No | YES |
| Application product trees | Application source | **No changes present** | Preserve certified content |

Recommended commits after review and after the release-blocking dependency decision: `feat(infra): add AWS production foundation`, `ci(deploy): add certified release pipeline`, and `docs(ops): add production operations evidence`. Do not amend or rewrite the certified application commit.

## D. Final Architecture

```text
Customer
  -> Route 53 (global DNS)
  -> ACM certificate + AWS WAF
  -> public ALB in two AZs; HTTP redirects to HTTPS/TLS 1.2+
     -> Web ECS/Fargate service, private subnets, 2 tasks
     -> API ECS/Fargate service + ClamAV sidecar, private subnets, 2 tasks
        -> RDS PostgreSQL 17.10 Multi-AZ, private data subnets, TLS/KMS/PITR
        -> ElastiCache Redis 7.1, private data subnets, TLS/AUTH/KMS/Multi-AZ
        -> encrypted EFS access point for certified filesystem providers
     -> Dashboard/export worker ECS service
     -> Pipeline worker ECS service
     -> Singleton scheduler ECS service, desired_count = 1
     -> One-off migration task used only by deployment

Secrets Manager/KMS -> ECS secret injection
ECR -> immutable API/web images by digest
CloudWatch/SNS/Route 53 checks -> logs, metrics, alarms, uptime
AWS Backup -> RDS + EFS -> Bahrain vault -> UAE cross-region vault
SES Frankfurt -> TLS SMTP + DKIM/SPF/DMARC + encrypted bounce/complaint/delivery SNS
S3 -> ALB logs and encrypted recovery artifacts
```

Route 53 is global. The remaining services and selected capabilities are available in Bahrain based on their official regional endpoints/product documentation. WAF is regional and attached to the ALB; ACM is created in Bahrain. SES is deliberately cross-region. ALB access logs use SSE-S3 because AWS documents SSE-S3 as the supported access-log bucket encryption mode: [ALB access logging](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/enable-access-logging.html).

EFS is the V1 compatibility store because the certified application registers filesystem providers, not S3 providers. It uses a KMS-encrypted filesystem, private mount targets, security-group-only NFS, an access point rooted at `/vip`, enforced UID 100/GID 101, TLS mounts, tenant-scoped application keys, lifecycle management, and AWS Backup. Native S3 artifacts remain a recertified V1.1 improvement.

## E. Infrastructure Matrix

| Component | Implemented | Validated | AWS-deployed | Production-ready |
| --- | --- | --- | --- | --- |
| DNS | YES | PASS — Terraform | NOT EXECUTED | FAIL — live DNS absent |
| TLS | YES | PASS — policy/code | NOT EXECUTED | FAIL — certificate not issued/tested |
| WAF | YES | PASS — IaC scan | NOT EXECUTED | FAIL — rules not traffic-tested |
| ALB | YES | PASS — Terraform/mock plan | NOT EXECUTED | FAIL — listener/targets untested |
| ECS | YES | PASS — Terraform + local images | NOT EXECUTED | FAIL — no AWS service evidence |
| RDS | YES | PASS — Terraform assertions | NOT EXECUTED | FAIL — no RDS/PITR evidence |
| Redis | YES | PASS — Terraform assertions | NOT EXECUTED | FAIL — no failover evidence |
| Workers | YES | PASS — local restart/heartbeat | NOT EXECUTED | FAIL — no staging job-flow evidence |
| Scheduler | YES | PASS — singleton assertion/local restart | NOT EXECUTED | FAIL — no staging duplicate-fire test |
| EFS | YES | PASS — Terraform/IaC scan | NOT EXECUTED | FAIL — no mount/restore evidence |
| SES | YES | PASS — Terraform only | NOT EXECUTED | FAIL — production access/send/subscriptions untested |
| Secrets | YES | PASS — code/IAM/output audit | NOT EXECUTED | FAIL — values and rotation unconfigured |
| Backup | YES | PASS — Terraform only | NOT EXECUTED | FAIL — managed restore not run |
| Monitoring | YES | PASS — Terraform only | NOT EXECUTED | FAIL — alarms/subscriptions untested |
| CI | YES | PASS — YAML/static; dependency gate FAIL | NOT APPLICABLE | FAIL — open High findings |
| CD | YES | PASS — static/script validation | NOT EXECUTED | FAIL — OIDC/environments/rollout untested |

## F. Validation Results

```text
Terraform fmt: PASS
Terraform init: PASS — backend disabled; AWS 6.60.0 and random 3.9.0 pinned
Terraform validate: PASS
Terraform plan: NOT EXECUTED against AWS — no AWS CLI or credentials
Terraform mocked plan: PASS — terraform test, 1 passed/0 failed
TFLint: PASS
IaC security scan: PASS — Trivy 0.66.0, 0 High/Critical misconfigurations
Secret scan: PASS — Gitleaks scanned 134 commits/12.72 MB; no leaks; uncommitted credential-pattern scan clean
Container build: PASS — API, web, and worker-compatible API image
Container scan: FAIL — web PASS; API has 2 unique High cryptography CVEs
Frontend dependency scan: FAIL — 2 High npm advisories
CI validation: FAIL — YAML/static syntax PASS, but mandatory dependency gates fail; GitHub execution NOT EXECUTED
CD validation: PASS — YAML, Bash syntax, ShellCheck, migration/order/rollback review; AWS execution NOT EXECUTED
Backup restore drill: PASS — local PostgreSQL; AWS managed restore NOT EXECUTED
Smoke test: PASS — local health/readiness/version/login/session subset; AWS staging/full flows NOT EXECUTED
Failure tests: PASS — local API, dashboard worker, pipeline worker, scheduler, Redis, and PostgreSQL restart recovery
Rollback execution: NOT EXECUTED against ECS; argument guard/static logic PASS
```

The actual AWS plan is not claimed as validated: the host has no AWS CLI, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`, and `AWS_PROFILE` were unset. The mocked Terraform plan asserted private RDS, encryption, 35-day PITR, Redis `noeviction`, private ECS tasks, singleton scheduler, encrypted EFS, immutable ECR, and TLS 1.2+.

Container evidence: API build PASS, user `vip`, approximately 73.3 MB, certified OCI revision label; web build PASS, user `nginx`, approximately 35.1 MB, certified revision label. The web runtime has 0 High/Critical findings after Alpine security updates. It passed SPA fallback, gzip, CSP/security headers, no-store HTML, non-root health, and absence of `.env`, source maps, TypeScript/Vue sources, Git, tests, and runtime `node_modules`. The API reports the certified SHA and became ready against both the primary local QA DB and a freshly restored DB.

## G. Security Matrix

| Control | Result | Evidence |
| --- | --- | --- |
| TLS | PASS — code | ALB TLS 1.2/1.3 policy; HTTPS redirect; RDS forced SSL; Redis/EFS/SMTP TLS |
| Private DB | PASS — Terraform | Data subnets, `publicly_accessible=false`, SG ingress only from ECS |
| Private Redis | PASS — Terraform | Data subnets, no public address, SG ingress only from ECS |
| Secrets Manager | PASS — code | Runtime and SMTP secrets injected through ECS `secrets`; task execution role read scoped |
| Encryption at rest | PASS — Terraform | CMKs for RDS, Redis, EFS, Secrets, logs, backup, S3, SES event SNS |
| Encryption in transit | PASS — code | ALB HTTPS, RDS `ssl=require`/forced SSL, Redis `rediss`, EFS TLS, SMTP STARTTLS |
| WAF | PASS — code | Common, known-bad-input, IP reputation, login/reset/upload/general rate rules |
| Rate limiting | PASS — code | WAF volumetric rules plus application Redis/account-aware controls |
| Secure cookies | PASS — local/config | Production validator requires Secure; HttpOnly access/refresh and readable CSRF cookie smoke-tested |
| CORS/trusted hosts | PASS — local/config | Exact app origin/API host; production rejects wildcards |
| Secret scan | PASS | Gitleaks history plus uncommitted infrastructure credential-pattern scan |
| Vulnerability scan | **FAIL** | API: CVE-2026-69247 and CVE-2026-69249; npm: `js-yaml` and `nanoid` High advisories |

IAM has no `AdministratorAccess` and no task/deployment policy with unconstrained `Action="*"`. API/workers receive storage write plus runtime secrets; web/scheduler/migration use the minimal task role; migration connectivity is private; backup uses AWS service roles; execution-secret access is ARN-scoped. The CloudWatch Logs, alert-topic, and SES notification CMKs contain the standard key-policy `kms:*`/`Resource:"*"` account-root administration statement; because each is a resource policy attached to one key, the resource value means that key, not all account keys. Service cryptographic use is separately limited to required KMS data operations, named service principals, the current account, and—in the Logs policy—the expected encryption context.

Outbound connector traffic permits arbitrary destination ports because the certified connector catalog supports databases and third-party systems on customer-defined ports. It is isolated to API/worker security groups behind NAT, with VPC flow logs and application SSRF controls that block private/metadata targets by default. This is a documented P2 exposure, not an unnoticed wildcard.

Terraform state will contain generated secret material used to construct runtime URLs. The backend must be a separately provisioned KMS-encrypted, versioned, locked, access-logged S3 state store. No secret values are Terraform outputs; the runtime secret ARN is marked sensitive.

## H. Backup & Recovery

```text
PostgreSQL backups: RDS automated backups plus AWS Backup daily/monthly rules
PITR: 35 days in production
Backup retention: daily 35 days; monthly 365 days
Cross-region backup: Bahrain -> UAE (me-central-1), encrypted vault copies
EFS backup: selected by the same daily/monthly AWS Backup plan
Vault lock: production primary vault; 7–365 day bounds, 3-day changeable window
Restore drill: LOCAL RESTORE DRILL = PASS; AWS MANAGED RESTORE = NOT EXECUTED
RPO: <=15 minutes PostgreSQL; <=24 hours EFS artifacts; Redis best-effort/ephemeral acceleration
RTO: 4 hours database/bad-deploy recovery; 8 hours regional data-plane target
```

The local drill restored Alembic `20260808_0024`, 162 public tables, 100 users, 424 datasets, and 809 dashboards. The production image passed health/readiness/version against the restored database. The temporary API, database, and dump were removed. See `LOCAL_RESTORE_DRILL.md`.

## I. CI/CD

```text
CI gates: Trivy repository scan, Terraform fmt/init/validate, frontend type/lint/format/unit/build/audit, browser/a11y, backend static/unit/integration/Alembic/audit, container scan
Image tagging: certified SHA plus environment; no latest deployment tag
Image digest: ECR push resolved to immutable digest and deploy rejects non-digest input
Certified SHA enforcement: exact input and empty product-tree diff from certified commit
Migration runner: pre-production snapshot -> one Fargate task -> upgrade -> current/head check -> promotion
Staging deployment: required first; production promotion verifies staging health and exact certified SHA
Production approval: assumed GitHub protected `production` environment; account configuration NOT EXECUTED
Rollback: previous task definitions captured before rollout; all services restored on rollout/smoke failure; no Alembic downgrade
Deployment manifest: environment, SHA, image digests, migration task, snapshot, timestamp; 365-day artifact
```

Deployment concurrency is environment-scoped. The script aborts on migration failure, preserves digest references, rolls back partial ECS promotion, waits for all services to stabilize, and runs final smoke before writing a successful manifest. Database schema rollback remains intentionally manual/forward-fix; destructive automated Alembic downgrade is prohibited.

## J. Monitoring

```text
Central logging: PASS — encrypted retained groups for web, API, ClamAV, both workers, scheduler, migration; ALB and VPC logs
API alerts: PASS — ALB/API 5xx, p95 latency, unhealthy targets, CPU, memory, desired/running
RDS alerts: PASS — CPU, free storage, connections
Redis alerts: PASS — CPU, memory, connections, any eviction
Worker alerts: PASS — desired/running, CPU/memory, structured ERROR/CRITICAL log metrics
Scheduler alerts: PASS — singleton running count, CPU/memory, structured errors
Uptime: PASS — Route 53 HTTPS checks for app and API
Error tracking: FAIL — structured CloudWatch exceptions/correlation IDs exist, but dedicated aggregation and managed application-metric scraping are P2
AWS alarm delivery test: NOT EXECUTED
```

Logs use the certified key-based redaction layer for authorization/cookie/password/secret-like fields. Original SES headers are excluded from notifications. Value-based leakage sampling in the deployed account remains mandatory.

## K. Production Smoke Results

| Flow | Result |
| --- | --- |
| Health | PASS — local web/API liveness, readiness, revision |
| Login | PASS — local supplied QA credential; session bootstrap and cookie flags |
| Connection | NOT EXECUTED against staging |
| Dataset | NOT EXECUTED against staging |
| Pipeline | NOT EXECUTED against staging |
| Dashboard | NOT EXECUTED against staging |
| Publish | NOT EXECUTED against staging |
| Export | NOT EXECUTED against staging |
| Scheduler | PASS — local process health/restart; scheduled-once flow NOT EXECUTED |
| Notifications | NOT EXECUTED against staging |

The provided HTTPS smoke script was statically validated but not executed against AWS because no endpoint exists. Local equivalents verified web health/SPA/headers, API health/readiness, exact SHA, basic API access, login, HttpOnly/SameSite cookies, CSRF cookie, and authenticated `/auth/me`.

## L. Infrastructure Defects

```text
ID: VIP-INFRA-P1-001
Severity: P1
Area: API runtime dependency
Evidence: Trivy reports CVE-2026-69247 and CVE-2026-69249 in cryptography 48.0.1; fixed in 50.0.0 and 49.0.0 respectively.
Required remediation: update the certified runtime dependency/lock, rebuild, scan clean, run application regression and recertify a new SHA.
Release blocker: YES
```

```text
ID: VIP-INFRA-P1-002
Severity: P1
Area: Frontend build/dependency chain
Evidence: npm audit reports High GHSA-5p4m-2wfm-xmqj in js-yaml 4.3.0 and High GHSA-2v37-7h3g-55p8 in nanoid 3.3.16. The final web runtime scan is clean, but the trusted build gate fails.
Required remediation: update overrides/transitive dependencies and lockfile, rebuild, scan, run frontend/browser regression, and recertify a new SHA.
Release blocker: YES
```

```text
ID: VIP-INFRA-P1-003
Severity: P1
Area: AWS provisioning and configuration
Evidence: no AWS CLI/credentials; real plan/apply, DNS, certificates, OIDC roles, state backend, GitHub environments, secrets, SES production access, subscriptions, and alarms are absent/unverified.
Required remediation: provision approved staging with reviewed real Terraform plan, configure GitHub/OIDC/protected environments/state, confirm subscriptions and controls, then provision production through CD.
Release blocker: YES
```

```text
ID: VIP-INFRA-P1-004
Severity: P1
Area: Recovery and end-to-end validation
Evidence: local restore/restarts pass, but RDS PITR/AWS Backup/EFS restore, Multi-AZ failover, full authenticated staging flows, exact-once schedule behavior, and deployment/rollback execution are NOT EXECUTED.
Required remediation: run and approve the staging deployment, restore, resilience, smoke, schedule, export, and rollback evidence matrix.
Release blocker: YES
```

```text
ID: VIP-INFRA-P1-005
Severity: P1
Area: Data residency and transactional email
Evidence: Bahrain is not Saudi-resident; SES SMTP is cross-region in Frankfurt. No customer/legal approval or live send/bounce/complaint test exists.
Required remediation: obtain written data-location/email-content approval or select an approved hosting/mail provider; obtain SES production access, confirm SNS subscriptions, and test DKIM/SPF/DMARC/send/bounce/complaint.
Release blocker: YES
```

```text
ID: VIP-INFRA-P2-001
Severity: P2
Area: Observability
Evidence: protected application Prometheus metrics are not managed-scraped; no dedicated error aggregation service.
Required remediation: add approved private scraping/error aggregation after staging measurements.
Release blocker: NO
```

```text
ID: VIP-INFRA-P2-002
Severity: P2
Area: Connector egress
Evidence: arbitrary customer connector ports require broad NAT egress on API/worker connector security groups.
Required remediation: add customer destination allowlists/proxy controls in a recertified release where commercially practical; continue flow-log/SSRF monitoring.
Release blocker: NO
```

```text
ID: VIP-INFRA-P2-003
Severity: P2
Area: Storage/capacity
Evidence: EFS is a compatibility layer and no representative production load test has established sizing.
Required remediation: load-test in staging; evaluate a native S3 provider in V1.1 with application recertification.
Release blocker: NO
```

Open infrastructure P0: **0**. Open infrastructure P1: **5**. Required deployment state is P0=0 and P1=0, so release is blocked.

## M. Remaining Risks

### BLOCKING

- Recertified dependency update for the API and frontend High advisories.
- Reviewed real AWS Terraform plan and successful staging apply; no resource currently exists.
- AWS RDS/EFS managed restore, deployment, rollback, full smoke, schedule, worker, Redis/RDS failure evidence.
- Bahrain/GCC data-residency and Frankfurt email-processing approval for each applicable customer.
- SES production access, verified domain/DKIM/SPF/DMARC, confirmed SNS subscriptions, and live delivery/bounce/complaint tests.
- GitHub OIDC roles, protected staging/production environments, production reviewers, encrypted state backend, secrets, alert ownership, and on-call subscription confirmation.

### NON-BLOCKING

- EFS cost/throughput and future native S3 provider.
- Protected application metric scraping and dedicated error aggregation.
- Connector destination allowlisting beyond certified application SSRF controls.
- Load-test-derived task/database/cache sizing and later Savings Plans/reservations.

### Initial sizing and cost awareness

| Service | Minimum | Recommended first production | Scale trigger |
| --- | ---: | ---: | --- |
| API + ClamAV | 1 x 2 vCPU/4 GiB | 2 x 2 vCPU/4 GiB | CPU 60%, memory 75%, p95 2s, DB connections |
| Web | 1 x 0.25 vCPU/0.5 GiB | 2 x 0.25 vCPU/0.5 GiB | CPU/request rate/latency |
| RDS | Single-AZ `db.t4g.medium`, 50 GiB staging | Multi-AZ `db.t4g.medium`, 100 GiB gp3 | CPU 70%, storage forecast, connection pressure |
| Redis | 1 x `cache.t4g.small` staging | 2 x `cache.t4g.small` Multi-AZ | memory 75%, CPU 70%, any eviction |
| Pipeline worker | 1 vCPU/2 GiB | 1 x 2 vCPU/4 GiB | queue age, execution time, CPU/memory |
| Dashboard worker | 0.5 vCPU/1 GiB | 1 x 1 vCPU/2 GiB | queue age, export time, CPU/memory |
| Scheduler | 0.25 vCPU/0.5 GiB | 1 x 0.5 vCPU/1 GiB | never horizontal-scale; alert if running !=1 |
| EFS | Elastic | Elastic/general purpose | IO latency, throughput, storage growth/cost |

Approximate on-demand monthly architecture ranges, before tax/support and highly variable transfer/storage/email usage: **staging USD 450–850** with one NAT gateway and smaller/single data nodes; **initial production USD 950–1,650** with two-AZ Fargate, Multi-AZ RDS/Redis, and two NAT gateways. These are planning bands, not a quote. Major drivers are Fargate task-hours, RDS Multi-AZ, Redis nodes, NAT hourly/data processing, ALB/WAF, EFS, CloudWatch, backup copies, and data transfer. AWS bills Fargate by requested vCPU/memory duration and NAT by gateway-hours plus processed GB: [Fargate pricing](https://aws.amazon.com/fargate/pricing/), [VPC/NAT pricing](https://aws.amazon.com/vpc/pricing/), [RDS pricing](https://aws.amazon.com/rds/pricing/), [ElastiCache pricing](https://aws.amazon.com/elasticache/pricing/).

Low-risk savings already implemented: one NAT gateway in staging and two zonal NAT gateways in production; an S3 gateway endpoint avoids NAT processing for S3. After baseline measurements, use scheduled staging shutdown, ARM validation, Savings Plans/reservations, log-tiering, and right-sizing. Production HA/security controls are not removed for marginal savings.

### Exact steps remaining

1. Create a new application RC that upgrades the vulnerable Python/npm lock entries; run the complete certified regression and produce a new certified SHA.
2. Provision a restricted encrypted/locked Terraform state backend and deployment OIDC roles; configure protected GitHub `staging` and `production` environments and reviewers.
3. Supply reviewed staging variables/secrets, run a real `terraform plan`, complete security/architecture approval, and apply to a dedicated staging account.
4. Confirm DNS/TLS/WAF/ALB/ECS/RDS/Redis/EFS/backup/log/monitoring settings from AWS APIs and test alarm/SNS delivery.
5. Obtain customer/legal Bahrain and Frankfurt SES data-flow approval; obtain SES production access; confirm DKIM/SPF/DMARC and bounce/complaint/delivery SNS subscriptions.
6. Deploy the new certified SHA to staging through CD; run the full smoke checklist, failure tests, exact-once schedule test, migration and rollback test.
7. Restore RDS PITR/AWS Backup and EFS into isolated staging resources; validate schema/counts/artifacts; record measured RPO/RTO and cleanup.
8. Review all evidence, close P1 findings, approve production variables/plan/change window, then promote the exact staging-certified digests through the protected production environment.

## N. Go / No-Go

**NO-GO — PRODUCTION INFRASTRUCTURE REMEDIATION REQUIRED**

The codebase now contains a coherent production foundation and strong local evidence, but it is neither AWS-deployed nor free of release-blocking High vulnerabilities. No paying customer should be onboarded until every P1 above is closed and the deployment checklist is approved.
