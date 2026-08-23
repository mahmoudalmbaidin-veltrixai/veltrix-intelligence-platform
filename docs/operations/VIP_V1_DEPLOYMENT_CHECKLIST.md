# VIP V1 Deployment and Infrastructure Acceptance Checklist

Authoritative release: `4e97591845a93037d6e54b0237bcb3208d1b2696`  
Expected Alembic head: `20260808_0025`

Every checked item requires an owner, UTC timestamp, and evidence link/change record. Any failed P0/P1, ambiguous image revision, public data service, migration mismatch, missing backup, or failed smoke test is NO-GO.

## 1. Freeze and handoff intake

- [ ] Working copy is on branch `feat/post-core-p1-p2-connectors-scheduling-versions` for reference and `git rev-parse HEAD` is exactly `4e97591845a93037d6e54b0237bcb3208d1b2696` before application builds.
- [ ] Application source diff from the frozen SHA is empty.
- [ ] Infrastructure work is isolated in a separate branch/commit/review; no application file is staged or committed.
- [ ] No deployment uses a branch, `latest`, mutable tag, locally modified tree, or unverified artifact.
- [ ] This six-file `VIP_V1_*` handoff set is attached to the change.
- [ ] Customer/legal/security approval covers the selected AWS region and data residency.

## 2. CI quality and security gates

Run the current certified commands from the frozen tree (or require the equivalent protected CI jobs):

```bash
# Backend, from apps/api after locked dependencies are installed
python -m ruff check .
python -m ruff format --check .
python -m mypy src tests
python -m pytest -m "not integration"
RUN_INTEGRATION_TESTS=1 python scripts/backend_quality.py
python -m alembic check

# Frontend, from repository root
npm ci
npm run lint
npm run format:check
npm run typecheck
npm run test
npm run build

# Certified desktop browser projects against a live API
npm run test:e2e -- --project=chrome-desktop --project=firefox-desktop --project=webkit-desktop
```

- [ ] Ruff passes.
- [ ] Ruff format check passes.
- [ ] mypy passes.
- [ ] Backend unit tests pass.
- [ ] Backend integration tests pass against isolated PostgreSQL/Redis.
- [ ] Alembic check passes; migration graph has one head, `20260808_0025`.
- [ ] ESLint passes.
- [ ] Prettier check passes.
- [ ] TypeScript typecheck passes.
- [ ] Frontend tests pass.
- [ ] Frontend production build passes with live API mode.
- [ ] Chromium, Firefox, and WebKit core E2E pass.
- [ ] Python and npm production dependency audits pass policy.
- [ ] Repository secret scan reports no committed production secrets.
- [ ] Terraform format/validate/test and IaC security scan pass.
- [ ] Final API and web runtime image scans report Critical 0 / High 0, or a formally approved exception is attached.

## 3. Infrastructure configuration prerequisites

- [ ] Separate staging AWS account/environment or equivalent isolation is selected.
- [ ] Encrypted, versioned, locked, access-logged Terraform backend exists; state access is limited to deployment/break-glass roles.
- [ ] GitHub OIDC deployment role and protected `staging` environment are configured.
- [ ] Required workflow variables exist: `AWS_DEPLOY_ROLE_ARN`, `APP_HOSTNAME`, `API_HOSTNAME`, `API_ECR_REPOSITORY`, `WEB_ECR_REPOSITORY`, `ECS_CLUSTER`, `PRIVATE_SUBNET_IDS`, `ECS_SECURITY_GROUP_ID`, `RDS_IDENTIFIER`.
- [ ] Root domain/hosted zone, web/API hostnames, alert mailbox, approved region/DR region, SMTP provider/region, and sender domain are decided.
- [ ] `infra/aws/terraform.tfvars.example` has been copied to an uncommitted environment-specific file and all placeholders replaced.
- [ ] Terraform `release_sha` is exactly the frozen full SHA and output `alembic_head` is `20260808_0025`.
- [ ] A peer-reviewed staging Terraform plan has no unexpected public routes, destructive stateful changes, or plaintext secrets.

## 4. Exact staging deployment order

1. [ ] Create/validate VPC, public ALB subnets, private application/data subnets, routes/NAT or approved VPC endpoints, security groups, VPC flow logging, IAM/KMS, and encrypted remote state.
2. [ ] Create Secrets Manager objects and access policy. Populate SMTP credentials through an out-of-band approved channel; verify no secret appears in plan/logs.
3. [ ] Create ECR repositories with immutability/scanning controls.
4. [ ] Create private RDS PostgreSQL 17.10 with forced TLS, backups/PITR, monitoring, encryption, and a new empty `vip` database.
5. [ ] Create private TLS/AUTH ElastiCache Redis 7.1 with `noeviction`, encryption, snapshots, and alarms.
6. [ ] Create encrypted EFS/access point/mount targets and backup selection; verify only ECS can mount it at `/data`.
7. [ ] Configure/verify SMTP sender domain, DKIM, MAIL FROM/SPF, DMARC, production/sandbox mode, credentials, events, and quotas.
8. [ ] Build API/web from the exact frozen tree, apply OCI revision labels, scan both final images, push, resolve ECR digests, and write the digest mapping to the change record.
9. [ ] Materialize ECS task definitions using only digest image references and the approved environment/secrets inventory. Set `SKIP_PLATFORM_BOOTSTRAP=true` everywhere.
10. [ ] Take/record the pre-migration checkpoint (or clean-DB baseline checkpoint), then run exactly one private migration task.
11. [ ] Require migration exit 0 and `alembic current` = `20260808_0025`; require only deterministic `seed-governance` and `seed-connection-types`.
12. [ ] Deploy dashboard/export worker and pipeline worker; require fresh heartbeats.
13. [ ] Deploy scheduler at desired count 1, concurrency 1, queue `scheduler`; verify all other services have both scheduler flags false.
14. [ ] Deploy API tasks; require container liveness and ALB `/ready` health.
15. [ ] Deploy web tasks; require `/healthz`.
16. [ ] Enable/validate ALB host routing, WAF, ACM/TLS, HTTP redirect, DNS, cookies, CORS, CSRF, trusted hosts, and security headers.
17. [ ] Enable/validate CloudWatch/Route 53/SNS monitoring, log retention, backup jobs, certificate/SMTP/queue/worker/scheduler/storage alerts, and on-call delivery.
18. [ ] Bootstrap the first Super Admin through an isolated one-off task; delete the short-lived bootstrap secret; require immediate password change/session revocation.
19. [ ] Run `infra/aws/scripts/smoke.sh`, then the authenticated `VIP_V1_STAGING_SMOKE_TEST.md` checklist.
20. [ ] Execute and record a managed staging RDS **and EFS** restore drill. Do not promote production without PASS.
21. [ ] Capture deployment manifest, image digests, task-definition revisions, runtime SHA, Alembic head, smoke evidence, alarms, backup/restore evidence, and approvers.

Do not deploy production until staging is stable for the agreed soak window and every applicable item passes. Repeat the sequence with separate production state, data services, storage, secrets, images/web build, DNS, approvals, and evidence.

## 5. Migration acceptance

- [ ] Migration was a single one-off task, not API startup or one task per replica.
- [ ] Checkpoint identifier and availability are recorded before mutation.
- [ ] Command used the frozen API image digest.
- [ ] `alembic upgrade head` exited 0.
- [ ] `alembic current` reports exactly `20260808_0025`.
- [ ] Deterministic governance roles/permissions and connection types exist.
- [ ] No demo/QA seeds, QA organizations, fixture users, or known passwords exist.
- [ ] API traffic was not promoted before migration success.

## 6. Infrastructure acceptance

- [ ] Final application SHA pinned: `4e97591845a93037d6e54b0237bcb3208d1b2696`.
- [ ] API and web images are immutable digest references.
- [ ] API runtime `/api/v1/version` reports the full frozen SHA and correct environment.
- [ ] Both images have matching OCI revision labels; deployment manifest records digests.
- [ ] HTTPS is enabled; HTTP redirects; TLS 1.2+; certificates valid.
- [ ] WAF/rate limits, security headers, secure cookies, CORS, CSRF, SameSite, and trusted hosts are validated.
- [ ] RDS is private, encrypted, TLS-forced, backed up, monitored, and has no QA data.
- [ ] Redis is private, TLS/authenticated, encrypted, `noeviction`, backed up, and monitored.
- [ ] EFS is private, encrypted, persistent, mounted at `/data`, and backed up.
- [ ] Secrets are injected securely and absent from Git/images/frontend/logs/plan output.
- [ ] Migrations are at `20260808_0025`.
- [ ] API and web have at least two healthy tasks in production.
- [ ] Dashboard/export and pipeline workers are running with fresh heartbeats.
- [ ] Scheduler is a singleton and scheduling is disabled everywhere else.
- [ ] SMTP delivery and bounce/complaint visibility pass.
- [ ] Availability, 5xx, latency, RDS, Redis, worker, scheduler, pipeline/export, storage, backup, and security alerts are enabled and delivered.
- [ ] RDS PITR and RDS/EFS AWS Backup are enabled.
- [ ] Managed staging RDS/EFS restore test passes with measured RPO/RTO.
- [ ] Infrastructure smoke passes.
- [ ] Authenticated staging smoke passes.
- [ ] Rollback to prior task definitions and data-recovery decision tree has been rehearsed.
- [ ] Operational owner/on-call, escalation, maintenance window, and change record are assigned.

## 7. Production approval record

```text
Environment:
Change ticket:
Application SHA:
API digest:
Web digest:
Alembic head:
Terraform plan/apply reference:
Migration task ARN / exit:
Runtime version evidence:
Backup checkpoint:
Restore drill evidence:
Smoke evidence:
Security scan evidence:
Operations owner:
Approvers:
Deployment UTC:
```
